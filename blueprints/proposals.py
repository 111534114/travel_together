from flask import Blueprint, flash, redirect, render_template, request, session, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式
import proposal_review  # 提案 AI 小幫手(預審、自動收下)
from proposal_actions import approve_proposal_record, return_proposal_record  # 收下／退回共用邏輯(含通知會員)

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
    ai_filter = request.args.get("ai", "").strip()  # AI 小幫手建議篩選：approve / return / needs_human / unreviewed
    if ai_filter not in ("approve", "return", "needs_human", "unreviewed"):
        ai_filter = ""
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
            page=1, total_pages=1, total=0, reviews={}, ai_filter=ai_filter, auto_approve=False, ai_enabled=False,
            ai_missing_message=proposal_review.TABLE_MISSING_MESSAGE,
            ai_labels=proposal_review.RECOMMENDATION_LABELS,
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        ai_enabled = proposal_review.table_available(cursor)  # AI 預審資料表能不能用(不存在時試著建立)
        if not ai_enabled:
            ai_filter = ""
        ai_join = "LEFT JOIN proposal_ai_reviews ar ON ar.proposal_id = p.proposal_id" if ai_enabled else ""
        params = []  # 建立 SQL 參數清單
        conditions = []  # 篩選條件

        if status != "all":  # 如果不是要看全部
            conditions.append("p.content_review_status = %s")  # 加上依審核狀態篩選的條件
            params.append(status)  # 加入對應參數
        if ai_filter == "unreviewed":
            conditions.append("p.proposal_type IN ('attraction','restaurant','accommodation') AND (ar.status IS NULL OR ar.status <> 'done')")
        elif ai_filter:
            conditions.append("ar.status = 'done' AND ar.recommendation = %s")
            params.append(ai_filter)
        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor.execute(  # 查詢符合條件的提案總筆數(用來算分頁)
            f"""
            SELECT COUNT(*) AS total
            FROM proposals p
            {ai_join}
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
            {ai_join}
            {where_clause}
            ORDER BY p.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, offset]  # 加上分頁用的 LIMIT、OFFSET 參數
        )
        proposals = cursor.fetchall()  # 取出當頁提案清單
        reviews = proposal_review.get_reviews(cursor, [p["proposal_id"] for p in proposals])  # 每筆的 AI 小紙條
        auto_approve, _ = proposal_review.auto_approve_setting(cursor) if ai_enabled else (False, None)  # 自動收下開關

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
        reviews=reviews,  # {proposal_id: AI 預審結果}
        ai_filter=ai_filter,  # 目前的 AI 建議篩選
        ai_labels=proposal_review.RECOMMENDATION_LABELS,
        auto_approve=auto_approve,
        ai_enabled=ai_enabled,  # False 代表 AI 預審資料表還沒建立
        ai_missing_message=proposal_review.TABLE_MISSING_MESSAGE,
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
        review = proposal_review.get_reviews(cursor, [proposal_id]).get(proposal_id) if proposal else None  # AI 小紙條

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
        review=review,  # AI 小幫手的預審結果(還沒檢查過是 None)
        ai_labels=proposal_review.RECOMMENDATION_LABELS,
    )


def _ai_suggestions(cursor, proposal_id):
    """AI 預審從 Google 查到、規則也確認過的欄位(座標、營業時間)，收下時一起帶進正式資料。"""
    review = proposal_review.get_reviews(cursor, [proposal_id]).get(proposal_id)
    if not review or review.get("status") != "done":
        return None
    return review["result"].get("suggestions")


@proposals_bp.route("/<int:proposal_id>/approve", methods=["POST"])  # 設定核准提案的路由，網址帶入提案 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def approve_proposal(proposal_id):  # 定義核准提案函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 嘗試更新資料(建立正式資料、更新狀態、寫紀錄、通知會員，都在 proposal_actions 裡)
        ok, message = approve_proposal_record(
            cursor, proposal_id, session["user_id"], log_action, suggestions=_ai_suggestions(cursor, proposal_id)
        )
        if not ok:
            flash(message, "error")
            return redirect(url_for("proposals.list_proposals"))
        connection.commit()  # 提交交易(提案狀態、新建立的正式資料、操作紀錄、通知一起寫入)
        flash(message, "success")  # 顯示成功訊息
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

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 嘗試更新資料(更新狀態、寫紀錄、通知會員)
        ok, message = return_proposal_record(cursor, proposal_id, session["user_id"], review_note[:500], log_action)
        if not ok:
            flash(message, "error")
            return redirect(url_for("proposals.list_proposals"))
        connection.commit()  # 提交交易
        flash(message, "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外
        connection.rollback()  # 回復交易
        print("退回提案失敗：", error)  # 在伺服器端印出錯誤內容
        flash("退回提案失敗", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁


@proposals_bp.route("/<int:proposal_id>/ai-review", methods=["POST"])  # 管理員按「再檢查一次」
@login_required("content_admin")
def rerun_ai_review(proposal_id):
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))
    cursor = connection.cursor(dictionary=True)
    queued = False
    try:
        queued, message = proposal_review.request_review(cursor, proposal_id, session["user_id"], manual=True)
        if queued:
            log_action(cursor, "ai_review_proposal", "proposal", proposal_id, "請 AI 小幫手重新檢查提案")
        connection.commit()
        flash(message, "success" if queued else "error")
    except Exception as error:
        connection.rollback()
        print("排入 AI 預審失敗：", error)
        flash("小幫手暫時沒辦法檢查，請稍後再試", "error")
    finally:
        cursor.close()
        connection.close()
    if queued:
        proposal_review.start_review(proposal_id)
    return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))


@proposals_bp.route("/ai-review/pending", methods=["POST"])  # 一次請小幫手檢查所有還沒檢查過的待審提案
@login_required("content_admin")
def review_all_pending():
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("proposals.list_proposals"))
    cursor = connection.cursor(dictionary=True)
    queued_ids = []
    try:
        for proposal_id in proposal_review.pending_without_review(cursor, limit=30):
            queued, _ = proposal_review.request_review(cursor, proposal_id, session["user_id"])
            if queued:
                queued_ids.append(proposal_id)
        if queued_ids:
            log_action(cursor, "ai_review_proposal", "proposal", None, f"請 AI 小幫手檢查 {len(queued_ids)} 筆待審提案")
        connection.commit()
        if queued_ids:
            flash(f"已請小幫手檢查 {len(queued_ids)} 筆提案，一筆大約 10～30 秒，等一下重新整理就能看到結果", "success")
        else:
            flash("沒有需要檢查的提案：待審核的提案都已經檢查過了", "success")
    except Exception as error:
        connection.rollback()
        print("排入 AI 預審失敗：", error)
        queued_ids = []
        flash("小幫手暫時沒辦法檢查，請稍後再試", "error")
    finally:
        cursor.close()
        connection.close()
    for proposal_id in queued_ids:
        proposal_review.start_review(proposal_id)
    return redirect(url_for("proposals.list_proposals", status="pending"))


@proposals_bp.route("/batch-approve", methods=["POST"])  # 勾選多筆，一次收下
@login_required("content_admin")
def batch_approve():
    ids = []
    for value in request.form.getlist("proposal_ids"):
        if value.isdigit() and int(value) not in ids:
            ids.append(int(value))
    back = redirect(url_for("proposals.list_proposals", status="pending", ai=request.form.get("ai", "")))
    if not ids:
        flash("請先勾選要收下的提案", "error")
        return back
    if len(ids) > 100:
        flash("一次最多收下 100 筆", "error")
        return back
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return back
    cursor = connection.cursor(dictionary=True)
    try:
        approved, skipped = 0, 0
        for proposal_id in ids:
            ok, _ = approve_proposal_record(
                cursor, proposal_id, session["user_id"], log_action,
                suggestions=_ai_suggestions(cursor, proposal_id), require_pending=True,
            )
            if ok:
                approved += 1
            else:
                skipped += 1
        connection.commit()
        flash(f"已收下 {approved} 筆提案，並通知提案的會員" + (f"；{skipped} 筆已經不是待審核，略過" if skipped else ""), "success")
    except Exception as error:
        connection.rollback()
        print("批次核准提案失敗：", error)
        flash("一次收下失敗，所有提案都沒有變動，請再試一次", "error")
    finally:
        cursor.close()
        connection.close()
    return back


@proposals_bp.route("/auto-approve", methods=["POST"])  # 自動收下開關
@login_required("content_admin")
def toggle_auto_approve():
    enabled = request.form.get("enabled") == "1"
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("proposals.list_proposals"))
    cursor = connection.cursor(dictionary=True)
    try:
        proposal_review.set_auto_approve(cursor, enabled, session["user_id"])
        log_action(cursor, "toggle_proposal_auto_approve", "setting", None,
                   "開啟提案自動收下" if enabled else "關閉提案自動收下")
        connection.commit()
        flash("已開啟自動收下：小幫手檢查全部通過的提案會自動收下" if enabled else "已關閉自動收下", "success")
    except Exception as error:
        connection.rollback()
        print("切換自動收下失敗：", error)
        flash("切換失敗，請再試一次", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("proposals.list_proposals"))


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
