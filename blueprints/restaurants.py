from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import login_required
from db import get_db_connection
from utils import (
    delete_uploaded_image,
    get_categories,
    get_cities,
    get_countries,
    save_uploaded_image,
)

restaurants_bp = Blueprint("restaurants", __name__, url_prefix="/content-admin/restaurants")

PAGE_SIZE = 20

STATUS_CHOICES = ("active", "hidden", "pending")
PRICE_LEVEL_CHOICES = ("low", "medium", "high", "luxury")


def _parse_form(form_data):
    form = {
        "category_id": form_data.get("category_id", "").strip() or None,
        "name": form_data.get("name", "").strip(),
        "country_id": form_data.get("country_id", "").strip(),
        "city_id": form_data.get("city_id", "").strip(),
        "address": form_data.get("address", "").strip() or None,
        "cuisine_type": form_data.get("cuisine_type", "").strip() or None,
        "price_level": form_data.get("price_level", "medium").strip(),
        "opening_hours": form_data.get("opening_hours", "").strip() or None,
        "description": form_data.get("description", "").strip() or None,
        "website_url": form_data.get("website_url", "").strip() or None,
        "status": form_data.get("status", "active").strip(),
        "remove_image": form_data.get("remove_image") == "on",
    }

    errors = []

    if not form["name"]:
        errors.append("請輸入餐廳名稱")

    if not form["country_id"]:
        errors.append("請選擇國家")

    if not form["city_id"]:
        errors.append("請選擇城市")

    if form["price_level"] not in PRICE_LEVEL_CHOICES:
        form["price_level"] = "medium"

    if form["status"] not in STATUS_CHOICES:
        form["status"] = "active"

    return form, errors


def _load_options(cursor):
    return {
        "countries": get_countries(cursor),
        "cities": get_cities(cursor),
        "categories": get_categories(cursor, "restaurant"),
    }


@restaurants_bp.route("/")
@login_required("content_admin")
def list_restaurants():
    keyword = request.args.get("keyword", "").strip()
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    category_id = request.args.get("category_id", "").strip()
    status = request.args.get("status", "").strip()
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() and int(page) > 0 else 1

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template(
            "content_admin/restaurants/list.html",
            restaurants=[], countries=[], cities=[], categories=[],
            keyword=keyword, country_id=country_id, city_id=city_id,
            category_id=category_id, status=status, page=1, total_pages=1, total=0
        )

    cursor = connection.cursor(dictionary=True)

    try:
        conditions = []
        params = []

        if keyword:
            conditions.append("(r.name LIKE %s OR r.address LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        if country_id:
            conditions.append("r.country_id = %s")
            params.append(country_id)

        if city_id:
            conditions.append("r.city_id = %s")
            params.append(city_id)

        if category_id:
            conditions.append("r.category_id = %s")
            params.append(category_id)

        if status:
            conditions.append("r.status = %s")
            params.append(status)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor.execute(
            f"SELECT COUNT(*) AS total FROM restaurants r {where_clause}",
            params
        )
        total = cursor.fetchone()["total"]

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        offset = (page - 1) * PAGE_SIZE

        cursor.execute(
            f"""
            SELECT r.restaurant_id, r.name, r.address, r.cuisine_type, r.price_level,
                   r.image_path, r.status, r.ai_verified_at,
                   cat.category_name, co.name AS country_name, ci.name AS city_name
            FROM restaurants r
            LEFT JOIN categories cat ON cat.category_id = r.category_id
            JOIN countries co ON co.country_id = r.country_id
            JOIN cities ci ON ci.city_id = r.city_id
            {where_clause}
            ORDER BY r.restaurant_id DESC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, offset]
        )
        restaurants = cursor.fetchall()

        options = _load_options(cursor)

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "content_admin/restaurants/list.html",
        restaurants=restaurants,
        countries=options["countries"],
        cities=options["cities"],
        categories=options["categories"],
        keyword=keyword,
        country_id=country_id,
        city_id=city_id,
        category_id=category_id,
        status=status,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@restaurants_bp.route("/new", methods=["GET", "POST"])
@login_required("content_admin")
def create_restaurant():
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("restaurants.list_restaurants"))

    cursor = connection.cursor(dictionary=True)

    try:
        options = _load_options(cursor)

        if request.method == "POST":
            form, errors = _parse_form(request.form)

            if not errors:
                try:
                    image_path = save_uploaded_image(request.files.get("image"), "restaurants")
                except ValueError as error:
                    errors.append(str(error))
                    image_path = None

            if errors:
                for message in errors:
                    flash(message, "error")
                return render_template(
                    "content_admin/restaurants/form.html",
                    mode="create", restaurant=form, **options
                )

            try:
                cursor.execute(
                    """
                    INSERT INTO restaurants
                    (category_id, name, country_id, city_id, address, cuisine_type,
                     price_level, opening_hours, description, website_url,
                     image_path, status, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        form["category_id"], form["name"], form["country_id"], form["city_id"],
                        form["address"], form["cuisine_type"], form["price_level"],
                        form["opening_hours"], form["description"], form["website_url"],
                        image_path, form["status"], session["user_id"]
                    )
                )
                connection.commit()
                flash("餐廳新增成功", "success")
            except Exception as error:
                connection.rollback()
                print("新增餐廳失敗：", error)
                flash("新增餐廳失敗", "error")

            return redirect(url_for("restaurants.list_restaurants"))

        return render_template(
            "content_admin/restaurants/form.html",
            mode="create", restaurant=None, **options
        )

    finally:
        cursor.close()
        connection.close()


@restaurants_bp.route("/<int:restaurant_id>/edit", methods=["GET", "POST"])
@login_required("content_admin")
def edit_restaurant(restaurant_id):
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("restaurants.list_restaurants"))

    cursor = connection.cursor(dictionary=True)

    try:
        options = _load_options(cursor)

        cursor.execute("SELECT * FROM restaurants WHERE restaurant_id = %s", (restaurant_id,))
        existing = cursor.fetchone()

        if existing is None:
            flash("找不到這筆餐廳資料", "error")
            return redirect(url_for("restaurants.list_restaurants"))

        if request.method == "POST":
            form, errors = _parse_form(request.form)
            image_path = existing["image_path"]

            new_file = request.files.get("image")
            if new_file and new_file.filename:
                try:
                    uploaded_path = save_uploaded_image(new_file, "restaurants")
                    if uploaded_path:
                        delete_uploaded_image(existing["image_path"])
                        image_path = uploaded_path
                except ValueError as error:
                    errors.append(str(error))
            elif form["remove_image"]:
                delete_uploaded_image(existing["image_path"])
                image_path = None

            if errors:
                for message in errors:
                    flash(message, "error")
                form["restaurant_id"] = restaurant_id
                form["image_path"] = image_path
                return render_template(
                    "content_admin/restaurants/form.html",
                    mode="edit", restaurant=form, **options
                )

            try:
                cursor.execute(
                    """
                    UPDATE restaurants
                    SET category_id = %s, name = %s, country_id = %s, city_id = %s,
                        address = %s, cuisine_type = %s, price_level = %s,
                        opening_hours = %s, description = %s, website_url = %s,
                        image_path = %s, status = %s
                    WHERE restaurant_id = %s
                    """,
                    (
                        form["category_id"], form["name"], form["country_id"], form["city_id"],
                        form["address"], form["cuisine_type"], form["price_level"],
                        form["opening_hours"], form["description"], form["website_url"],
                        image_path, form["status"], restaurant_id
                    )
                )
                connection.commit()
                flash("餐廳資料已更新", "success")
            except Exception as error:
                connection.rollback()
                print("更新餐廳失敗：", error)
                flash("更新餐廳失敗", "error")

            return redirect(url_for("restaurants.list_restaurants"))

        return render_template(
            "content_admin/restaurants/form.html",
            mode="edit", restaurant=existing, **options
        )

    finally:
        cursor.close()
        connection.close()


@restaurants_bp.route("/<int:restaurant_id>/delete", methods=["POST"])
@login_required("content_admin")
def delete_restaurant(restaurant_id):
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("restaurants.list_restaurants"))

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT image_path FROM restaurants WHERE restaurant_id = %s",
            (restaurant_id,)
        )
        existing = cursor.fetchone()

        cursor.execute("DELETE FROM restaurants WHERE restaurant_id = %s", (restaurant_id,))
        connection.commit()

        if existing:
            delete_uploaded_image(existing["image_path"])

        flash("餐廳已刪除", "success")

    except Exception as error:
        connection.rollback()
        print("刪除餐廳失敗：", error)
        flash("刪除餐廳失敗，請確認沒有其他資料仍在使用此餐廳", "error")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("restaurants.list_restaurants", **request.args.to_dict()))
