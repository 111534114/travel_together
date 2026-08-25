from flask import Blueprint, flash, redirect, render_template, request, session, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式

categories_bp = Blueprint("categories", __name__, url_prefix="/content-admin/categories")  # 建立分類管理藍圖，網址前綴 /content-admin/categories

ALLOWED_TYPES = ("attraction", "restaurant", "accommodation")  # 定義內容管理員可以管理的分類類型(不含 trip、expense)

TYPE_LABELS = {  # 定義分類類型對應的中文顯示名稱
    "attraction": "景點類別",
    "restaurant": "餐廳類別",
    "accommodation": "住宿類別",
}


@categories_bp.route("/")  # 設定分類管理頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def manage_categories():  # 定義分類管理頁函式
    category_type = request.args.get("type", "attraction").strip()  # 取得網址上的分類類型參數，預設景點

    if category_type not in ALLOWED_TYPES:  # 如果類型不在允許清單內(防止網址被亂改)
        category_type = "attraction"  # 強制改回預設值

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "content_admin/categories.html",
            categories=[], category_type=category_type,
            type_labels=TYPE_LABELS, allowed_types=ALLOWED_TYPES
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        cursor.execute(  # 依分類類型查詢該類型的所有分類
            """
            SELECT category_id, category_name, description, status
            FROM categories
            WHERE category_type = %s
            ORDER BY category_name
            """,
            (category_type,)
        )
        categories = cursor.fetchall()  # 取出分類清單

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染分類管理頁面
        "content_admin/categories.html",
        categories=categories,  # 分類清單
        category_type=category_type,  # 目前選擇的分類類型
        type_labels=TYPE_LABELS,  # 類型對應的中文名稱
        allowed_types=ALLOWED_TYPES  # 允許的類型清單(用來畫分頁籤)
    )


@categories_bp.route("/new", methods=["POST"])  # 設定新增分類的路由，只允許 POST
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def create_category():  # 定義新增分類函式
    category_type = request.form.get("category_type", "").strip()  # 取得表單傳來的分類類型
    name = request.form.get("category_name", "").strip()  # 取得表單輸入的分類名稱
    description = request.form.get("description", "").strip() or None  # 取得說明文字，空字串轉成 None

    if category_type not in ALLOWED_TYPES:  # 如果分類類型不在允許清單內(防止竄改表單去動到 trip/expense 分類)
        flash("類別類型錯誤", "error")  # 顯示錯誤提示
        return redirect(url_for("categories.manage_categories"))  # 導回分類管理頁(預設景點分頁)

    if not name:  # 如果分類名稱是空的
        flash("請輸入類別名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("categories.manage_categories", type=category_type))  # 導回原本的分類分頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("categories.manage_categories", type=category_type))  # 導回原本的分類分頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試新增資料
        cursor.execute(  # 執行新增分類的 SQL
            """
            INSERT INTO categories(category_type, category_name, description, created_by)
            VALUES (%s, %s, %s, %s)
            """,
            (category_type, name, description, session["user_id"])
        )
        log_action(  # 把這次新增動作寫入操作紀錄
            cursor, "create_category", "category", cursor.lastrowid,
            f"新增{TYPE_LABELS[category_type]}：{name}"
        )
        connection.commit()  # 提交交易(分類資料與操作紀錄一起寫入)
        flash("類別新增成功", "success")  # 顯示成功訊息
    except Exception as error:  # 如果新增過程發生例外(例如同類型下名稱重複)
        connection.rollback()  # 回復交易
        print("新增類別失敗：", error)  # 在伺服器端印出錯誤內容
        flash("新增類別失敗，名稱可能已存在", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("categories.manage_categories", type=category_type))  # 導回原本的分類分頁


@categories_bp.route("/<int:category_id>/edit", methods=["POST"])  # 設定編輯分類的路由，網址帶入分類 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def edit_category(category_id):  # 定義編輯分類函式
    category_type = request.form.get("category_type", "").strip()  # 取得表單傳來的分類類型
    name = request.form.get("category_name", "").strip()  # 取得表單輸入的分類名稱
    description = request.form.get("description", "").strip() or None  # 取得說明文字，空字串轉成 None
    status = request.form.get("status", "active").strip()  # 取得狀態，預設 active

    if category_type not in ALLOWED_TYPES:  # 如果分類類型不在允許清單內
        flash("類別類型錯誤", "error")  # 顯示錯誤提示
        return redirect(url_for("categories.manage_categories"))  # 導回分類管理頁

    if not name:  # 如果分類名稱是空的
        flash("請輸入類別名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("categories.manage_categories", type=category_type))  # 導回原本的分類分頁

    if status not in ("active", "hidden"):  # 如果狀態不在合法清單內(防止表單被竄改)
        status = "active"  # 強制改回預設值

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("categories.manage_categories", type=category_type))  # 導回原本的分類分頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
        cursor.execute(  # 執行更新分類的 SQL，同時用 category_type 當條件避免跨類型誤改
            """
            UPDATE categories
            SET category_name = %s, description = %s, status = %s
            WHERE category_id = %s AND category_type = %s
            """,
            (name, description, status, category_id, category_type)
        )
        log_action(  # 把這次更新動作寫入操作紀錄
            cursor, "update_category", "category", category_id,
            f"更新{TYPE_LABELS[category_type]}：{name}"
        )
        connection.commit()  # 提交交易(分類資料與操作紀錄一起寫入)
        flash("類別已更新", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外(例如名稱重複)
        connection.rollback()  # 回復交易
        print("更新類別失敗：", error)  # 在伺服器端印出錯誤內容
        flash("更新類別失敗，名稱可能已存在", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("categories.manage_categories", type=category_type))  # 導回原本的分類分頁


@categories_bp.route("/<int:category_id>/delete", methods=["POST"])  # 設定刪除分類的路由，網址帶入分類 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def delete_category(category_id):  # 定義刪除分類函式
    category_type = request.form.get("category_type", "").strip()  # 取得表單傳來的分類類型

    if category_type not in ALLOWED_TYPES:  # 如果分類類型不在允許清單內
        flash("類別類型錯誤", "error")  # 顯示錯誤提示
        return redirect(url_for("categories.manage_categories"))  # 導回分類管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("categories.manage_categories", type=category_type))  # 導回原本的分類分頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試刪除資料
        cursor.execute(  # 先查出分類名稱，等下寫操作紀錄要用
            "SELECT category_name FROM categories WHERE category_id = %s AND category_type = %s",
            (category_id, category_type)
        )
        existing = cursor.fetchone()  # 取得查詢結果(可能為 None)

        cursor.execute(  # 執行刪除分類的 SQL，同時用 category_type 當條件避免跨類型誤刪
            "DELETE FROM categories WHERE category_id = %s AND category_type = %s",
            (category_id, category_type)
        )

        if existing:  # 如果原本有查到這個分類(代表確實刪除了)
            log_action(  # 把這次刪除動作寫入操作紀錄
                cursor, "delete_category", "category", category_id,
                f"刪除{TYPE_LABELS[category_type]}：{existing[0]}"
            )

        connection.commit()  # 提交交易(分類資料與操作紀錄一起寫入)
        flash("類別已刪除", "success")  # 顯示成功訊息
    except Exception as error:  # 如果刪除過程發生例外
        connection.rollback()  # 回復交易
        print("刪除類別失敗：", error)  # 在伺服器端印出錯誤內容
        flash("刪除類別失敗", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("categories.manage_categories", type=category_type))  # 導回原本的分類分頁
