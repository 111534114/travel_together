import csv
import io

from flask import Blueprint, Response, flash, redirect, url_for

from auth import login_required
from db import get_db_connection

reports_bp = Blueprint("reports", __name__, url_prefix="/content-admin/reports")


def _csv_response(filename, header, rows):
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@reports_bp.route("/export/attractions.csv")
@login_required("content_admin")
def export_attractions():
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("content_admin_home"))

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT name, country, city, favorite_count, itinerary_count
            FROM vw_popular_attractions
            ORDER BY (favorite_count + itinerary_count) DESC, name
        """)
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    data = [
        (r["name"], r["country"], r["city"], r["favorite_count"], r["itinerary_count"])
        for r in rows
    ]

    return _csv_response(
        "attractions_report.csv",
        ["景點名稱", "國家", "城市", "收藏次數", "被排入行程次數"],
        data
    )


@reports_bp.route("/export/restaurants.csv")
@login_required("content_admin")
def export_restaurants():
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("content_admin_home"))

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT r.name, co.name AS country, ci.name AS city,
                   COUNT(i.itinerary_id) AS itinerary_count
            FROM restaurants r
            JOIN countries co ON co.country_id = r.country_id
            JOIN cities ci ON ci.city_id = r.city_id
            LEFT JOIN itineraries i ON i.restaurant_id = r.restaurant_id
            GROUP BY r.restaurant_id, r.name, co.name, ci.name
            ORDER BY itinerary_count DESC, r.name
        """)
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    data = [(r["name"], r["country"], r["city"], r["itinerary_count"]) for r in rows]

    return _csv_response(
        "restaurants_report.csv",
        ["餐廳名稱", "國家", "城市", "被排入行程次數"],
        data
    )


@reports_bp.route("/export/accommodations.csv")
@login_required("content_admin")
def export_accommodations():
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("content_admin_home"))

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT ac.name, co.name AS country, ci.name AS city,
                   COUNT(i.itinerary_id) AS itinerary_count
            FROM accommodations ac
            JOIN countries co ON co.country_id = ac.country_id
            JOIN cities ci ON ci.city_id = ac.city_id
            LEFT JOIN itineraries i ON i.accommodation_id = ac.accommodation_id
            GROUP BY ac.accommodation_id, ac.name, co.name, ci.name
            ORDER BY itinerary_count DESC, ac.name
        """)
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    data = [(r["name"], r["country"], r["city"], r["itinerary_count"]) for r in rows]

    return _csv_response(
        "accommodations_report.csv",
        ["住宿名稱", "國家", "城市", "被排入行程次數"],
        data
    )
