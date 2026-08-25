from flask import Blueprint, flash, redirect, render_template, request, session, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式

proposals_bp = Blueprint("proposals", __name__, url_prefix="/content-admin/proposals")  # 建立提案審核藍圖，網址前綴 /content-admin/proposals

STATUS_CHOICES = ("pending", "approved", "returned", "not_required")  # 定義提案審核狀態允許的合法值

STATUS_LABELS = {  # 定義審核狀態對應的中文顯示名稱
    "pending": "待審核",
    "approved": "已核准",
    "returned": "已退回",
    "not_required": "無需審核",
}


@proposals_bp.route("/")  # 設定提案列表頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def list_proposals():  # 定義提案列表頁函式
    status = request.args.get("status", "pending").strip()  # 取得網址上的狀態篩選參數，預設待審核

    if status not in STATUS_CHOICES and status != "all":  # 如果狀態不合法也不是「全部」
        status = "pending"  # 強制改回預設值

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "content_admin/proposals/list.html",
            proposals=[], status=status, status_labels=STATUS_LABELS
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        params = []  # 建立 SQL 參數清單
        where_clause = ""  # 預設沒有篩選條件(顯示全部)

        if status != "all":  # 如果不是要看全部
            where_clause = "WHERE p.content_review_status = %s"  # 加上依審核狀態篩選的條件
            params.append(status)  # 加入對應參數

        cursor.execute(  # 查詢提案清單，並關聯所屬行程名稱與提案人姓名
            f"""
            SELECT p.proposal_id, p.proposal_type, p.title, p.location,
                   p.estimated_cost, p.proposed_date, p.content_review_status,
                   p.created_at, t.trip_name, u.full_name AS proposer_name
            FROM proposals p
            JOIN trips t ON t.trip_id = p.trip_id
            JOIN users u ON u.user_id = p.proposer_id
            {where_clause}
            ORDER BY p.created_at DESC
            """,
            params
        )
        proposals = cursor.fetchall()  # 取出提案清單

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染提案列表頁面
        "content_admin/proposals/list.html",
        proposals=proposals,  # 提案清單
        status=status,  # 目前篩選的狀態
        status_labels=STATUS_LABELS  # 狀態對應的中文名稱
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
        status_labels=STATUS_LABELS  # 狀態對應的中文名稱
    )


@proposals_bp.route("/<int:proposal_id>/approve", methods=["POST"])  # 設定核准提案的路由，網址帶入提案 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def approve_proposal(proposal_id):  # 定義核准提案函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))  # 導回提案詳情頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
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
        connection.commit()  # 提交交易(提案狀態與操作紀錄一起寫入)
        flash("提案已核准", "success")  # 顯示成功訊息
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
