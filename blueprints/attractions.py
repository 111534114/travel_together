import csv  # 匯入 csv，用來解析上傳的 CSV 檔案內容
import io  # 匯入 io，用來把上傳的檔案內容包裝成可供 csv 模組讀取的物件

from flask import Blueprint, flash, redirect, render_template, request, session, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式
from utils import (  # 匯入圖片、下拉選單、CSV 匯入匯出相關的共用工具函式
    csv_response,  # 組成 CSV 檔案下載回應
    delete_uploaded_image,  # 刪除已上傳圖片
    get_categories,  # 取得分類清單
    get_cities,  # 取得城市清單
    get_countries,  # 取得國家清單
    get_or_create_category,  # 依名稱找分類，找不到就自動新增
    get_or_create_city,  # 依名稱找城市，找不到就自動新增
    get_or_create_country,  # 依名稱找國家，找不到就自動新增
    save_uploaded_image,  # 儲存上傳圖片
)

attractions_bp = Blueprint("attractions", __name__, url_prefix="/content-admin/attractions")  # 建立景點管理藍圖，網址前綴 /content-admin/attractions

PAGE_SIZE = 20  # 定義列表頁每頁顯示筆數

STATUS_CHOICES = ("active", "hidden", "pending")  # 定義景點狀態允許的合法值


def _parse_form(form_data):  # 定義內部函式：把表單資料解析成乾淨的欄位字典，並做基本驗證
    form = {  # 從表單中逐一取出欄位，並做去除空白等初步處理
        "category_id": form_data.get("category_id", "").strip() or None,  # 分類 ID，空字串轉成 None(未分類)
        "name": form_data.get("name", "").strip(),  # 景點名稱
        "country_id": form_data.get("country_id", "").strip(),  # 國家 ID
        "city_id": form_data.get("city_id", "").strip(),  # 城市 ID
        "address": form_data.get("address", "").strip() or None,  # 地址，空字串轉成 None
        "opening_hours": form_data.get("opening_hours", "").strip() or None,  # 開放時間，空字串轉成 None
        "ticket_price": form_data.get("ticket_price", "").strip(),  # 票價(先當字串處理，後面再轉數字)
        "suggested_duration_minutes": form_data.get("suggested_duration_minutes", "").strip(),  # 建議停留分鐘數(先當字串)
        "description": form_data.get("description", "").strip() or None,  # 景點描述，空字串轉成 None
        "website_url": form_data.get("website_url", "").strip() or None,  # 官方網站，空字串轉成 None
        "is_popular": form_data.get("is_popular") == "on",  # 是否熱門景點，checkbox 有勾選時值為 "on"
        "status": form_data.get("status", "active").strip(),  # 狀態，預設 active
        "remove_image": form_data.get("remove_image") == "on",  # 是否要移除目前圖片(編輯時使用)
    }

    errors = []  # 建立錯誤訊息清單

    if not form["name"]:  # 如果名稱是空的
        errors.append("請輸入景點名稱")  # 加入錯誤訊息

    if not form["country_id"]:  # 如果沒選國家
        errors.append("請選擇國家")  # 加入錯誤訊息

    if not form["city_id"]:  # 如果沒選城市
        errors.append("請選擇城市")  # 加入錯誤訊息

    if form["ticket_price"] == "":  # 如果票價欄位是空的
        form["ticket_price"] = 0  # 預設為 0
    else:  # 如果有輸入票價
        try:  # 嘗試轉換成浮點數
            form["ticket_price"] = float(form["ticket_price"])  # 轉換成浮點數
            if form["ticket_price"] < 0:  # 如果是負數
                raise ValueError  # 主動拋出錯誤，統一交給下面的 except 處理
        except ValueError:  # 如果轉換失敗或是負數
            errors.append("票價必須是不小於 0 的數字")  # 加入錯誤訊息
            form["ticket_price"] = 0  # 錯誤時退回預設值 0

    if form["suggested_duration_minutes"] == "":  # 如果建議停留時間是空的
        form["suggested_duration_minutes"] = None  # 設為 None(未填寫)
    else:  # 如果有輸入建議停留時間
        try:  # 嘗試轉換成整數
            form["suggested_duration_minutes"] = int(form["suggested_duration_minutes"])  # 轉換成整數
            if form["suggested_duration_minutes"] < 0:  # 如果是負數
                raise ValueError  # 主動拋出錯誤
        except ValueError:  # 如果轉換失敗或是負數
            errors.append("建議停留時間必須是不小於 0 的整數")  # 加入錯誤訊息
            form["suggested_duration_minutes"] = None  # 錯誤時退回 None

    if form["status"] not in STATUS_CHOICES:  # 如果狀態不在合法清單內(防止表單被竄改)
        form["status"] = "active"  # 強制改回預設值

    return form, errors  # 回傳整理後的表單資料與錯誤清單


def _load_options(cursor):  # 定義內部函式：一次取得新增/編輯表單需要的下拉選單資料
    return {
        "countries": get_countries(cursor),  # 國家清單
        "cities": get_cities(cursor),  # 城市清單
        "categories": get_categories(cursor, "attraction"),  # 景點分類清單
    }


@attractions_bp.route("/")  # 設定景點列表頁路由(網址即為 /content-admin/attractions/)
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def list_attractions():  # 定義景點列表頁函式
    keyword = request.args.get("keyword", "").strip()  # 取得搜尋關鍵字參數
    country_id = request.args.get("country_id", "").strip()  # 取得國家篩選參數
    city_id = request.args.get("city_id", "").strip()  # 取得城市篩選參數
    category_id = request.args.get("category_id", "").strip()  # 取得分類篩選參數
    status = request.args.get("status", "").strip()  # 取得狀態篩選參數
    page = request.args.get("page", "1")  # 取得頁碼參數(字串)
    page = int(page) if page.isdigit() and int(page) > 0 else 1  # 驗證頁碼為正整數，否則預設第 1 頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "content_admin/attractions/list.html",
            attractions=[], countries=[], cities=[], categories=[],
            keyword=keyword, country_id=country_id, city_id=city_id,
            category_id=category_id, status=status, page=1, total_pages=1, total=0
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        conditions = []  # 建立 SQL WHERE 條件清單
        params = []  # 建立對應的參數清單

        if keyword:  # 如果有輸入關鍵字
            conditions.append("(a.name LIKE %s OR a.address LIKE %s)")  # 加入依名稱或地址模糊搜尋的條件
            params.extend([f"%{keyword}%", f"%{keyword}%"])  # 加入對應的兩個參數(名稱、地址各一次)

        if country_id:  # 如果有篩選國家
            conditions.append("a.country_id = %s")  # 加入國家條件
            params.append(country_id)  # 加入對應參數

        if city_id:  # 如果有篩選城市
            conditions.append("a.city_id = %s")  # 加入城市條件
            params.append(city_id)  # 加入對應參數

        if category_id:  # 如果有篩選分類
            conditions.append("a.category_id = %s")  # 加入分類條件
            params.append(category_id)  # 加入對應參數

        if status:  # 如果有篩選狀態
            conditions.append("a.status = %s")  # 加入狀態條件
            params.append(status)  # 加入對應參數

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""  # 把所有條件組成 WHERE 子句，沒有條件就是空字串

        cursor.execute(  # 查詢符合條件的景點總筆數(用來算分頁)
            f"SELECT COUNT(*) AS total FROM attractions a {where_clause}",
            params
        )
        total = cursor.fetchone()["total"]  # 取出總筆數

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)  # 計算總頁數(無條件進位，至少 1 頁)
        page = min(page, total_pages)  # 如果頁碼超過總頁數，修正為最後一頁
        offset = (page - 1) * PAGE_SIZE  # 計算 SQL 要跳過的筆數

        cursor.execute(  # 查詢當頁的景點資料，並關聯分類、國家、城市名稱
            f"""
            SELECT a.attraction_id, a.name, a.address, a.ticket_price,
                   a.suggested_duration_minutes, a.image_path, a.status,
                   a.is_popular, a.ai_verified_at,
                   cat.category_name, co.name AS country_name, ci.name AS city_name
            FROM attractions a
            LEFT JOIN categories cat ON cat.category_id = a.category_id
            JOIN countries co ON co.country_id = a.country_id
            JOIN cities ci ON ci.city_id = a.city_id
            {where_clause}
            ORDER BY a.attraction_id DESC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, offset]  # 加上分頁用的 LIMIT、OFFSET 參數
        )
        attractions = cursor.fetchall()  # 取出當頁景點清單

        options = _load_options(cursor)  # 取得下拉選單需要的國家/城市/分類清單

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染景點列表頁面
        "content_admin/attractions/list.html",
        attractions=attractions,  # 當頁景點清單
        countries=options["countries"],  # 國家下拉選單資料
        cities=options["cities"],  # 城市下拉選單資料
        categories=options["categories"],  # 分類下拉選單資料
        keyword=keyword,  # 搜尋關鍵字(回填搜尋框)
        country_id=country_id,  # 國家篩選值(回填下拉選單)
        city_id=city_id,  # 城市篩選值(回填下拉選單)
        category_id=category_id,  # 分類篩選值(回填下拉選單)
        status=status,  # 狀態篩選值(回填下拉選單)
        page=page,  # 目前頁碼
        total_pages=total_pages,  # 總頁數
        total=total,  # 符合條件的總筆數
    )


@attractions_bp.route("/new", methods=["GET", "POST"])  # 設定新增景點頁路由，GET 顯示表單、POST 送出表單
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def create_attraction():  # 定義新增景點函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("attractions.list_attractions"))  # 導回景點列表頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始處理表單/資料庫操作
        options = _load_options(cursor)  # 先取得下拉選單資料(GET、POST 失敗都要用到)

        if request.method == "POST":  # 如果是表單送出請求
            form, errors = _parse_form(request.form)  # 解析並驗證表單資料

            if not errors:  # 如果基本驗證沒有錯誤，才處理圖片上傳
                try:  # 嘗試儲存上傳圖片
                    image_path = save_uploaded_image(request.files.get("image"), "attractions")  # 儲存圖片，回傳相對路徑或 None
                except ValueError as error:  # 如果圖片格式不符合規定
                    errors.append(str(error))  # 把錯誤訊息加入錯誤清單
                    image_path = None  # 圖片路徑設為 None

            if errors:  # 如果有任何驗證錯誤(欄位或圖片)
                for message in errors:  # 逐一顯示每個錯誤訊息
                    flash(message, "error")
                return render_template(  # 重新顯示新增表單，並保留使用者已輸入的資料
                    "content_admin/attractions/form.html",
                    mode="create", attraction=form, **options
                )

            try:  # 嘗試寫入資料庫
                cursor.execute(  # 執行新增景點的 SQL
                    """
                    INSERT INTO attractions
                    (category_id, name, country_id, city_id, address, opening_hours,
                     ticket_price, suggested_duration_minutes, description, website_url,
                     image_path, is_popular, status, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        form["category_id"], form["name"], form["country_id"], form["city_id"],  # 分類、名稱、國家、城市
                        form["address"], form["opening_hours"], form["ticket_price"],  # 地址、開放時間、票價
                        form["suggested_duration_minutes"], form["description"],  # 建議停留時間、描述
                        form["website_url"], image_path, form["is_popular"], form["status"],  # 網站、圖片路徑、是否熱門、狀態
                        session["user_id"]  # 建立者(目前登入的內容管理員)
                    )
                )
                log_action(  # 把這次新增動作寫入操作紀錄
                    cursor, "create_attraction", "attraction", cursor.lastrowid,
                    f"新增景點：{form['name']}"
                )
                connection.commit()  # 提交交易，正式寫入資料庫(景點資料與操作紀錄一起寫入)
                flash("景點新增成功", "success")  # 顯示成功訊息
            except Exception as error:  # 如果寫入過程發生例外
                connection.rollback()  # 回復交易
                print("新增景點失敗：", error)  # 在伺服器端印出錯誤內容
                flash("新增景點失敗", "error")  # 顯示錯誤提示

            return redirect(url_for("attractions.list_attractions"))  # 不論成功或失敗，都導回景點列表頁

        return render_template(  # GET 請求，顯示空白的新增表單
            "content_admin/attractions/form.html",
            mode="create", attraction=None, **options
        )

    finally:  # 不論上面流程如何結束都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線


@attractions_bp.route("/<int:attraction_id>/edit", methods=["GET", "POST"])  # 設定編輯景點頁路由，網址帶入景點 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def edit_attraction(attraction_id):  # 定義編輯景點函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("attractions.list_attractions"))  # 導回景點列表頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始處理表單/資料庫操作
        options = _load_options(cursor)  # 取得下拉選單資料

        cursor.execute("SELECT * FROM attractions WHERE attraction_id = %s", (attraction_id,))  # 依 ID 查詢景點目前的完整資料
        existing = cursor.fetchone()  # 取得查詢結果

        if existing is None:  # 如果查無此景點(可能已被刪除)
            flash("找不到這筆景點資料", "error")  # 顯示錯誤提示
            return redirect(url_for("attractions.list_attractions"))  # 導回景點列表頁

        if request.method == "POST":  # 如果是表單送出請求
            form, errors = _parse_form(request.form)  # 解析並驗證表單資料
            image_path = existing["image_path"]  # 預設沿用原本的圖片路徑

            new_file = request.files.get("image")  # 取得使用者這次上傳的檔案(可能沒有選檔案)
            if new_file and new_file.filename:  # 如果使用者有選擇新圖片檔案
                try:  # 嘗試儲存新圖片
                    uploaded_path = save_uploaded_image(new_file, "attractions")  # 儲存新圖片，取得新路徑
                    if uploaded_path:  # 如果有成功存到新圖片
                        delete_uploaded_image(existing["image_path"])  # 刪除舊圖片檔案，避免留下孤兒檔案
                        image_path = uploaded_path  # 更新要存進資料庫的圖片路徑
                except ValueError as error:  # 如果新圖片格式不符合規定
                    errors.append(str(error))  # 加入錯誤訊息
            elif form["remove_image"]:  # 如果沒有上傳新圖片，但使用者勾選了「移除目前圖片」
                delete_uploaded_image(existing["image_path"])  # 刪除硬碟上的舊圖片
                image_path = None  # 圖片路徑改為 None

            if errors:  # 如果有任何驗證錯誤
                for message in errors:  # 逐一顯示每個錯誤訊息
                    flash(message, "error")
                form["attraction_id"] = attraction_id  # 把景點 ID 補回表單資料，方便樣板使用
                form["image_path"] = image_path  # 把目前圖片路徑補回表單資料
                return render_template(  # 重新顯示編輯表單
                    "content_admin/attractions/form.html",
                    mode="edit", attraction=form, **options
                )

            try:  # 嘗試更新資料庫
                cursor.execute(  # 執行更新景點的 SQL
                    """
                    UPDATE attractions
                    SET category_id = %s, name = %s, country_id = %s, city_id = %s,
                        address = %s, opening_hours = %s, ticket_price = %s,
                        suggested_duration_minutes = %s, description = %s,
                        website_url = %s, image_path = %s, is_popular = %s, status = %s
                    WHERE attraction_id = %s
                    """,
                    (
                        form["category_id"], form["name"], form["country_id"], form["city_id"],  # 分類、名稱、國家、城市
                        form["address"], form["opening_hours"], form["ticket_price"],  # 地址、開放時間、票價
                        form["suggested_duration_minutes"], form["description"],  # 建議停留時間、描述
                        form["website_url"], image_path, form["is_popular"], form["status"],  # 網站、圖片路徑、是否熱門、狀態
                        attraction_id  # WHERE 條件用的景點 ID
                    )
                )
                log_action(  # 把這次更新動作寫入操作紀錄
                    cursor, "update_attraction", "attraction", attraction_id,
                    f"更新景點：{form['name']}"
                )
                connection.commit()  # 提交交易，正式更新資料庫(景點資料與操作紀錄一起寫入)
                flash("景點資料已更新", "success")  # 顯示成功訊息
            except Exception as error:  # 如果更新過程發生例外
                connection.rollback()  # 回復交易
                print("更新景點失敗：", error)  # 在伺服器端印出錯誤內容
                flash("更新景點失敗", "error")  # 顯示錯誤提示

            return redirect(url_for("attractions.list_attractions"))  # 不論成功或失敗，都導回景點列表頁

        return render_template(  # GET 請求，顯示已填好目前資料的編輯表單
            "content_admin/attractions/form.html",
            mode="edit", attraction=existing, **options
        )

    finally:  # 不論上面流程如何結束都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線


@attractions_bp.route("/<int:attraction_id>/delete", methods=["POST"])  # 設定刪除景點的路由，網址帶入景點 ID，只允許 POST
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def delete_attraction(attraction_id):  # 定義刪除景點函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("attractions.list_attractions"))  # 導回景點列表頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始執行刪除
        cursor.execute(  # 先查出這筆景點目前的名稱與圖片路徑，等下操作紀錄與刪除檔案要用
            "SELECT name, image_path FROM attractions WHERE attraction_id = %s",
            (attraction_id,)
        )
        existing = cursor.fetchone()  # 取得查詢結果(可能為 None)

        cursor.execute("DELETE FROM attractions WHERE attraction_id = %s", (attraction_id,))  # 執行刪除景點資料列

        if existing:  # 如果原本有查到這筆資料(代表確實刪除了某筆景點)
            log_action(  # 把這次刪除動作寫入操作紀錄
                cursor, "delete_attraction", "attraction", attraction_id,
                f"刪除景點：{existing['name']}"
            )

        connection.commit()  # 提交交易，正式從資料庫刪除(景點資料與操作紀錄一起寫入)

        if existing:  # 如果原本有查到這筆資料
            delete_uploaded_image(existing["image_path"])  # 一併刪除硬碟上的圖片檔案

        flash("景點已刪除", "success")  # 顯示成功訊息

    except Exception as error:  # 如果刪除過程發生例外(例如仍有其他資料參照這筆景點)
        connection.rollback()  # 回復交易
        print("刪除景點失敗：", error)  # 在伺服器端印出錯誤內容
        flash("刪除景點失敗，請確認沒有其他資料仍在使用此景點", "error")  # 顯示錯誤提示

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("attractions.list_attractions", **request.args.to_dict()))  # 導回景點列表頁，並保留原本的搜尋/篩選參數


IMPORT_HEADER = [  # 定義景點 CSV 匯入需要的欄位順序，範本下載與匯入解析都用這份清單
    "name", "country", "city", "category", "address", "opening_hours",
    "ticket_price", "suggested_duration_minutes", "description", "website_url",
    "status", "is_popular"
]


@attractions_bp.route("/import/template.csv")  # 設定下載景點匯入範本的路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def download_attraction_template():  # 定義下載匯入範本函式
    example_row = [  # 準備一列範例資料，讓使用者知道每個欄位該怎麼填
        "台北101", "台灣", "台北市", "景點", "台北市信義區信義路五段7號", "09:00-22:00",
        "600", "120", "台北代表性地標與觀景台", "https://www.taipei-101.com.tw",
        "active", "1"
    ]
    return csv_response(  # 組成並回傳 CSV 下載回應
        "attractions_import_template.csv",  # 下載檔名
        IMPORT_HEADER,  # CSV 表頭
        [example_row]  # CSV 範例資料列
    )


@attractions_bp.route("/import", methods=["GET", "POST"])  # 設定景點 CSV 匯入頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def import_attractions():  # 定義景點 CSV 匯入函式
    if request.method == "GET":  # 如果是進頁面(還沒上傳檔案)
        return render_template("content_admin/attractions/import.html")  # 顯示上傳表單頁面

    uploaded_file = request.files.get("csv_file")  # 取得使用者上傳的檔案

    if not uploaded_file or not uploaded_file.filename:  # 如果沒有選擇檔案
        flash("請選擇要匯入的 CSV 檔案", "error")  # 顯示錯誤提示
        return redirect(url_for("attractions.import_attractions"))  # 導回匯入頁面

    if not uploaded_file.filename.lower().endswith(".csv"):  # 如果副檔名不是 .csv
        flash("請上傳 CSV 格式的檔案", "error")  # 顯示錯誤提示
        return redirect(url_for("attractions.import_attractions"))  # 導回匯入頁面

    try:  # 嘗試把上傳內容解碼成文字
        content = uploaded_file.read().decode("utf-8-sig")  # 讀取檔案內容並用 utf-8-sig 解碼(可自動去除 BOM)
    except UnicodeDecodeError:  # 如果不是合法的 UTF-8 編碼
        flash("檔案編碼有誤，請使用 UTF-8 編碼的 CSV 檔案", "error")  # 顯示錯誤提示
        return redirect(url_for("attractions.import_attractions"))  # 導回匯入頁面

    reader = csv.DictReader(io.StringIO(content))  # 用 CSV 讀取器把內容解析成一列一列的字典

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("attractions.import_attractions"))  # 導回匯入頁面

    cursor = connection.cursor()  # 建立一般游標(不需要字典格式，方便搭配 get_or_create 系列函式)
    results = []  # 建立每一列的匯入結果清單，元素為 (列號, 名稱, 是否成功, 說明)
    success_count = 0  # 建立成功筆數計數器

    try:  # 開始逐列處理匯入資料
        for row_number, row in enumerate(reader, start=2):  # 從第 2 列開始編號(第 1 列是表頭)
            name = (row.get("name") or "").strip()  # 取得景點名稱
            country_name = (row.get("country") or "").strip()  # 取得國家名稱
            city_name = (row.get("city") or "").strip()  # 取得城市名稱

            if not name or not country_name or not city_name:  # 如果名稱、國家、城市任一為空
                results.append((row_number, name or "(無名稱)", False, "名稱、國家、城市為必填欄位"))  # 記錄失敗原因
                continue  # 跳過這一列，繼續處理下一列

            try:  # 嘗試把票價轉成數字
                ticket_price = float(row.get("ticket_price") or 0)  # 沒填就當 0
                if ticket_price < 0:  # 如果是負數
                    ticket_price = 0  # 修正為 0
            except ValueError:  # 如果轉換失敗
                ticket_price = 0  # 修正為 0

            duration_raw = (row.get("suggested_duration_minutes") or "").strip()  # 取得建議停留時間文字
            try:  # 嘗試把建議停留時間轉成整數
                suggested_duration = int(duration_raw) if duration_raw else None  # 有填才轉換，沒填是 None
                if suggested_duration is not None and suggested_duration < 0:  # 如果是負數
                    suggested_duration = None  # 修正為 None
            except ValueError:  # 如果轉換失敗
                suggested_duration = None  # 修正為 None

            status = (row.get("status") or "active").strip()  # 取得狀態，預設 active
            if status not in STATUS_CHOICES:  # 如果不是合法狀態
                status = "active"  # 修正為預設值

            is_popular_raw = (row.get("is_popular") or "").strip().lower()  # 取得是否熱門的原始文字並轉小寫
            is_popular = is_popular_raw in ("1", "true", "yes", "是")  # 常見的「是」寫法都視為勾選

            try:  # 嘗試處理這一列的國家/城市/分類並寫入資料庫
                country_id = get_or_create_country(cursor, country_name)  # 取得(或新增)國家 ID
                city_id = get_or_create_city(cursor, country_id, city_name)  # 取得(或新增)城市 ID
                category_name = (row.get("category") or "").strip()  # 取得分類名稱
                category_id = get_or_create_category(cursor, "attraction", category_name)  # 取得(或新增)分類 ID

                cursor.execute(  # 執行新增景點的 SQL
                    """
                    INSERT INTO attractions
                    (category_id, name, country_id, city_id, address, opening_hours,
                     ticket_price, suggested_duration_minutes, description, website_url,
                     is_popular, status, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        category_id, name, country_id, city_id,  # 分類、名稱、國家、城市
                        (row.get("address") or "").strip() or None,  # 地址
                        (row.get("opening_hours") or "").strip() or None,  # 開放時間
                        ticket_price, suggested_duration,  # 票價、建議停留時間
                        (row.get("description") or "").strip() or None,  # 描述
                        (row.get("website_url") or "").strip() or None,  # 官方網站
                        is_popular, status, session["user_id"]  # 是否熱門、狀態、建立者
                    )
                )
                success_count += 1  # 成功筆數加一
                results.append((row_number, name, True, ""))  # 記錄這一列匯入成功
            except Exception as error:  # 如果這一列處理過程發生例外(不中斷整批匯入)
                results.append((row_number, name, False, str(error)))  # 記錄這一列失敗與原因

        log_action(  # 把這次批次匯入寫入操作紀錄
            cursor, "import_attractions", "attraction", None,
            f"CSV 匯入景點，成功 {success_count} 筆，失敗 {len(results) - success_count} 筆"
        )
        connection.commit()  # 提交交易，正式寫入這次匯入成功的所有景點與操作紀錄

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染匯入結果頁面
        "content_admin/attractions/import_result.html",
        results=results,  # 每一列的匯入結果
        success_count=success_count,  # 成功筆數
        fail_count=len(results) - success_count,  # 失敗筆數
    )
