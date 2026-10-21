from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import login_required
from db import get_db_connection

friend_groups_bp = Blueprint("friend_groups", __name__, url_prefix="/member/friend-groups")

MIN_AGE = 18  # 申請這個功能的最低年齡限制

PACE_LABELS = {"relaxed": "悠閒", "balanced": "適中", "packed": "緊湊"}
SOCIAL_LABELS = {"group": "熱鬧團體", "small_group": "小圈子深聊", "solo": "獨立探索"}
BUDGET_LABELS = {"frugal": "精打細算", "moderate": "適度花費", "generous": "願意享受"}
DIET_LABELS = {"none": "不限", "vegetarian": "素食", "halal": "清真", "no_beef": "不吃牛", "no_seafood": "不吃海鮮", "other": "其他"}
TRANSPORT_LABELS = {"any": "皆可", "public": "大眾運輸", "drive": "自行開車", "taxi": "計程車／叫車", "carpool": "共乘"}
WALK_LABELS = {"low": "低", "medium": "中", "high": "高"}
ACTIVITY_TAGS = ["觀光景點", "在地美食", "購物", "戶外活動", "文化體驗", "夜生活", "拍照打卡", "放鬆度假"]

# 旅遊人格稱號：由「步調 x 社交傾向」9 種組合算出，純顯示用，不另外存表
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


def _connection_or_home():
    connection = get_db_connection()
    if connection is None:
        flash("目前無法連線資料庫，請稍後再試。", "error")
        return None
    return connection


def _feature_enabled(cursor):
    cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key='friend_group_enabled'")
    row = cursor.fetchone()
    return bool(row) and row["setting_value"] == "1"


def _latest_application(cursor, user_id):
    cursor.execute(
        "SELECT * FROM friend_group_applications WHERE user_id=%s ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    return cursor.fetchone()


def _has_attended_event(cursor, user_id):
    cursor.execute(
        "SELECT 1 FROM friend_group_event_participants WHERE user_id=%s AND status='attended' LIMIT 1",
        (user_id,)
    )
    return cursor.fetchone() is not None


def _can_use_groups(cursor, user_id):
    application = _latest_application(cursor, user_id)
    if not application or application["status"] != "approved":
        return False
    return _has_attended_event(cursor, user_id)


def _traveler_profile(cursor, user_id):
    cursor.execute("SELECT * FROM traveler_profiles WHERE user_id=%s", (user_id,))
    return cursor.fetchone()


@friend_groups_bp.route("/")
@login_required("member")
def index():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        if not _feature_enabled(cursor):
            flash("交友揪團功能目前尚未開放。", "error")
            return redirect(url_for("member.dashboard"))

        user_id = session["user_id"]
        application = _latest_application(cursor, user_id)
        unlocked = False
        profile = None
        events = []
        groups = []
        my_groups = []

        if application and application["status"] == "approved":
            unlocked = _has_attended_event(cursor, user_id)
            profile = _traveler_profile(cursor, user_id)

            cursor.execute("""
                SELECT e.*,
                       (SELECT COUNT(*) FROM friend_group_event_participants p WHERE p.event_id=e.event_id AND p.status IN ('registered','attended')) AS registered_count,
                       (SELECT status FROM friend_group_event_participants p WHERE p.event_id=e.event_id AND p.user_id=%s) AS my_status
                FROM friend_group_events e
                WHERE e.status='open'
                ORDER BY e.event_date ASC
            """, (user_id,))
            events = cursor.fetchall()

            if unlocked:
                cursor.execute("""
                    SELECT g.*, u.nickname, u.full_name,
                           (SELECT COUNT(*) FROM friend_group_members m WHERE m.group_id=g.group_id AND m.status='approved') AS member_count,
                           (SELECT status FROM friend_group_members m WHERE m.group_id=g.group_id AND m.user_id=%s) AS my_status
                    FROM friend_groups g JOIN users u ON u.user_id=g.host_user_id
                    WHERE g.status='open' AND g.host_user_id != %s
                    ORDER BY g.event_date ASC
                """, (user_id, user_id))
                groups = cursor.fetchall()

                cursor.execute("""
                    SELECT g.*,
                           (SELECT COUNT(*) FROM friend_group_members m WHERE m.group_id=g.group_id AND m.status='approved') AS member_count,
                           (SELECT COUNT(*) FROM friend_group_members m WHERE m.group_id=g.group_id AND m.status='pending') AS pending_count
                    FROM friend_groups g
                    WHERE g.host_user_id=%s
                    ORDER BY g.created_at DESC
                """, (user_id,))
                my_groups = cursor.fetchall()
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/index.html",
        application=application, unlocked=unlocked, profile=profile,
        events=events, groups=groups, my_groups=my_groups,
        pace_labels=PACE_LABELS, social_labels=SOCIAL_LABELS,
    )


@friend_groups_bp.route("/apply", methods=["POST"])
@login_required("member")
def apply():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        if not _feature_enabled(cursor):
            flash("交友揪團功能目前尚未開放。", "error")
            return redirect(url_for("member.dashboard"))

        user_id = session["user_id"]
        application = _latest_application(cursor, user_id)
        if application and application["status"] in ("pending", "approved"):
            flash("你已經申請過了。", "error")
            return redirect(url_for("friend_groups.index"))

        birthdate_raw = request.form.get("birthdate", "").strip()
        note = request.form.get("note", "").strip()
        if not birthdate_raw:
            flash("請填寫生日。", "error")
            return redirect(url_for("friend_groups.index"))
        try:
            birthdate = datetime.strptime(birthdate_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("生日格式不正確。", "error")
            return redirect(url_for("friend_groups.index"))

        today = date.today()
        if birthdate > today:
            flash("生日不能是未來的日期。", "error")
            return redirect(url_for("friend_groups.index"))
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        if age < MIN_AGE:
            flash(f"這個功能限 {MIN_AGE} 歲以上會員申請。", "error")
            return redirect(url_for("friend_groups.index"))

        cursor.execute("UPDATE users SET birthdate=%s WHERE user_id=%s", (birthdate, user_id))
        cursor.execute(
            "INSERT INTO friend_group_applications (user_id, note) VALUES (%s,%s)",
            (user_id, note or None)
        )
        connection.commit()
        flash("申請已送出，等待管理員審核。", "success")
    except Exception:
        connection.rollback(); flash("申請失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.index"))


@friend_groups_bp.route("/questionnaire", methods=["GET", "POST"])
@login_required("member")
def questionnaire():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        application = _latest_application(cursor, user_id)
        if not application or application["status"] != "approved":
            flash("要先通過申請才能填問卷。", "error")
            return redirect(url_for("friend_groups.index"))

        if request.method == "POST":
            pace = request.form.get("pace")
            social_style = request.form.get("social_style")
            budget_style = request.form.get("budget_style", "moderate")
            diet = request.form.get("diet", "none")
            transport_pref = request.form.get("transport_pref", "any")
            walk_tolerance = request.form.get("walk_tolerance", "medium")
            like_activities = ",".join(request.form.getlist("like_activities"))
            dislike_activities = ",".join(request.form.getlist("dislike_activities"))

            if pace not in PACE_LABELS or social_style not in SOCIAL_LABELS:
                flash("請完整填寫問卷。", "error")
                return redirect(url_for("friend_groups.questionnaire"))

            traveler_type = TRAVELER_TYPE_NAMES.get((pace, social_style), "旅人")

            cursor.execute("""
                INSERT INTO traveler_profiles
                    (user_id, pace, social_style, budget_style, like_activities, dislike_activities,
                     diet, transport_pref, walk_tolerance, traveler_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    pace=VALUES(pace), social_style=VALUES(social_style), budget_style=VALUES(budget_style),
                    like_activities=VALUES(like_activities), dislike_activities=VALUES(dislike_activities),
                    diet=VALUES(diet), transport_pref=VALUES(transport_pref), walk_tolerance=VALUES(walk_tolerance),
                    traveler_type=VALUES(traveler_type)
            """, (user_id, pace, social_style, budget_style, like_activities or None, dislike_activities or None,
                  diet, transport_pref, walk_tolerance, traveler_type))
            connection.commit()
            flash(f"問卷已送出！你的旅遊人格是「{traveler_type}」。", "success")
            return redirect(url_for("friend_groups.index"))

        profile = _traveler_profile(cursor, user_id)
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/questionnaire.html",
        profile=profile, activity_tags=ACTIVITY_TAGS,
        pace_labels=PACE_LABELS, social_labels=SOCIAL_LABELS, budget_labels=BUDGET_LABELS,
        diet_labels=DIET_LABELS, transport_labels=TRANSPORT_LABELS, walk_labels=WALK_LABELS,
    )


@friend_groups_bp.route("/events/<int:event_id>/register", methods=["POST"])
@login_required("member")
def register_event(event_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        application = _latest_application(cursor, user_id)
        if not application or application["status"] != "approved":
            flash("要先通過申請才能報名活動。", "error")
            return redirect(url_for("friend_groups.index"))

        cursor.execute("SELECT * FROM friend_group_events WHERE event_id=%s AND status='open'", (event_id,))
        event = cursor.fetchone()
        if not event:
            flash("找不到這場活動，或活動已關閉。", "error")
            return redirect(url_for("friend_groups.index"))

        if event["capacity"]:
            cursor.execute(
                "SELECT COUNT(*) AS c FROM friend_group_event_participants WHERE event_id=%s AND status IN ('registered','attended')",
                (event_id,)
            )
            if cursor.fetchone()["c"] >= event["capacity"]:
                flash("這場活動人數已滿。", "error")
                return redirect(url_for("friend_groups.index"))

        cursor.execute(
            """INSERT INTO friend_group_event_participants (event_id, user_id) VALUES (%s,%s)
               ON DUPLICATE KEY UPDATE status='registered', registered_at=NOW()""",
            (event_id, user_id)
        )
        connection.commit()
        flash("已報名這場活動。", "success")
    except Exception:
        connection.rollback(); flash("報名失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.index"))


@friend_groups_bp.route("/events/<int:event_id>/cancel", methods=["POST"])
@login_required("member")
def cancel_event(event_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE friend_group_event_participants SET status='cancelled' WHERE event_id=%s AND user_id=%s AND status='registered'",
            (event_id, session["user_id"])
        )
        connection.commit()
        flash("已取消報名。", "success")
    except Exception:
        connection.rollback(); flash("取消失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.index"))


@friend_groups_bp.route("/groups/new", methods=["GET", "POST"])
@login_required("member")
def new_group():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        if not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動才能發起揪團。", "error")
            return redirect(url_for("friend_groups.index"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            location = request.form.get("location", "").strip()
            event_date = request.form.get("event_date", "").strip()
            start_time = request.form.get("start_time") or None
            end_time = request.form.get("end_time") or None
            capacity = request.form.get("capacity") or None
            description = request.form.get("description", "").strip() or None
            pace_filter = request.form.get("pace_filter") or None
            social_style_filter = request.form.get("social_style_filter") or None

            if not title or not event_date:
                flash("請填寫揪團名稱與日期。", "error")
                return redirect(url_for("friend_groups.new_group"))

            cursor.execute("""
                INSERT INTO friend_groups
                    (host_user_id, title, description, location, event_date, start_time, end_time,
                     capacity, pace_filter, social_style_filter)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (user_id, title, description, location or None, event_date, start_time, end_time,
                  capacity, pace_filter, social_style_filter))
            connection.commit()
            flash("揪團已發起。", "success")
            return redirect(url_for("friend_groups.index"))
    finally:
        cursor.close(); connection.close()

    return render_template("member/friend_groups/group_new.html", pace_labels=PACE_LABELS, social_labels=SOCIAL_LABELS)


@friend_groups_bp.route("/groups/<int:group_id>")
@login_required("member")
def group_detail(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        cursor.execute("""
            SELECT g.*, u.nickname, u.full_name
            FROM friend_groups g JOIN users u ON u.user_id=g.host_user_id
            WHERE g.group_id=%s
        """, (group_id,))
        group = cursor.fetchone()
        if not group:
            flash("找不到這個揪團。", "error")
            return redirect(url_for("friend_groups.index"))

        is_host = group["host_user_id"] == user_id
        if not is_host and not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動才能查看其他人的揪團。", "error")
            return redirect(url_for("friend_groups.index"))

        cursor.execute(
            "SELECT status FROM friend_group_members WHERE group_id=%s AND user_id=%s",
            (group_id, user_id)
        )
        my_membership = cursor.fetchone()

        cursor.execute("""
            SELECT m.*, u.nickname, u.full_name
            FROM friend_group_members m JOIN users u ON u.user_id=m.user_id
            WHERE m.group_id=%s AND m.status='approved'
            ORDER BY m.responded_at
        """, (group_id,))
        members = cursor.fetchall()
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/group_detail.html",
        group=group, is_host=is_host, my_membership=my_membership, members=members,
    )


@friend_groups_bp.route("/groups/<int:group_id>/apply", methods=["POST"])
@login_required("member")
def apply_group(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        if not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動才能加入揪團。", "error")
            return redirect(url_for("friend_groups.index"))

        cursor.execute("SELECT * FROM friend_groups WHERE group_id=%s AND status='open'", (group_id,))
        group = cursor.fetchone()
        if not group:
            flash("找不到這個揪團，或已關閉。", "error")
            return redirect(url_for("friend_groups.index"))
        if group["host_user_id"] == user_id:
            flash("你是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.group_detail", group_id=group_id))

        cursor.execute(
            """INSERT INTO friend_group_members (group_id, user_id) VALUES (%s,%s)
               ON DUPLICATE KEY UPDATE status='pending', applied_at=NOW(), responded_at=NULL""",
            (group_id, user_id)
        )
        cursor.execute("SELECT nickname, full_name FROM users WHERE user_id=%s", (user_id,))
        applicant = cursor.fetchone()
        cursor.execute(
            "INSERT INTO notifications (user_id, notification_type, title, message, target_url) VALUES (%s,'system','有人申請加入你的揪團',%s,%s)",
            (group["host_user_id"],
             f"{applicant['nickname'] or applicant['full_name']} 申請加入「{group['title']}」，去審核一下吧。",
             url_for("friend_groups.manage_group", group_id=group_id))
        )
        connection.commit()
        flash("已送出申請，等待團主審核。", "success")
    except Exception:
        connection.rollback(); flash("申請失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.group_detail", group_id=group_id))


@friend_groups_bp.route("/groups/<int:group_id>/manage")
@login_required("member")
def manage_group(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("找不到這個揪團，或你不是團主。", "error")
            return redirect(url_for("friend_groups.index"))

        cursor.execute("""
            SELECT m.*, u.nickname, u.full_name
            FROM friend_group_members m JOIN users u ON u.user_id=m.user_id
            WHERE m.group_id=%s
            ORDER BY FIELD(m.status,'pending','approved','rejected','left'), m.applied_at
        """, (group_id,))
        members = cursor.fetchall()
    finally:
        cursor.close(); connection.close()

    return render_template("member/friend_groups/group_manage.html", group=group, members=members)


@friend_groups_bp.route("/groups/<int:group_id>/members/<int:member_user_id>/approve", methods=["POST"])
@login_required("member")
def approve_group_member(group_id, member_user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id, title, capacity FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index"))

        if group["capacity"]:
            cursor.execute(
                "SELECT COUNT(*) AS c FROM friend_group_members WHERE group_id=%s AND status='approved'",
                (group_id,)
            )
            if cursor.fetchone()["c"] >= group["capacity"]:
                flash("這個揪團人數已滿。", "error")
                return redirect(url_for("friend_groups.manage_group", group_id=group_id))

        cursor.execute(
            "UPDATE friend_group_members SET status='approved', responded_at=NOW() WHERE group_id=%s AND user_id=%s",
            (group_id, member_user_id)
        )
        cursor.execute(
            "INSERT INTO notifications (user_id, notification_type, title, message, target_url) VALUES (%s,'system','揪團申請已通過',%s,%s)",
            (member_user_id, f"你申請加入的「{group['title']}」已經通過審核！",
             url_for("friend_groups.group_detail", group_id=group_id))
        )
        connection.commit()
        flash("已通過這位成員的申請。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.manage_group", group_id=group_id))


@friend_groups_bp.route("/groups/<int:group_id>/members/<int:member_user_id>/reject", methods=["POST"])
@login_required("member")
def reject_group_member(group_id, member_user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index"))

        cursor.execute(
            "UPDATE friend_group_members SET status='rejected', responded_at=NOW() WHERE group_id=%s AND user_id=%s",
            (group_id, member_user_id)
        )
        connection.commit()
        flash("已婉拒這位成員的申請。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.manage_group", group_id=group_id))


@friend_groups_bp.route("/groups/<int:group_id>/cancel", methods=["POST"])
@login_required("member")
def cancel_group(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index"))
        cursor.execute("UPDATE friend_groups SET status='cancelled' WHERE group_id=%s", (group_id,))
        connection.commit()
        flash("揪團已取消。", "success")
    except Exception:
        connection.rollback(); flash("取消失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.index"))
