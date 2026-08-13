from flask import Blueprint, flash, redirect, render_template, request, url_for

from auth import login_required
from db import get_db_connection

locations_bp = Blueprint("locations", __name__, url_prefix="/content-admin/locations")


@locations_bp.route("/")
@login_required("content_admin")
def manage_locations():
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template("content_admin/locations.html", countries=[], cities=[])

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT co.country_id, co.name,
                   COUNT(DISTINCT ci.city_id) AS city_count
            FROM countries co
            LEFT JOIN cities ci ON ci.country_id = co.country_id
            GROUP BY co.country_id, co.name
            ORDER BY co.name
        """)
        countries = cursor.fetchall()

        cursor.execute("""
            SELECT ci.city_id, ci.name, ci.country_id, co.name AS country_name
            FROM cities ci
            JOIN countries co ON co.country_id = ci.country_id
            ORDER BY co.name, ci.name
        """)
        cities = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "content_admin/locations.html",
        countries=countries,
        cities=cities
    )


@locations_bp.route("/countries/new", methods=["POST"])
@login_required("content_admin")
def create_country():
    name = request.form.get("name", "").strip()

    if not name:
        flash("請輸入國家名稱", "error")
        return redirect(url_for("locations.manage_locations"))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("locations.manage_locations"))

    cursor = connection.cursor()

    try:
        cursor.execute("INSERT INTO countries(name) VALUES (%s)", (name,))
        connection.commit()
        flash("國家新增成功", "success")
    except Exception as error:
        connection.rollback()
        print("新增國家失敗：", error)
        flash("新增國家失敗，名稱可能已存在", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("locations.manage_locations"))


@locations_bp.route("/countries/<int:country_id>/edit", methods=["POST"])
@login_required("content_admin")
def edit_country(country_id):
    name = request.form.get("name", "").strip()

    if not name:
        flash("請輸入國家名稱", "error")
        return redirect(url_for("locations.manage_locations"))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("locations.manage_locations"))

    cursor = connection.cursor()

    try:
        cursor.execute(
            "UPDATE countries SET name = %s WHERE country_id = %s",
            (name, country_id)
        )
        connection.commit()
        flash("國家名稱已更新", "success")
    except Exception as error:
        connection.rollback()
        print("更新國家失敗：", error)
        flash("更新國家失敗，名稱可能已存在", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("locations.manage_locations"))


@locations_bp.route("/countries/<int:country_id>/delete", methods=["POST"])
@login_required("content_admin")
def delete_country(country_id):
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("locations.manage_locations"))

    cursor = connection.cursor()

    try:
        cursor.execute("DELETE FROM countries WHERE country_id = %s", (country_id,))
        connection.commit()
        flash("國家已刪除", "success")
    except Exception as error:
        connection.rollback()
        print("刪除國家失敗：", error)
        flash("刪除失敗，此國家底下仍有城市，請先刪除相關城市", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("locations.manage_locations"))


@locations_bp.route("/cities/new", methods=["POST"])
@login_required("content_admin")
def create_city():
    country_id = request.form.get("country_id", "").strip()
    name = request.form.get("name", "").strip()

    if not country_id or not name:
        flash("請選擇國家並輸入城市名稱", "error")
        return redirect(url_for("locations.manage_locations"))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("locations.manage_locations"))

    cursor = connection.cursor()

    try:
        cursor.execute(
            "INSERT INTO cities(country_id, name) VALUES (%s, %s)",
            (country_id, name)
        )
        connection.commit()
        flash("城市新增成功", "success")
    except Exception as error:
        connection.rollback()
        print("新增城市失敗：", error)
        flash("新增城市失敗，此國家下可能已有相同名稱的城市", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("locations.manage_locations"))


@locations_bp.route("/cities/<int:city_id>/edit", methods=["POST"])
@login_required("content_admin")
def edit_city(city_id):
    country_id = request.form.get("country_id", "").strip()
    name = request.form.get("name", "").strip()

    if not country_id or not name:
        flash("請選擇國家並輸入城市名稱", "error")
        return redirect(url_for("locations.manage_locations"))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("locations.manage_locations"))

    cursor = connection.cursor()

    try:
        cursor.execute(
            "UPDATE cities SET country_id = %s, name = %s WHERE city_id = %s",
            (country_id, name, city_id)
        )
        connection.commit()
        flash("城市資料已更新", "success")
    except Exception as error:
        connection.rollback()
        print("更新城市失敗：", error)
        flash("更新城市失敗，此國家下可能已有相同名稱的城市", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("locations.manage_locations"))


@locations_bp.route("/cities/<int:city_id>/delete", methods=["POST"])
@login_required("content_admin")
def delete_city(city_id):
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("locations.manage_locations"))

    cursor = connection.cursor()

    try:
        cursor.execute("DELETE FROM cities WHERE city_id = %s", (city_id,))
        connection.commit()
        flash("城市已刪除", "success")
    except Exception as error:
        connection.rollback()
        print("刪除城市失敗：", error)
        flash("刪除失敗，此城市仍有景點、餐廳或住宿使用中", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("locations.manage_locations"))
