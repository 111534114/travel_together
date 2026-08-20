from flask import Blueprint, flash, redirect, render_template, request, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式

locations_bp = Blueprint("locations", __name__, url_prefix="/content-admin/locations")  # 建立國家/城市管理藍圖，網址前綴 /content-admin/locations


@locations_bp.route("/")  # 設定國家與城市管理頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def manage_locations():  # 定義國家與城市管理頁函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template("content_admin/locations.html", countries=[], cities=[])  # 回傳空清單頁面

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        cursor.execute("""
            SELECT co.country_id, co.name,
                   COUNT(DISTINCT ci.city_id) AS city_count
            FROM countries co
            LEFT JOIN cities ci ON ci.country_id = co.country_id
            GROUP BY co.country_id, co.name
            ORDER BY co.name
        """)  # 查詢所有國家，並統計每個國家底下有幾個城市
        countries = cursor.fetchall()  # 取出國家清單

        cursor.execute("""
            SELECT ci.city_id, ci.name, ci.country_id, co.name AS country_name
            FROM cities ci
            JOIN countries co ON co.country_id = ci.country_id
            ORDER BY co.name, ci.name
        """)  # 查詢所有城市，並關聯出所屬國家名稱，依國家再依城市名稱排序
        cities = cursor.fetchall()  # 取出城市清單

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染國家與城市管理頁面
        "content_admin/locations.html",
        countries=countries,  # 國家清單
        cities=cities  # 城市清單
    )


@locations_bp.route("/countries/new", methods=["POST"])  # 設定新增國家的路由，只允許 POST
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def create_country():  # 定義新增國家函式
    name = request.form.get("name", "").strip()  # 取得表單輸入的國家名稱

    if not name:  # 如果名稱是空的
        flash("請輸入國家名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試新增資料
        cursor.execute("INSERT INTO countries(name) VALUES (%s)", (name,))  # 執行新增國家的 SQL
        log_action(cursor, "create_country", "country", cursor.lastrowid, f"新增國家：{name}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(國家資料與操作紀錄一起寫入)
        flash("國家新增成功", "success")  # 顯示成功訊息
    except Exception as error:  # 如果新增過程發生例外(例如名稱重複)
        connection.rollback()  # 回復交易
        print("新增國家失敗：", error)  # 在伺服器端印出錯誤內容
        flash("新增國家失敗，名稱可能已存在", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/countries/<int:country_id>/edit", methods=["POST"])  # 設定編輯國家名稱的路由，網址帶入國家 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def edit_country(country_id):  # 定義編輯國家函式
    name = request.form.get("name", "").strip()  # 取得表單輸入的新國家名稱

    if not name:  # 如果名稱是空的
        flash("請輸入國家名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
        cursor.execute(  # 執行更新國家名稱的 SQL
            "UPDATE countries SET name = %s WHERE country_id = %s",
            (name, country_id)
        )
        log_action(cursor, "update_country", "country", country_id, f"更新國家名稱為：{name}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(國家資料與操作紀錄一起寫入)
        flash("國家名稱已更新", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外(例如名稱重複)
        connection.rollback()  # 回復交易
        print("更新國家失敗：", error)  # 在伺服器端印出錯誤內容
        flash("更新國家失敗，名稱可能已存在", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/countries/<int:country_id>/delete", methods=["POST"])  # 設定刪除國家的路由，網址帶入國家 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def delete_country(country_id):  # 定義刪除國家函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試刪除資料
        cursor.execute("SELECT name FROM countries WHERE country_id = %s", (country_id,))  # 先查出國家名稱，等下寫操作紀錄要用
        existing = cursor.fetchone()  # 取得查詢結果(可能為 None)

        cursor.execute("DELETE FROM countries WHERE country_id = %s", (country_id,))  # 執行刪除國家的 SQL

        if existing:  # 如果原本有查到這個國家(代表確實刪除了)
            log_action(cursor, "delete_country", "country", country_id, f"刪除國家：{existing[0]}")  # 寫入操作紀錄

        connection.commit()  # 提交交易(國家資料與操作紀錄一起寫入)
        flash("國家已刪除", "success")  # 顯示成功訊息
    except Exception as error:  # 如果刪除過程發生例外(例如底下還有城市，外鍵擋住)
        connection.rollback()  # 回復交易
        print("刪除國家失敗：", error)  # 在伺服器端印出錯誤內容
        flash("刪除失敗，此國家底下仍有城市，請先刪除相關城市", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/cities/new", methods=["POST"])  # 設定新增城市的路由，只允許 POST
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def create_city():  # 定義新增城市函式
    country_id = request.form.get("country_id", "").strip()  # 取得表單選擇的國家 ID
    name = request.form.get("name", "").strip()  # 取得表單輸入的城市名稱

    if not country_id or not name:  # 如果國家沒選或名稱是空的
        flash("請選擇國家並輸入城市名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試新增資料
        cursor.execute(  # 執行新增城市的 SQL
            "INSERT INTO cities(country_id, name) VALUES (%s, %s)",
            (country_id, name)
        )
        log_action(cursor, "create_city", "city", cursor.lastrowid, f"新增城市：{name}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(城市資料與操作紀錄一起寫入)
        flash("城市新增成功", "success")  # 顯示成功訊息
    except Exception as error:  # 如果新增過程發生例外(例如同一國家下城市名稱重複)
        connection.rollback()  # 回復交易
        print("新增城市失敗：", error)  # 在伺服器端印出錯誤內容
        flash("新增城市失敗，此國家下可能已有相同名稱的城市", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/cities/<int:city_id>/edit", methods=["POST"])  # 設定編輯城市的路由，網址帶入城市 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def edit_city(city_id):  # 定義編輯城市函式
    country_id = request.form.get("country_id", "").strip()  # 取得表單選擇的所屬國家 ID
    name = request.form.get("name", "").strip()  # 取得表單輸入的城市名稱

    if not country_id or not name:  # 如果國家沒選或名稱是空的
        flash("請選擇國家並輸入城市名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
        cursor.execute(  # 執行更新城市資料的 SQL(可同時更換所屬國家)
            "UPDATE cities SET country_id = %s, name = %s WHERE city_id = %s",
            (country_id, name, city_id)
        )
        log_action(cursor, "update_city", "city", city_id, f"更新城市資料為：{name}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(城市資料與操作紀錄一起寫入)
        flash("城市資料已更新", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外(例如名稱重複)
        connection.rollback()  # 回復交易
        print("更新城市失敗：", error)  # 在伺服器端印出錯誤內容
        flash("更新城市失敗，此國家下可能已有相同名稱的城市", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/cities/<int:city_id>/delete", methods=["POST"])  # 設定刪除城市的路由，網址帶入城市 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def delete_city(city_id):  # 定義刪除城市函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試刪除資料
        cursor.execute("SELECT name FROM cities WHERE city_id = %s", (city_id,))  # 先查出城市名稱，等下寫操作紀錄要用
        existing = cursor.fetchone()  # 取得查詢結果(可能為 None)

        cursor.execute("DELETE FROM cities WHERE city_id = %s", (city_id,))  # 執行刪除城市的 SQL

        if existing:  # 如果原本有查到這個城市(代表確實刪除了)
            log_action(cursor, "delete_city", "city", city_id, f"刪除城市：{existing[0]}")  # 寫入操作紀錄

        connection.commit()  # 提交交易(城市資料與操作紀錄一起寫入)
        flash("城市已刪除", "success")  # 顯示成功訊息
    except Exception as error:  # 如果刪除過程發生例外(例如仍有景點/餐廳/住宿使用這個城市，外鍵擋住)
        connection.rollback()  # 回復交易
        print("刪除城市失敗：", error)  # 在伺服器端印出錯誤內容
        flash("刪除失敗，此城市仍有景點、餐廳或住宿使用中", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁
