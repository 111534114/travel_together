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

accommodations_bp = Blueprint(
    "accommodations", __name__, url_prefix="/content-admin/accommodations"
)

PAGE_SIZE = 20

STATUS_CHOICES = ("active", "hidden", "pending")


def _parse_time(value):
    value = value.strip()
    return value or None


def _parse_form(form_data):
    form = {
        "category_id": form_data.get("category_id", "").strip() or None,
        "name": form_data.get("name", "").strip(),
        "country_id": form_data.get("country_id", "").strip(),
        "city_id": form_data.get("city_id", "").strip(),
        "address": form_data.get("address", "").strip() or None,
        "accommodation_type": form_data.get("accommodation_type", "").strip() or None,
        "price_per_night": form_data.get("price_per_night", "").strip(),
        "check_in_time": _parse_time(form_data.get("check_in_time", "")),
        "check_out_time": _parse_time(form_data.get("check_out_time", "")),
        "description": form_data.get("description", "").strip() or None,
        "website_url": form_data.get("website_url", "").strip() or None,
        "status": form_data.get("status", "active").strip(),
        "remove_image": form_data.get("remove_image") == "on",
    }

    errors = []

    if not form["name"]:
        errors.append("請輸入住宿名稱")

    if not form["country_id"]:
        errors.append("請選擇國家")

    if not form["city_id"]:
        errors.append("請選擇城市")

    if form["price_per_night"] == "":
        form["price_per_night"] = 0
    else:
        try:
            form["price_per_night"] = float(form["price_per_night"])
            if form["price_per_night"] < 0:
                raise ValueError
        except ValueError:
            errors.append("房價必須是不小於 0 的數字")
            form["price_per_night"] = 0

    if form["status"] not in STATUS_CHOICES:
        form["status"] = "active"

    return form, errors


def _load_options(cursor):
    return {
        "countries": get_countries(cursor),
        "cities": get_cities(cursor),
        "categories": get_categories(cursor, "accommodation"),
    }


@accommodations_bp.route("/")
@login_required("content_admin")
def list_accommodations():
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
            "content_admin/accommodations/list.html",
            accommodations=[], countries=[], cities=[], categories=[],
            keyword=keyword, country_id=country_id, city_id=city_id,
            category_id=category_id, status=status, page=1, total_pages=1, total=0
        )

    cursor = connection.cursor(dictionary=True)

    try:
        conditions = []
        params = []

        if keyword:
            conditions.append("(ac.name LIKE %s OR ac.address LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        if country_id:
            conditions.append("ac.country_id = %s")
            params.append(country_id)

        if city_id:
            conditions.append("ac.city_id = %s")
            params.append(city_id)

        if category_id:
            conditions.append("ac.category_id = %s")
            params.append(category_id)

        if status:
            conditions.append("ac.status = %s")
            params.append(status)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor.execute(
            f"SELECT COUNT(*) AS total FROM accommodations ac {where_clause}",
            params
        )
        total = cursor.fetchone()["total"]

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        offset = (page - 1) * PAGE_SIZE

        cursor.execute(
            f"""
            SELECT ac.accommodation_id, ac.name, ac.address, ac.accommodation_type,
                   ac.price_per_night, ac.check_in_time, ac.check_out_time,
                   ac.image_path, ac.status, ac.ai_verified_at,
                   cat.category_name, co.name AS country_name, ci.name AS city_name
            FROM accommodations ac
            LEFT JOIN categories cat ON cat.category_id = ac.category_id
            JOIN countries co ON co.country_id = ac.country_id
            JOIN cities ci ON ci.city_id = ac.city_id
            {where_clause}
            ORDER BY ac.accommodation_id DESC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, offset]
        )
        accommodations = cursor.fetchall()

        options = _load_options(cursor)

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "content_admin/accommodations/list.html",
        accommodations=accommodations,
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


@accommodations_bp.route("/new", methods=["GET", "POST"])
@login_required("content_admin")
def create_accommodation():
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("accommodations.list_accommodations"))

    cursor = connection.cursor(dictionary=True)

    try:
        options = _load_options(cursor)

        if request.method == "POST":
            form, errors = _parse_form(request.form)

            if not errors:
                try:
                    image_path = save_uploaded_image(request.files.get("image"), "accommodations")
                except ValueError as error:
                    errors.append(str(error))
                    image_path = None

            if errors:
                for message in errors:
                    flash(message, "error")
                return render_template(
                    "content_admin/accommodations/form.html",
                    mode="create", accommodation=form, **options
                )

            try:
                cursor.execute(
                    """
                    INSERT INTO accommodations
                    (category_id, name, country_id, city_id, address, accommodation_type,
                     price_per_night, check_in_time, check_out_time, description,
                     website_url, image_path, status, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        form["category_id"], form["name"], form["country_id"], form["city_id"],
                        form["address"], form["accommodation_type"], form["price_per_night"],
                        form["check_in_time"], form["check_out_time"], form["description"],
                        form["website_url"], image_path, form["status"], session["user_id"]
                    )
                )
                connection.commit()
                flash("住宿新增成功", "success")
            except Exception as error:
                connection.rollback()
                print("新增住宿失敗：", error)
                flash("新增住宿失敗", "error")

            return redirect(url_for("accommodations.list_accommodations"))

        return render_template(
            "content_admin/accommodations/form.html",
            mode="create", accommodation=None, **options
        )

    finally:
        cursor.close()
        connection.close()


@accommodations_bp.route("/<int:accommodation_id>/edit", methods=["GET", "POST"])
@login_required("content_admin")
def edit_accommodation(accommodation_id):
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("accommodations.list_accommodations"))

    cursor = connection.cursor(dictionary=True)

    try:
        options = _load_options(cursor)

        cursor.execute(
            "SELECT * FROM accommodations WHERE accommodation_id = %s",
            (accommodation_id,)
        )
        existing = cursor.fetchone()

        if existing is None:
            flash("找不到這筆住宿資料", "error")
            return redirect(url_for("accommodations.list_accommodations"))

        if request.method == "POST":
            form, errors = _parse_form(request.form)
            image_path = existing["image_path"]

            new_file = request.files.get("image")
            if new_file and new_file.filename:
                try:
                    uploaded_path = save_uploaded_image(new_file, "accommodations")
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
                form["accommodation_id"] = accommodation_id
                form["image_path"] = image_path
                return render_template(
                    "content_admin/accommodations/form.html",
                    mode="edit", accommodation=form, **options
                )

            try:
                cursor.execute(
                    """
                    UPDATE accommodations
                    SET category_id = %s, name = %s, country_id = %s, city_id = %s,
                        address = %s, accommodation_type = %s, price_per_night = %s,
                        check_in_time = %s, check_out_time = %s, description = %s,
                        website_url = %s, image_path = %s, status = %s
                    WHERE accommodation_id = %s
                    """,
                    (
                        form["category_id"], form["name"], form["country_id"], form["city_id"],
                        form["address"], form["accommodation_type"], form["price_per_night"],
                        form["check_in_time"], form["check_out_time"], form["description"],
                        form["website_url"], image_path, form["status"], accommodation_id
                    )
                )
                connection.commit()
                flash("住宿資料已更新", "success")
            except Exception as error:
                connection.rollback()
                print("更新住宿失敗：", error)
                flash("更新住宿失敗", "error")

            return redirect(url_for("accommodations.list_accommodations"))

        return render_template(
            "content_admin/accommodations/form.html",
            mode="edit", accommodation=existing, **options
        )

    finally:
        cursor.close()
        connection.close()


@accommodations_bp.route("/<int:accommodation_id>/delete", methods=["POST"])
@login_required("content_admin")
def delete_accommodation(accommodation_id):
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("accommodations.list_accommodations"))

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT image_path FROM accommodations WHERE accommodation_id = %s",
            (accommodation_id,)
        )
        existing = cursor.fetchone()

        cursor.execute(
            "DELETE FROM accommodations WHERE accommodation_id = %s",
            (accommodation_id,)
        )
        connection.commit()

        if existing:
            delete_uploaded_image(existing["image_path"])

        flash("住宿已刪除", "success")

    except Exception as error:
        connection.rollback()
        print("刪除住宿失敗：", error)
        flash("刪除住宿失敗，請確認沒有其他資料仍在使用此住宿", "error")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("accommodations.list_accommodations", **request.args.to_dict()))
