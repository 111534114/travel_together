from flask import Blueprint, flash, render_template, request  # 匯入 Flask 藍圖與常用功能

from activity_log import ACTION_LABELS  # 匯入操作代碼對應的中文名稱
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式

logs_bp = Blueprint("logs", __name__, url_prefix="/content-admin/logs")  # 建立操作紀錄藍圖，網址前綴 /content-admin/logs

PAGE_SIZE = 30  # 定義列表頁每頁顯示筆數


@logs_bp.route("/")  # 設定操作紀錄查詢頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def list_logs():  # 定義操作紀錄查詢頁函式
    keyword = request.args.get("keyword", "").strip()  # 取得搜尋關鍵字(比對說明文字)
    action = request.args.get("action", "").strip()  # 取得動作類型篩選參數
    date_from = request.args.get("date_from", "").strip()  # 取得起始日期篩選參數
    date_to = request.args.get("date_to", "").strip()  # 取得結束日期篩選參數
    page = request.args.get("page", "1")  # 取得頁碼參數(字串)
    page = int(page) if page.isdigit() and int(page) > 0 else 1  # 驗證頁碼為正整數，否則預設第 1 頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "content_admin/logs.html",
            logs=[], actions=[], action_labels=ACTION_LABELS,
            keyword=keyword, action=action, date_from=date_from, date_to=date_to,
            page=1, total_pages=1, total=0
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        conditions = []  # 建立 SQL WHERE 條件清單
        params = []  # 建立對應的參數清單

        if keyword:  # 如果有輸入關鍵字
            conditions.append("l.description LIKE %s")  # 加入依說明文字模糊搜尋的條件
            params.append(f"%{keyword}%")  # 加入對應參數

        if action:  # 如果有篩選動作類型
            conditions.append("l.action = %s")  # 加入動作類型條件
            params.append(action)  # 加入對應參數

        if date_from:  # 如果有指定起始日期
            conditions.append("l.created_at >= %s")  # 加入起始日期條件(含當天)
            params.append(f"{date_from} 00:00:00")  # 加入對應參數，補上當天最早時間

        if date_to:  # 如果有指定結束日期
            conditions.append("l.created_at <= %s")  # 加入結束日期條件(含當天)
            params.append(f"{date_to} 23:59:59")  # 加入對應參數，補上當天最晚時間

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""  # 把所有條件組成 WHERE 子句

        cursor.execute(  # 查詢符合條件的紀錄總筆數(用來算分頁)
            f"SELECT COUNT(*) AS total FROM admin_logs l {where_clause}",
            params
        )
        total = cursor.fetchone()["total"]  # 取出總筆數

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)  # 計算總頁數(無條件進位，至少 1 頁)
        page = min(page, total_pages)  # 如果頁碼超過總頁數，修正為最後一頁
        offset = (page - 1) * PAGE_SIZE  # 計算 SQL 要跳過的筆數

        cursor.execute(  # 查詢當頁的操作紀錄，並關聯出操作人姓名
            f"""
            SELECT l.admin_log_id, l.action, l.target_type, l.target_id,
                   l.description, l.ip_address, l.created_at,
                   u.full_name AS admin_name
            FROM admin_logs l
            JOIN users u ON u.user_id = l.admin_id
            {where_clause}
            ORDER BY l.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, offset]  # 加上分頁用的 LIMIT、OFFSET 參數
        )
        logs = cursor.fetchall()  # 取出當頁操作紀錄清單

        cursor.execute("SELECT DISTINCT action FROM admin_logs ORDER BY action")  # 查詢目前資料庫裡出現過的所有動作代碼
        actions = [row["action"] for row in cursor.fetchall()]  # 整理成動作代碼清單，給篩選下拉選單用

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染操作紀錄查詢頁面
        "content_admin/logs.html",
        logs=logs,  # 當頁操作紀錄清單
        actions=actions,  # 動作類型下拉選單資料
        action_labels=ACTION_LABELS,  # 動作代碼對應的中文名稱
        keyword=keyword,  # 搜尋關鍵字(回填搜尋框)
        action=action,  # 動作類型篩選值(回填下拉選單)
        date_from=date_from,  # 起始日期篩選值(回填欄位)
        date_to=date_to,  # 結束日期篩選值(回填欄位)
        page=page,  # 目前頁碼
        total_pages=total_pages,  # 總頁數
        total=total,  # 符合條件的總筆數
    )
