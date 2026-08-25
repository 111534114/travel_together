import csv  # 匯入 csv 模組，用來產生 CSV 檔案內容
import io  # 匯入 io 模組，用來在記憶體中組出檔案內容(不用真的寫檔案到硬碟)

from flask import Blueprint, Response, flash, redirect, url_for  # 匯入 Flask 藍圖、自訂回應、常用功能

from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式

reports_bp = Blueprint("reports", __name__, url_prefix="/content-admin/reports")  # 建立統計報表藍圖，網址前綴 /content-admin/reports


def _csv_response(filename, header, rows):  # 定義內部函式：把表頭與資料列組成可下載的 CSV 回應
    buffer = io.StringIO()  # 建立一個記憶體中的文字緩衝區
    buffer.write("﻿")  # 寫入 UTF-8 BOM，讓 Excel 開啟 CSV 時能正確辨識中文編碼
    writer = csv.writer(buffer)  # 建立 CSV 寫入器，綁定到這個緩衝區
    writer.writerow(header)  # 寫入表頭那一列
    writer.writerows(rows)  # 寫入所有資料列

    return Response(  # 組成 Flask 回應物件
        buffer.getvalue(),  # 回應內容為緩衝區裡累積的所有文字
        mimetype="text/csv",  # 設定回應的內容類型為 CSV
        headers={"Content-Disposition": f"attachment; filename={filename}"}  # 設定為附件下載，並指定檔名
    )


@reports_bp.route("/export/attractions.csv")  # 設定匯出景點統計 CSV 的路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def export_attractions():  # 定義匯出景點統計函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("content_admin_home"))  # 導回內容管理員首頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        cursor.execute("""
            SELECT name, country, city, favorite_count, itinerary_count
            FROM vw_popular_attractions
            ORDER BY (favorite_count + itinerary_count) DESC, name
        """)  # 從熱門景點檢視表查詢，依收藏數+行程使用數排序
        rows = cursor.fetchall()  # 取出查詢結果
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    data = [  # 把查詢結果(字典格式)轉成一列一列的 tuple，符合 CSV 寫入格式
        (r["name"], r["country"], r["city"], r["favorite_count"], r["itinerary_count"])
        for r in rows
    ]

    return _csv_response(  # 組成並回傳 CSV 下載回應
        "attractions_report.csv",  # 下載檔名
        ["景點名稱", "國家", "城市", "收藏次數", "被排入行程次數"],  # CSV 表頭
        data  # CSV 資料列
    )


@reports_bp.route("/export/restaurants.csv")  # 設定匯出餐廳統計 CSV 的路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def export_restaurants():  # 定義匯出餐廳統計函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("content_admin_home"))  # 導回內容管理員首頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        cursor.execute("""
            SELECT r.name, co.name AS country, ci.name AS city,
                   COUNT(i.itinerary_id) AS itinerary_count
            FROM restaurants r
            JOIN countries co ON co.country_id = r.country_id
            JOIN cities ci ON ci.city_id = r.city_id
            LEFT JOIN itineraries i ON i.restaurant_id = r.restaurant_id
            GROUP BY r.restaurant_id, r.name, co.name, ci.name
            ORDER BY itinerary_count DESC, r.name
        """)  # 查詢每間餐廳被排入行程的次數，依使用次數排序
        rows = cursor.fetchall()  # 取出查詢結果
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    data = [(r["name"], r["country"], r["city"], r["itinerary_count"]) for r in rows]  # 把查詢結果轉成 CSV 用的 tuple 清單

    return _csv_response(  # 組成並回傳 CSV 下載回應
        "restaurants_report.csv",  # 下載檔名
        ["餐廳名稱", "國家", "城市", "被排入行程次數"],  # CSV 表頭
        data  # CSV 資料列
    )


@reports_bp.route("/export/accommodations.csv")  # 設定匯出住宿統計 CSV 的路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def export_accommodations():  # 定義匯出住宿統計函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("content_admin_home"))  # 導回內容管理員首頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        cursor.execute("""
            SELECT ac.name, co.name AS country, ci.name AS city,
                   COUNT(i.itinerary_id) AS itinerary_count
            FROM accommodations ac
            JOIN countries co ON co.country_id = ac.country_id
            JOIN cities ci ON ci.city_id = ac.city_id
            LEFT JOIN itineraries i ON i.accommodation_id = ac.accommodation_id
            GROUP BY ac.accommodation_id, ac.name, co.name, ci.name
            ORDER BY itinerary_count DESC, ac.name
        """)  # 查詢每筆住宿被排入行程的次數，依使用次數排序
        rows = cursor.fetchall()  # 取出查詢結果
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    data = [(r["name"], r["country"], r["city"], r["itinerary_count"]) for r in rows]  # 把查詢結果轉成 CSV 用的 tuple 清單

    return _csv_response(  # 組成並回傳 CSV 下載回應
        "accommodations_report.csv",  # 下載檔名
        ["住宿名稱", "國家", "城市", "被排入行程次數"],  # CSV 表頭
        data  # CSV 資料列
    )
