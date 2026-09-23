from flask import Blueprint, flash, redirect, render_template, request, session, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式

ai_data_bp = Blueprint("ai_data", __name__, url_prefix="/content-admin/ai-data")  # 建立 AI 資料維護藍圖，網址前綴 /content-admin/ai-data

TYPE_CONFIG = {  # 定義每種資料類型對應的資料表名稱、主鍵欄位、中文標籤(避免直接把使用者輸入拼進 SQL)
    "attraction": {
        "table": "attractions",  # 景點資料表名稱
        "pk": "attraction_id",  # 景點主鍵欄位名稱
        "label": "景點",  # 中文標籤
        "check_fields": [  # 自動審核要檢查「是否有填」的欄位，及顯示用的中文名稱
            ("address", "地址"),
            ("opening_hours", "營業時間"),
            ("description", "介紹"),
            ("image_path", "圖片"),
        ],
    },
    "restaurant": {
        "table": "restaurants",  # 餐廳資料表名稱
        "pk": "restaurant_id",  # 餐廳主鍵欄位名稱
        "label": "餐廳",  # 中文標籤
        "check_fields": [
            ("address", "地址"),
            ("opening_hours", "營業時間"),
            ("description", "介紹"),
            ("image_path", "圖片"),
        ],
    },
    "accommodation": {
        "table": "accommodations",  # 住宿資料表名稱
        "pk": "accommodation_id",  # 住宿主鍵欄位名稱
        "label": "住宿",  # 中文標籤
        "check_fields": [
            ("address", "地址"),
            ("description", "介紹"),
            ("image_path", "圖片"),
            ("accommodation_type", "住宿類型"),
        ],
    },
}


def _missing_fields(row, check_fields):  # 檢查一筆資料哪些欄位是空的，回傳缺少欄位的中文名稱清單
    missing = []  # 準備存放缺少欄位的中文名稱
    for column, label in check_fields:  # 逐一檢查每個要求的欄位
        value = row.get(column)  # 取得該欄位目前的值
        if value is None or (isinstance(value, str) and not value.strip()):  # 空值或空白字串都算沒填
            missing.append(label)  # 記錄缺少的欄位中文名稱
    return missing  # 回傳缺少欄位清單(空清單代表資料完整)


@ai_data_bp.route("/")  # 設定 AI 資料維護頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def list_ai_data():  # 定義 AI 資料維護頁函式
    item_type = request.args.get("type", "attraction").strip()  # 取得網址上的資料類型參數，預設景點
    keyword = request.args.get("keyword", "").strip()  # 取得搜尋關鍵字參數

    if item_type not in TYPE_CONFIG:  # 如果類型不在允許清單內(防止網址被亂改)
        item_type = "attraction"  # 強制改回預設值

    config = TYPE_CONFIG[item_type]  # 取得這個類型對應的資料表設定

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "content_admin/ai_data.html",
            items=[], item_type=item_type, type_config=TYPE_CONFIG, keyword=keyword
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        conditions = ["t.deleted_at IS NULL"]  # 一律排除已軟刪除(在回收桶裡)的資料
        params = []  # 建立對應的參數清單

        if keyword:  # 如果有輸入關鍵字
            conditions.append("t.name LIKE %s")  # 加入依名稱模糊搜尋的條件
            params.append(f"%{keyword}%")  # 加入對應參數

        where_clause = "WHERE " + " AND ".join(conditions)  # 把所有條件組成 WHERE 子句
        check_columns = ", ".join(f"t.{column}" for column, _label in config["check_fields"])  # 組出自動審核要用的欄位清單

        cursor.execute(  # 查詢該類型符合條件的資料，關聯國家、城市名稱及最後確認人姓名，未確認的排最前面
            f"""
            SELECT t.{config['pk']} AS item_id, t.name, t.updated_at,
                   t.ai_verified_at, co.name AS country_name, ci.name AS city_name,
                   v.full_name AS verified_by_name, {check_columns}
            FROM {config['table']} t
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            LEFT JOIN users v ON v.user_id = t.ai_verified_by
            {where_clause}
            ORDER BY (t.ai_verified_at IS NULL) DESC, t.ai_verified_at ASC, t.name ASC
            """,
            params
        )
        items = cursor.fetchall()  # 取出資料清單

        auto_verified_ids = []  # 記錄這次自動審核通過、要標記已確認的資料 ID
        for item in items:  # 逐筆檢查尚未確認的資料是否已經填寫完整
            if item["ai_verified_at"] is not None:  # 已經確認過(不論人工或系統)就不用再檢查
                item["missing_fields"] = []  # 已確認資料不顯示缺漏欄位
                continue
            missing = _missing_fields(item, config["check_fields"])  # 檢查這筆資料缺少哪些欄位
            item["missing_fields"] = missing  # 存到這筆資料上，模板要顯示缺少什麼
            if not missing:  # 資料填寫完整 -> 系統自動審核通過
                auto_verified_ids.append(item["item_id"])  # 記下這筆的 ID，等等一次寫入資料庫

        if auto_verified_ids:  # 如果有資料這次要被系統自動審核通過
            write_cursor = connection.cursor()  # 另開一個一般游標執行更新
            for item_id in auto_verified_ids:  # 逐筆把系統自動審核結果寫入資料庫
                write_cursor.execute(  # 標記為已確認，確認人留空代表是系統自動審核，而非人工點擊
                    f"""
                    UPDATE {config['table']}
                    SET ai_verified_at = NOW(), ai_verified_by = NULL
                    WHERE {config['pk']} = %s
                    """,
                    (item_id,)
                )
                log_action(  # 把系統自動審核動作寫入操作紀錄
                    write_cursor, "auto_verify_ai_data", item_type, item_id,
                    f"系統自動審核通過{config['label']}資料(欄位皆已填寫)"
                )
            connection.commit()  # 一次提交所有自動審核結果
            write_cursor.close()  # 關閉寫入用游標

            cursor.execute(  # 重新查詢確認時間，讓畫面顯示剛剛系統自動審核的時間
                f"SELECT {config['pk']} AS item_id, ai_verified_at FROM {config['table']} WHERE {config['pk']} IN ({','.join(['%s'] * len(auto_verified_ids))})",
                auto_verified_ids
            )
            refreshed = {row["item_id"]: row["ai_verified_at"] for row in cursor.fetchall()}  # 建立 ID 對應最新確認時間的字典
            for item in items:  # 把最新的確認時間更新回原本要顯示的清單
                if item["item_id"] in refreshed:  # 如果這筆是這次自動審核的資料
                    item["ai_verified_at"] = refreshed[item["item_id"]]  # 更新顯示用的確認時間

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染 AI 資料維護頁面
        "content_admin/ai_data.html",
        items=items,  # 資料清單
        item_type=item_type,  # 目前選擇的資料類型
        type_config=TYPE_CONFIG,  # 各類型的設定(用來畫分頁籤)
        keyword=keyword,  # 搜尋關鍵字(回填搜尋框)
    )


@ai_data_bp.route("/<item_type>/<int:item_id>/verify", methods=["POST"])  # 設定標記資料已確認的路由，網址帶入類型與資料 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def verify_item(item_type, item_id):  # 定義標記已確認函式
    if item_type not in TYPE_CONFIG:  # 如果類型不在允許清單內(防止網址被亂改去更新其他資料表)
        flash("資料類型錯誤", "error")  # 顯示錯誤提示
        return redirect(url_for("ai_data.list_ai_data"))  # 導回 AI 資料維護頁

    config = TYPE_CONFIG[item_type]  # 取得這個類型對應的資料表設定

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("ai_data.list_ai_data", type=item_type, keyword=request.args.get("keyword", "")))  # 導回 AI 資料維護頁(保留原本類型與搜尋關鍵字)

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
        cursor.execute(  # 執行標記已確認的 SQL：把確認時間設為現在、確認人設為目前登入者
            f"""
            UPDATE {config['table']}
            SET ai_verified_at = NOW(), ai_verified_by = %s
            WHERE {config['pk']} = %s
            """,
            (session["user_id"], item_id)
        )
        log_action(  # 把這次標記確認動作寫入操作紀錄
            cursor, "verify_ai_data", item_type, item_id,
            f"標記{config['label']}資料已確認"
        )
        connection.commit()  # 提交交易(確認狀態與操作紀錄一起寫入)
        flash(f"已標記此{config['label']}資料為今日已確認", "success")  # 顯示成功訊息(帶入中文類型名稱)
    except Exception as error:  # 如果更新過程發生例外
        connection.rollback()  # 回復交易
        print("標記 AI 資料確認失敗：", error)  # 在伺服器端印出錯誤內容
        flash("標記失敗", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("ai_data.list_ai_data", type=item_type, keyword=request.args.get("keyword", "")))  # 導回 AI 資料維護頁(保留原本類型與搜尋關鍵字)
