from flask import request, session  # 匯入 Flask 的 request(取得來源 IP)、session(取得目前登入者)

ACTION_LABELS = {  # 定義每種操作代碼對應的中文顯示名稱，給操作紀錄頁面用
    "create_attraction": "新增景點",
    "update_attraction": "更新景點",
    "delete_attraction": "刪除景點",
    "import_attractions": "匯入景點",
    "create_restaurant": "新增餐廳",
    "update_restaurant": "更新餐廳",
    "delete_restaurant": "刪除餐廳",
    "import_restaurants": "匯入餐廳",
    "create_accommodation": "新增住宿",
    "update_accommodation": "更新住宿",
    "delete_accommodation": "刪除住宿",
    "import_accommodations": "匯入住宿",
    "create_country": "新增國家",
    "update_country": "更新國家",
    "delete_country": "刪除國家",
    "create_city": "新增城市",
    "update_city": "更新城市",
    "delete_city": "刪除城市",
    "create_category": "新增分類",
    "update_category": "更新分類",
    "delete_category": "刪除分類",
    "approve_proposal": "核准提案",
    "return_proposal": "退回提案",
    "update_proposal": "修正提案",
    "verify_ai_data": "標記AI資料已確認",
}


def log_action(cursor, action, target_type=None, target_id=None, description=None):  # 定義共用函式：把一筆操作紀錄寫進 admin_logs 資料表
    cursor.execute(  # 執行新增操作紀錄的 SQL
        """
        INSERT INTO admin_logs
        (admin_id, action, target_type, target_id, description, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            session.get("user_id"),  # 目前登入的管理員 ID
            action,  # 操作代碼(例如 create_attraction)
            target_type,  # 操作對象類型(例如 attraction)，可為 None
            target_id,  # 操作對象的 ID，可為 None
            description,  # 這筆操作的文字說明
            request.remote_addr,  # 發出這個請求的來源 IP
        )
    )  # 注意：這裡只是把 SQL 加進同一個交易，實際寫入要等呼叫端執行 connection.commit()
