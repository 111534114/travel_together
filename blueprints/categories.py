from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import login_required
from db import get_db_connection

categories_bp = Blueprint("categories", __name__, url_prefix="/content-admin/categories")

ALLOWED_TYPES = ("attraction", "restaurant", "accommodation")

TYPE_LABELS = {
    "attraction": "景點類別",
    "restaurant": "餐廳類別",
    "accommodation": "住宿類別",
}


@categories_bp.route("/")
@login_required("content_admin")
def manage_categories():
    category_type = request.args.get("type", "attraction").strip()

    if category_type not in ALLOWED_TYPES:
        category_type = "attraction"

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template(
            "content_admin/categories.html",
            categories=[], category_type=category_type,
            type_labels=TYPE_LABELS, allowed_types=ALLOWED_TYPES
        )

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT category_id, category_name, description, status
            FROM categories
            WHERE category_type = %s
            ORDER BY category_name
            """,
            (category_type,)
        )
        categories = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "content_admin/categories.html",
        categories=categories,
        category_type=category_type,
        type_labels=TYPE_LABELS,
        allowed_types=ALLOWED_TYPES
    )


@categories_bp.route("/new", methods=["POST"])
@login_required("content_admin")
def create_category():
    category_type = request.form.get("category_type", "").strip()
    name = request.form.get("category_name", "").strip()
    description = request.form.get("description", "").strip() or None

    if category_type not in ALLOWED_TYPES:
        flash("類別類型錯誤", "error")
        return redirect(url_for("categories.manage_categories"))

    if not name:
        flash("請輸入類別名稱", "error")
        return redirect(url_for("categories.manage_categories", type=category_type))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("categories.manage_categories", type=category_type))

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO categories(category_type, category_name, description, created_by)
            VALUES (%s, %s, %s, %s)
            """,
            (category_type, name, description, session["user_id"])
        )
        connection.commit()
        flash("類別新增成功", "success")
    except Exception as error:
        connection.rollback()
        print("新增類別失敗：", error)
        flash("新增類別失敗，名稱可能已存在", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("categories.manage_categories", type=category_type))


@categories_bp.route("/<int:category_id>/edit", methods=["POST"])
@login_required("content_admin")
def edit_category(category_id):
    category_type = request.form.get("category_type", "").strip()
    name = request.form.get("category_name", "").strip()
    description = request.form.get("description", "").strip() or None
    status = request.form.get("status", "active").strip()

    if category_type not in ALLOWED_TYPES:
        flash("類別類型錯誤", "error")
        return redirect(url_for("categories.manage_categories"))

    if not name:
        flash("請輸入類別名稱", "error")
        return redirect(url_for("categories.manage_categories", type=category_type))

    if status not in ("active", "hidden"):
        status = "active"

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("categories.manage_categories", type=category_type))

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE categories
            SET category_name = %s, description = %s, status = %s
            WHERE category_id = %s AND category_type = %s
            """,
            (name, description, status, category_id, category_type)
        )
        connection.commit()
        flash("類別已更新", "success")
    except Exception as error:
        connection.rollback()
        print("更新類別失敗：", error)
        flash("更新類別失敗，名稱可能已存在", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("categories.manage_categories", type=category_type))


@categories_bp.route("/<int:category_id>/delete", methods=["POST"])
@login_required("content_admin")
def delete_category(category_id):
    category_type = request.form.get("category_type", "").strip()

    if category_type not in ALLOWED_TYPES:
        flash("類別類型錯誤", "error")
        return redirect(url_for("categories.manage_categories"))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("categories.manage_categories", type=category_type))

    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM categories WHERE category_id = %s AND category_type = %s",
            (category_id, category_type)
        )
        connection.commit()
        flash("類別已刪除", "success")
    except Exception as error:
        connection.rollback()
        print("刪除類別失敗：", error)
        flash("刪除類別失敗", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("categories.manage_categories", type=category_type))
