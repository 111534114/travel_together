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
    },
    "restaurant": {
        "table": "restaurants",  # 餐廳資料表名稱
        "pk": "restaurant_id",  # 餐廳主鍵欄位名稱
        "label": "餐廳",  # 中文標籤
    },
    "accommodation": {
        "table": "accommodations",  # 住宿資料表名稱
        "pk": "accommodation_id",  # 住宿主鍵欄位名稱
        "label": "住宿",  # 中文標籤
    },
}


@ai_data_bp.route("/")  # 設定 AI 資料維護頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def list_ai_data():  # 定義 AI 資料維護頁函式
    item_type = request.args.get("type", "attraction").strip()  # 取得網址上的資料類型參數，預設景點

    if item_type not in TYPE_CONFIG:  # 如果類型不在允許清單內(防止網址被亂改)
        item_type = "attraction"  # 強制改回預設值

    config = TYPE_CONFIG[item_type]  # 取得這個類型對應的資料表設定

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "content_admin/ai_data.html",
            items=[], item_type=item_type, type_config=TYPE_CONFIG
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        cursor.execute(  # 查詢該類型所有資料，關聯國家、城市名稱及最後確認人姓名，未確認的排最前面
            f"""
            SELECT t.{config['pk']} AS item_id, t.name, t.updated_at,
                   t.ai_verified_at, co.name AS country_name, ci.name AS city_name,
                   v.full_name AS verified_by_name
            FROM {config['table']} t
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            LEFT JOIN users v ON v.user_id = t.ai_verified_by
            ORDER BY (t.ai_verified_at IS NULL) DESC, t.ai_verified_at ASC, t.name ASC
            """
        )
        items = cursor.fetchall()  # 取出資料清單

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染 AI 資料維護頁面
        "content_admin/ai_data.html",
        items=items,  # 資料清單
        item_type=item_type,  # 目前選擇的資料類型
        type_config=TYPE_CONFIG  # 各類型的設定(用來畫分頁籤)
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
        return redirect(url_for("ai_data.list_ai_data", type=item_type))  # 導回 AI 資料維護頁(保留原本類型)

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

    return redirect(url_for("ai_data.list_ai_data", type=item_type))  # 導回 AI 資料維護頁(保留原本類型)
