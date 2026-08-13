from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import login_required
from db import get_db_connection

ai_data_bp = Blueprint("ai_data", __name__, url_prefix="/content-admin/ai-data")

TYPE_CONFIG = {
    "attraction": {
        "table": "attractions",
        "pk": "attraction_id",
        "label": "景點",
    },
    "restaurant": {
        "table": "restaurants",
        "pk": "restaurant_id",
        "label": "餐廳",
    },
    "accommodation": {
        "table": "accommodations",
        "pk": "accommodation_id",
        "label": "住宿",
    },
}


@ai_data_bp.route("/")
@login_required("content_admin")
def list_ai_data():
    item_type = request.args.get("type", "attraction").strip()

    if item_type not in TYPE_CONFIG:
        item_type = "attraction"

    config = TYPE_CONFIG[item_type]

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template(
            "content_admin/ai_data.html",
            items=[], item_type=item_type, type_config=TYPE_CONFIG
        )

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
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
        items = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "content_admin/ai_data.html",
        items=items,
        item_type=item_type,
        type_config=TYPE_CONFIG
    )


@ai_data_bp.route("/<item_type>/<int:item_id>/verify", methods=["POST"])
@login_required("content_admin")
def verify_item(item_type, item_id):
    if item_type not in TYPE_CONFIG:
        flash("資料類型錯誤", "error")
        return redirect(url_for("ai_data.list_ai_data"))

    config = TYPE_CONFIG[item_type]

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("ai_data.list_ai_data", type=item_type))

    cursor = connection.cursor()

    try:
        cursor.execute(
            f"""
            UPDATE {config['table']}
            SET ai_verified_at = NOW(), ai_verified_by = %s
            WHERE {config['pk']} = %s
            """,
            (session["user_id"], item_id)
        )
        connection.commit()
        flash(f"已標記此{config['label']}資料為今日已確認", "success")
    except Exception as error:
        connection.rollback()
        print("標記 AI 資料確認失敗：", error)
        flash("標記失敗", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("ai_data.list_ai_data", type=item_type))
