from flask import Blueprint, flash, redirect, render_template, request, session, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式

proposals_bp = Blueprint("proposals", __name__, url_prefix="/content-admin/proposals")  # 建立提案審核藍圖，網址前綴 /content-admin/proposals

PAGE_SIZE = 20  # 定義列表頁每頁顯示筆數

STATUS_CHOICES = ("pending", "approved", "returned", "not_required")  # 定義提案審核狀態允許的合法值

STATUS_LABELS = {  # 定義審核狀態對應的中文顯示名稱
    "pending": "待審核",
    "approved": "已核准",
    "returned": "已退回",
    "not_required": "無需審核",
}

# 提案類型 -> 核准後要寫入的正式資料表、主鍵欄位名稱、以及編輯頁的 blueprint 端點名稱
CATALOG_TABLES = {
    "attraction": ("attractions", "attraction_id", "attractions.edit_attraction"),
    "restaurant": ("restaurants", "restaurant_id", "restaurants.edit_restaurant"),
    "accommodation": ("accommodations", "accommodation_id", "accommodations.edit_accommodation"),
}

PROPOSAL_TYPE_LABELS = {  # 定義提案類型對應的中文顯示名稱
    "attraction": "景點", "restaurant": "餐廳", "accommodation": "住宿",
    "activity": "活動", "transport": "交通", "date": "日期", "other": "其他",
}


def _linked_item_edit_url(proposal):  # 定義內部函式：如果這筆提案核准後已經建立正式資料，組出該筆資料的編輯連結
    catalog = CATALOG_TABLES.get(proposal["proposal_type"])
    if not catalog or not proposal["linked_item_id"]:  # 不是景點/餐廳/住宿類型，或還沒建立正式資料
        return None
    _, id_column, edit_endpoint = catalog
    return url_for(edit_endpoint, **{id_column: proposal["linked_item_id"]})


@proposals_bp.route("/")  # 設定提案列表頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def list_proposals():  # 定義提案列表頁函式
    status = request.args.get("status", "pending").strip()  # 取得網址上的狀態篩選參數，預設待審核
    page = request.args.get("page", "1")  # 取得頁碼參數(字串)
    page = int(page) if page.isdigit() and int(page) > 0 else 1  # 驗證頁碼為正整數，否則預設第 1 頁

    if status not in STATUS_CHOICES and status != "all":  # 如果狀態不合法也不是「全部」
        status = "pending"  # 強制改回預設值

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "content_admin/proposals/list.html",
            proposals=[], status=status, status_labels=STATUS_LABELS,
            page=1, total_pages=1, total=0
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        params = []  # 建立 SQL 參數清單
        where_clause = ""  # 預設沒有篩選條件(顯示全部)

        if status != "all":  # 如果不是要看全部
            where_clause = "WHERE p.content_review_status = %s"  # 加上依審核狀態篩選的條件
            params.append(status)  # 加入對應參數

        cursor.execute(  # 查詢符合條件的提案總筆數(用來算分頁)
            f"""
            SELECT COUNT(*) AS total
            FROM proposals p
            {where_clause}
            """,
            params
        )
        total = cursor.fetchone()["total"]  # 取出總筆數

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)  # 計算總頁數(無條件進位，至少 1 頁)
        page = min(page, total_pages)  # 如果頁碼超過總頁數，修正為最後一頁
        offset = (page - 1) * PAGE_SIZE  # 計算 SQL 要跳過的筆數

        cursor.execute(  # 查詢當頁的提案清單，並關聯所屬行程名稱與提案人姓名
            f"""
            SELECT p.proposal_id, p.proposal_type, p.title, p.location,
                   p.estimated_cost, p.proposed_date, p.content_review_status,
                   p.created_at, t.trip_name, u.full_name AS proposer_name
            FROM proposals p
            JOIN trips t ON t.trip_id = p.trip_id
            JOIN users u ON u.user_id = p.proposer_id
            {where_clause}
            ORDER BY p.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, offset]  # 加上分頁用的 LIMIT、OFFSET 參數
        )
        proposals = cursor.fetchall()  # 取出當頁提案清單

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染提案列表頁面
        "content_admin/proposals/list.html",
        proposals=proposals,  # 當頁提案清單
        status=status,  # 目前篩選的狀態
        status_labels=STATUS_LABELS,  # 狀態對應的中文名稱
        type_labels=PROPOSAL_TYPE_LABELS,  # 提案類型對應的中文名稱
        page=page,  # 目前頁碼
        total_pages=total_pages,  # 總頁數
        total=total,  # 符合條件的總筆數
    )


@proposals_bp.route("/<int:proposal_id>")  # 設定提案詳情頁路由，網址帶入提案 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def view_proposal(proposal_id):  # 定義提案詳情頁函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.list_proposals"))  # 導回提案列表頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        cursor.execute(  # 查詢單筆提案完整資料，並關聯行程名稱、提案人資訊、審核者姓名
            """
            SELECT p.*, t.trip_name, u.full_name AS proposer_name,
                   u.email AS proposer_email, r.full_name AS reviewer_name
            FROM proposals p
            JOIN trips t ON t.trip_id = p.trip_id
            JOIN users u ON u.user_id = p.proposer_id
            LEFT JOIN users r ON r.user_id = p.reviewed_by
            WHERE p.proposal_id = %s
            """,
            (proposal_id,)
        )
        proposal = cursor.fetchone()  # 取出這筆提案資料(查無資料則為 None)

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    if proposal is None:  # 如果查無此提案
        flash("找不到這筆提案", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.list_proposals"))  # 導回提案列表頁

    return render_template(  # 渲染提案詳情頁面
        "content_admin/proposals/detail.html",
        proposal=proposal,  # 提案完整資料
        status_labels=STATUS_LABELS,  # 狀態對應的中文名稱
        type_labels=PROPOSAL_TYPE_LABELS,  # 提案類型對應的中文名稱
        needs_review=proposal["proposal_type"] in CATALOG_TABLES,  # 這個類型核准後是否會自動建立正式資料
        linked_item_edit_url=_linked_item_edit_url(proposal),  # 如果已經建立正式資料，給編輯連結
    )


@proposals_bp.route("/<int:proposal_id>/approve", methods=["POST"])  # 設定核准提案的路由，網址帶入提案 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def approve_proposal(proposal_id):  # 定義核准提案函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標(要讀取提案內容才能決定要不要建立正式資料)

    try:  # 嘗試更新資料
        cursor.execute(  # 查詢提案內容，連同所屬行程的國家/城市(新資料的國家/城市就跟著這趟行程走)
            """
            SELECT p.proposal_id, p.proposal_type, p.title, p.location, p.description,
                   p.estimated_cost, p.website_url, p.linked_item_id,
                   t.country_id, t.city_id
            FROM proposals p
            JOIN trips t ON t.trip_id = p.trip_id
            WHERE p.proposal_id = %s
            """,
            (proposal_id,)
        )
        proposal = cursor.fetchone()  # 取出提案資料

        if proposal is None:  # 如果提案不存在(理論上不會發生，防呆用)
            flash("找不到這筆提案", "error")  # 顯示錯誤提示
            return redirect(url_for("proposals.list_proposals"))  # 導回提案列表頁

        created_note = ""  # 建立正式資料後，要附加在成功訊息裡的補充說明

        # 景點/餐廳/住宿類型的提案，核准時要順便在對應的正式資料表建一筆新資料(狀態設為待確認，
        # 因為提案沒有分類等欄位，需要管理員再進去補齊才能正式啟用)；linked_item_id 有值代表之前已經建立過，
        # 不要重複建立(例如退回後又重新核准的情況)
        catalog = CATALOG_TABLES.get(proposal["proposal_type"])
        if catalog and not proposal["linked_item_id"]:
            table, id_column, edit_endpoint = catalog
            name = proposal["title"]
            address = proposal["location"]
            description = proposal["description"]
            website_url = proposal["website_url"]
            country_id = proposal["country_id"]
            city_id = proposal["city_id"]

            if proposal["proposal_type"] == "attraction":
                cursor.execute(
                    """
                    INSERT INTO attractions (name, country_id, city_id, address, ticket_price, description, website_url, status, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',%s)
                    """,
                    (name, country_id, city_id, address, proposal["estimated_cost"] or 0, description, website_url, session["user_id"])
                )
            elif proposal["proposal_type"] == "restaurant":
                cursor.execute(
                    """
                    INSERT INTO restaurants (name, country_id, city_id, address, description, website_url, status, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,'pending',%s)
                    """,
                    (name, country_id, city_id, address, description, website_url, session["user_id"])
                )
            else:  # accommodation
                cursor.execute(
                    """
                    INSERT INTO accommodations (name, country_id, city_id, address, price_per_night, description, website_url, status, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',%s)
                    """,
                    (name, country_id, city_id, address, proposal["estimated_cost"] or 0, description, website_url, session["user_id"])
                )

            new_item_id = cursor.lastrowid  # 取得剛剛建立的新資料 ID
            log_action(  # 把這次建立正式資料的動作也寫入操作紀錄
                cursor, "create_from_proposal", proposal["proposal_type"], new_item_id,
                f"由提案核准建立：{name}（提案 #{proposal_id}），狀態為待確認，請補齊分類等資訊"
            )
            cursor.execute(  # 把新建立的資料 ID 記回提案，避免之後重複核准時又建立第二筆
                "UPDATE proposals SET linked_item_id = %s WHERE proposal_id = %s",
                (new_item_id, proposal_id)
            )
            created_note = "，已自動建立一筆對應資料(狀態為待確認)，請記得補上分類、地址等資訊後再啟用"

        cursor.execute(  # 執行核准提案的 SQL：更新審核狀態、審核者、審核時間，並清空之前的退回原因
            """
            UPDATE proposals
            SET content_review_status = 'approved',
                reviewed_by = %s, reviewed_at = NOW(), review_note = NULL
            WHERE proposal_id = %s
            """,
            (session["user_id"], proposal_id)
        )
        log_action(cursor, "approve_proposal", "proposal", proposal_id, "核准提案")  # 寫入操作紀錄
        connection.commit()  # 提交交易(提案狀態、新建立的正式資料、操作紀錄一起寫入)
        flash(f"提案已核准{created_note}", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外
        connection.rollback()  # 回復交易
        print("核准提案失敗：", error)  # 在伺服器端印出錯誤內容
        flash("核准提案失敗", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁


@proposals_bp.route("/<int:proposal_id>/return", methods=["POST"])  # 設定退回提案的路由，網址帶入提案 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def return_proposal(proposal_id):  # 定義退回提案函式
    review_note = request.form.get("review_note", "").strip()  # 取得表單輸入的退回原因

    if not review_note:  # 如果沒有填寫退回原因
        flash("退回提案時請填寫退回原因", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
        cursor.execute(  # 執行退回提案的 SQL：更新審核狀態、審核者、審核時間、退回原因
            """
            UPDATE proposals
            SET content_review_status = 'returned',
                reviewed_by = %s, reviewed_at = NOW(), review_note = %s
            WHERE proposal_id = %s
            """,
            (session["user_id"], review_note, proposal_id)
        )
        log_action(cursor, "return_proposal", "proposal", proposal_id, f"退回提案，原因：{review_note}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(提案狀態與操作紀錄一起寫入)
        flash("提案已退回", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外
        connection.rollback()  # 回復交易
        print("退回提案失敗：", error)  # 在伺服器端印出錯誤內容
        flash("退回提案失敗", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁


@proposals_bp.route("/<int:proposal_id>/update", methods=["POST"])  # 設定修正提案內容的路由，網址帶入提案 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def update_proposal(proposal_id):  # 定義修正提案內容函式
    title = request.form.get("title", "").strip()  # 取得表單輸入的標題
    location = request.form.get("location", "").strip() or None  # 取得地點，空字串轉成 None
    description = request.form.get("description", "").strip() or None  # 取得說明，空字串轉成 None
    website_url = request.form.get("website_url", "").strip() or None  # 取得參考網址，空字串轉成 None
    estimated_cost = request.form.get("estimated_cost", "").strip()  # 取得預估花費(先當字串)
    proposed_date = request.form.get("proposed_date", "").strip() or None  # 取得建議日期，空字串轉成 None

    if not title:  # 如果標題是空的
        flash("請輸入提案標題", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁

    try:  # 嘗試把預估花費轉成數字
        estimated_cost = float(estimated_cost) if estimated_cost else 0  # 有輸入就轉浮點數，沒輸入就是 0
        if estimated_cost < 0:  # 如果是負數
            raise ValueError  # 主動拋出錯誤，交給下面的 except 處理
    except ValueError:  # 如果轉換失敗或是負數
        flash("預估花費必須是不小於 0 的數字", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
        cursor.execute(  # 執行更新提案內容的 SQL(不會改動審核狀態，只修正內容)
            """
            UPDATE proposals
            SET title = %s, location = %s, description = %s,
                website_url = %s, estimated_cost = %s, proposed_date = %s
            WHERE proposal_id = %s
            """,
            (title, location, description, website_url, estimated_cost,
             proposed_date, proposal_id)
        )
        log_action(cursor, "update_proposal", "proposal", proposal_id, f"修正提案內容：{title}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(提案內容與操作紀錄一起寫入)
        flash("提案內容已修正", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外
        connection.rollback()  # 回復交易
        print("修正提案失敗：", error)  # 在伺服器端印出錯誤內容
        flash("修正提案失敗", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁
