from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from activity_log import log_action
from auth import login_required
from db import get_db_connection

friend_groups_admin_bp = Blueprint("friend_groups_admin", __name__, url_prefix="/content-admin/friend-groups")

PAGE_SIZE = 20

APPLICATION_STATUS_LABELS = {"pending": "待審核", "approved": "已核准", "rejected": "已退回"}
EVENT_STATUS_LABELS = {"open": "開放中", "closed": "已關閉", "cancelled": "已取消"}

TRAVELER_TYPE_NAMES = {
    ("relaxed", "group"): "悠閒派對咖",
    ("relaxed", "small_group"): "悠閒知己型",
    ("relaxed", "solo"): "悠閒漫遊者",
    ("balanced", "group"): "均衡社交家",
    ("balanced", "small_group"): "均衡旅伴",
    ("balanced", "solo"): "均衡獨行俠",
    ("packed", "group"): "熱血團長",
    ("packed", "small_group"): "熱血戰友",
    ("packed", "solo"): "熱血特種兵",
}


def _feature_enabled(cursor):
    cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key='friend_group_enabled'")
    row = cursor.fetchone()
    return bool(row) and row["setting_value"] == "1"


@friend_groups_admin_bp.route("/applications")
@login_required("content_admin")
def list_applications():
    status = request.args.get("status", "pending").strip()
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() and int(page) > 0 else 1

    if status not in APPLICATION_STATUS_LABELS and status != "all":
        status = "pending"

    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template(
            "content_admin/friend_groups/applications.html",
            applications=[], status=status, status_labels=APPLICATION_STATUS_LABELS,
            page=1, total_pages=1, total=0, feature_enabled=False,
        )

    cursor = connection.cursor(dictionary=True)
    try:
        feature_enabled = _feature_enabled(cursor)

        params = []
        where_clause = ""
        if status != "all":
            where_clause = "WHERE a.status = %s"
            params.append(status)

        cursor.execute(f"SELECT COUNT(*) AS total FROM friend_group_applications a {where_clause}", params)
        total = cursor.fetchone()["total"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        offset = (page - 1) * PAGE_SIZE

        cursor.execute(
            f"""
            SELECT a.application_id, a.note, a.status, a.review_note, a.created_at,
                   u.user_id, u.full_name, u.nickname, u.birthdate
            FROM friend_group_applications a
            JOIN users u ON u.user_id = a.user_id
            {where_clause}
            ORDER BY a.created_at ASC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, offset]
        )
        applications = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return render_template(
        "content_admin/friend_groups/applications.html",
        applications=applications, status=status, status_labels=APPLICATION_STATUS_LABELS,
        page=page, total_pages=total_pages, total=total, feature_enabled=feature_enabled,
    )


@friend_groups_admin_bp.route("/applications/<int:application_id>/approve", methods=["POST"])
@login_required("content_admin")
def approve_application(application_id):
    back_status = request.form.get("status", "pending")
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("friend_groups_admin.list_applications", status=back_status))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id FROM friend_group_applications WHERE application_id=%s", (application_id,))
        application = cursor.fetchone()
        if not application:
            flash("找不到這筆申請。", "error")
            return redirect(url_for("friend_groups_admin.list_applications", status=back_status))

        cursor.execute(
            """UPDATE friend_group_applications
               SET status='approved', reviewed_by=%s, reviewed_at=NOW(), review_note=NULL
               WHERE application_id=%s""",
            (session["user_id"], application_id)
        )
        cursor.execute(
            "INSERT INTO notifications (user_id, notification_type, title, message, target_url) VALUES (%s,'system','交友揪團申請已核准',%s,%s)",
            (application["user_id"], "你的交友揪團使用申請已經通過，先去報名一場官方活動吧！",
             url_for("friend_groups.index"))
        )
        log_action(cursor, "approve_friend_group_application", "friend_group_application", application_id, "核准交友揪團使用申請")
        connection.commit()
        flash("申請已核准。", "success")
    except Exception as error:
        connection.rollback()
        print("核准交友揪團申請失敗：", error)
        flash("核准失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("friend_groups_admin.list_applications", status=back_status))


@friend_groups_admin_bp.route("/applications/<int:application_id>/reject", methods=["POST"])
@login_required("content_admin")
def reject_application(application_id):
    back_status = request.form.get("status", "pending")
    review_note = request.form.get("review_note", "").strip()
    if not review_note:
        flash("退回時請填寫原因。", "error")
        return redirect(url_for("friend_groups_admin.list_applications", status=back_status))

    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("friend_groups_admin.list_applications", status=back_status))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id FROM friend_group_applications WHERE application_id=%s", (application_id,))
        application = cursor.fetchone()
        if not application:
            flash("找不到這筆申請。", "error")
            return redirect(url_for("friend_groups_admin.list_applications", status=back_status))

        cursor.execute(
            """UPDATE friend_group_applications
               SET status='rejected', reviewed_by=%s, reviewed_at=NOW(), review_note=%s
               WHERE application_id=%s""",
            (session["user_id"], review_note, application_id)
        )
        cursor.execute(
            "INSERT INTO notifications (user_id, notification_type, title, message, target_url) VALUES (%s,'system','交友揪團申請被退回',%s,%s)",
            (application["user_id"], f"你的交友揪團使用申請沒有通過，原因：{review_note}", url_for("friend_groups.index"))
        )
        log_action(cursor, "reject_friend_group_application", "friend_group_application", application_id, f"退回交友揪團使用申請，原因：{review_note}")
        connection.commit()
        flash("申請已退回。", "success")
    except Exception as error:
        connection.rollback()
        print("退回交友揪團申請失敗：", error)
        flash("退回失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("friend_groups_admin.list_applications", status=back_status))


@friend_groups_admin_bp.route("/settings/toggle", methods=["POST"])
@login_required("content_admin")
def toggle_setting():
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("friend_groups_admin.list_applications"))

    cursor = connection.cursor(dictionary=True)
    try:
        enabled = _feature_enabled(cursor)
        new_value = "0" if enabled else "1"
        cursor.execute(
            """INSERT INTO app_settings (setting_key, setting_value, updated_by) VALUES ('friend_group_enabled', %s, %s)
               ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value), updated_by=VALUES(updated_by)""",
            (new_value, session["user_id"])
        )
        log_action(cursor, "toggle_friend_group_setting", "app_setting", None, f"交友揪團功能總開關切換為 {'開啟' if new_value == '1' else '關閉'}")
        connection.commit()
        flash(f"交友揪團功能已{'開啟' if new_value == '1' else '關閉'}。", "success")
    except Exception as error:
        connection.rollback()
        print("切換交友揪團開關失敗：", error)
        flash("切換失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("friend_groups_admin.list_applications"))


@friend_groups_admin_bp.route("/events")
@login_required("content_admin")
def list_events():
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template("content_admin/friend_groups/events_list.html", events=[])

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT e.*,
                   (SELECT COUNT(*) FROM friend_group_event_participants p WHERE p.event_id=e.event_id AND p.status IN ('registered','attended')) AS registered_count,
                   (SELECT COUNT(*) FROM friend_group_event_participants p WHERE p.event_id=e.event_id AND p.status='attended') AS attended_count
            FROM friend_group_events e
            ORDER BY e.event_date DESC
        """)
        events = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
    return render_template(
        "content_admin/friend_groups/events_list.html",
        events=events, status_labels=EVENT_STATUS_LABELS,
    )


@friend_groups_admin_bp.route("/events/new", methods=["GET", "POST"])
@login_required("content_admin")
def new_event():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip() or None
        location = request.form.get("location", "").strip() or None
        event_date = request.form.get("event_date", "").strip()
        start_time = request.form.get("start_time") or None
        end_time = request.form.get("end_time") or None
        capacity = request.form.get("capacity") or None

        if not title or not event_date:
            flash("請填寫活動名稱與日期。", "error")
            return redirect(url_for("friend_groups_admin.new_event"))

        connection = get_db_connection()
        if connection is None:
            flash("資料庫連線失敗", "error")
            return redirect(url_for("friend_groups_admin.list_events"))
        cursor = connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO friend_group_events (title, description, location, event_date, start_time, end_time, capacity, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (title, description, location, event_date, start_time, end_time, capacity, session["user_id"]))
            event_id = cursor.lastrowid
            log_action(cursor, "create_friend_group_event", "friend_group_event", event_id, f"建立官方活動：{title}")
            connection.commit()
            flash("官方活動已建立。", "success")
        except Exception as error:
            connection.rollback()
            print("建立官方活動失敗：", error)
            flash("建立失敗，請再試一次。", "error")
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for("friend_groups_admin.list_events"))

    return render_template("content_admin/friend_groups/event_form.html", event=None)


@friend_groups_admin_bp.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required("content_admin")
def edit_event(event_id):
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("friend_groups_admin.list_events"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM friend_group_events WHERE event_id=%s", (event_id,))
        event = cursor.fetchone()
        if not event:
            flash("找不到這場活動。", "error")
            return redirect(url_for("friend_groups_admin.list_events"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip() or None
            location = request.form.get("location", "").strip() or None
            event_date = request.form.get("event_date", "").strip()
            start_time = request.form.get("start_time") or None
            end_time = request.form.get("end_time") or None
            capacity = request.form.get("capacity") or None

            if not title or not event_date:
                flash("請填寫活動名稱與日期。", "error")
                return redirect(url_for("friend_groups_admin.edit_event", event_id=event_id))

            cursor.execute("""
                UPDATE friend_group_events
                SET title=%s, description=%s, location=%s, event_date=%s, start_time=%s, end_time=%s, capacity=%s
                WHERE event_id=%s
            """, (title, description, location, event_date, start_time, end_time, capacity, event_id))
            log_action(cursor, "update_friend_group_event", "friend_group_event", event_id, f"編輯官方活動：{title}")
            connection.commit()
            flash("活動內容已更新。", "success")
            return redirect(url_for("friend_groups_admin.list_events"))
    finally:
        cursor.close()
        connection.close()
    return render_template("content_admin/friend_groups/event_form.html", event=event)


@friend_groups_admin_bp.route("/events/<int:event_id>/cancel", methods=["POST"])
@login_required("content_admin")
def cancel_event(event_id):
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("friend_groups_admin.list_events"))
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE friend_group_events SET status='cancelled' WHERE event_id=%s", (event_id,))
        log_action(cursor, "cancel_friend_group_event", "friend_group_event", event_id, "取消官方活動")
        connection.commit()
        flash("活動已取消。", "success")
    except Exception as error:
        connection.rollback()
        print("取消官方活動失敗：", error)
        flash("取消失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("friend_groups_admin.list_events"))


@friend_groups_admin_bp.route("/events/<int:event_id>/participants")
@login_required("content_admin")
def event_participants(event_id):
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("friend_groups_admin.list_events"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM friend_group_events WHERE event_id=%s", (event_id,))
        event = cursor.fetchone()
        if not event:
            flash("找不到這場活動。", "error")
            return redirect(url_for("friend_groups_admin.list_events"))

        cursor.execute("""
            SELECT p.*, u.full_name, u.nickname
            FROM friend_group_event_participants p JOIN users u ON u.user_id=p.user_id
            WHERE p.event_id=%s
            ORDER BY FIELD(p.status,'registered','attended','no_show','cancelled'), p.registered_at
        """, (event_id,))
        participants = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
    return render_template(
        "content_admin/friend_groups/event_participants.html",
        event=event, participants=participants,
    )


@friend_groups_admin_bp.route("/events/<int:event_id>/participants/<int:user_id>/check-in", methods=["POST"])
@login_required("content_admin")
def check_in_participant(event_id, user_id):
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("friend_groups_admin.event_participants", event_id=event_id))
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE friend_group_event_participants SET status='attended', checked_in_at=NOW() WHERE event_id=%s AND user_id=%s",
            (event_id, user_id)
        )
        log_action(cursor, "check_in_friend_group_participant", "friend_group_event", event_id, f"標記報到：使用者 {user_id}")
        connection.commit()
        flash("已標記報到。", "success")
    except Exception as error:
        connection.rollback()
        print("標記報到失敗：", error)
        flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("friend_groups_admin.event_participants", event_id=event_id))


@friend_groups_admin_bp.route("/stats")
@login_required("content_admin")
def stats():
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template("content_admin/friend_groups/stats.html", type_counts=[], total=0)

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT traveler_type, COUNT(*) AS total
            FROM traveler_profiles
            GROUP BY traveler_type
            ORDER BY total DESC
        """)
        type_counts = cursor.fetchall()
        total = sum(row["total"] for row in type_counts)
    finally:
        cursor.close()
        connection.close()
    return render_template("content_admin/friend_groups/stats.html", type_counts=type_counts, total=total)
