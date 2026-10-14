from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from activity_log import log_action
from auth import login_required
from db import get_db_connection
from utils import delete_uploaded_image


attraction_posts_admin_bp = Blueprint(
    "attraction_posts_admin", __name__, url_prefix="/content-admin/attraction-posts"
)
PAGE_SIZE = 20
STATUS_LABELS = {"pending": "待審核", "approved": "已核准", "rejected": "已退回"}


@attraction_posts_admin_bp.route("/")
@login_required("content_admin")
def list_posts():
    status = request.args.get("status", "pending").strip()
    if status not in STATUS_LABELS and status != "all":
        status = "pending"
    page_text = request.args.get("page", "1")
    page = int(page_text) if page_text.isdigit() and int(page_text) > 0 else 1
    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor(dictionary=True)
    try:
        params = []
        where_clause = ""
        if status != "all":
            where_clause = "WHERE p.review_status = %s"
            params.append(status)
        cursor.execute(f"SELECT COUNT(*) AS total FROM attraction_posts p {where_clause}", params)
        total = cursor.fetchone()["total"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        cursor.execute(
            f"""
            SELECT p.post_id, p.caption, p.review_status, p.review_note, p.created_at,
                   a.attraction_id, a.name AS attraction_name,
                   u.full_name AS poster_name, u.nickname AS poster_nickname
            FROM attraction_posts p
            JOIN attractions a ON a.attraction_id = p.attraction_id
            JOIN users u ON u.user_id = p.user_id
            {where_clause}
            ORDER BY p.created_at ASC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, (page - 1) * PAGE_SIZE],
        )
        posts = cursor.fetchall()
        if posts:
            post_ids = [post["post_id"] for post in posts]
            placeholders = ",".join(["%s"] * len(post_ids))
            cursor.execute(
                f"SELECT post_id, image_path FROM attraction_post_images "
                f"WHERE post_id IN ({placeholders}) ORDER BY post_id, sort_order, image_id",
                tuple(post_ids),
            )
            images_by_post = {}
            for row in cursor.fetchall():
                images_by_post.setdefault(row["post_id"], []).append(row["image_path"])
            for post in posts:
                post["images"] = images_by_post.get(post["post_id"], [])
    finally:
        cursor.close()
        connection.close()
    return render_template(
        "content_admin/attraction_posts/list.html", posts=posts, status=status,
        status_labels=STATUS_LABELS, page=page, total_pages=total_pages, total=total,
    )


def _back_status():
    status = request.form.get("status", "pending")
    return status if status in (*STATUS_LABELS, "all") else "pending"


@attraction_posts_admin_bp.route("/<int:post_id>/approve", methods=["POST"])
@login_required("content_admin")
def approve_post(post_id):
    back_status = _back_status()
    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT user_id, attraction_id FROM attraction_posts WHERE post_id=%s FOR UPDATE",
            (post_id,),
        )
        post = cursor.fetchone()
        if post is None:
            abort(404)
        cursor.execute(
            "UPDATE attraction_posts SET review_status='approved', reviewed_by=%s, "
            "reviewed_at=NOW(), review_note=NULL WHERE post_id=%s",
            (session["user_id"], post_id),
        )
        cursor.execute(
            "INSERT INTO notifications (user_id, notification_type, title, message, target_url) "
            "VALUES (%s, 'system', '景點相簿貼文已核准', "
            "'你分享的照片已經通過審核，現在大家都看得到了。', %s)",
            (post["user_id"], url_for("member.attraction_detail", attraction_id=post["attraction_id"]) + "#album"),
        )
        log_action(cursor, "approve_attraction_post", "attraction_post", post_id, "核准景點相簿貼文")
        connection.commit()
        flash("貼文已核准，會顯示在景點相簿中。", "success")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))


@attraction_posts_admin_bp.route("/<int:post_id>/reject", methods=["POST"])
@login_required("content_admin")
def reject_post(post_id):
    back_status = _back_status()
    review_note = request.form.get("review_note", "").strip()
    if not review_note:
        flash("退回時請填寫原因。", "error")
        return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))
    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor(dictionary=True)
    image_paths = []
    try:
        cursor.execute(
            "SELECT user_id, attraction_id FROM attraction_posts WHERE post_id=%s FOR UPDATE",
            (post_id,),
        )
        post = cursor.fetchone()
        if post is None:
            abort(404)
        cursor.execute("SELECT image_path FROM attraction_post_images WHERE post_id=%s", (post_id,))
        image_paths = [row["image_path"] for row in cursor.fetchall()]
        cursor.execute(
            "UPDATE attraction_posts SET review_status='rejected', reviewed_by=%s, "
            "reviewed_at=NOW(), review_note=%s WHERE post_id=%s",
            (session["user_id"], review_note[:255], post_id),
        )
        cursor.execute("DELETE FROM attraction_post_images WHERE post_id=%s", (post_id,))
        cursor.execute(
            "INSERT INTO notifications (user_id, notification_type, title, message, target_url) "
            "VALUES (%s, 'system', '景點相簿貼文被退回', %s, %s)",
            (post["user_id"], f"你分享的照片沒有通過審核，原因：{review_note[:255]}",
             url_for("member.attraction_detail", attraction_id=post["attraction_id"]) + "#album"),
        )
        log_action(cursor, "reject_attraction_post", "attraction_post", post_id,
                   f"退回景點相簿貼文，原因：{review_note[:255]}")
        connection.commit()
        for path in image_paths:
            delete_uploaded_image(path)
        flash("貼文已退回，照片已從伺服器移除。", "success")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))
