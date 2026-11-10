from datetime import date, datetime, timedelta
import json
import os
import re
import secrets

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for

from auth import login_required
from blueprints.member import ISSUE_PREFIX, ISSUE_REASONS, _city_matches_country
from db import get_db_connection
from notification_preferences import send_notification
from utils import get_cities, get_countries
from group_ai_planner import generate_plan, normalize_plan
from chat_moderation import blocked_term
from config import ANTHROPIC_API_KEY, GEMINI_API_KEY

friend_groups_bp = Blueprint("friend_groups", __name__, url_prefix="/member/friend-groups")

MIN_AGE = 18  # 申請這個功能的最低年齡限制

# 分級團長制度：Lv.1 新手團長剛解鎖時限制單日、限人數；累積開團次數達標且平均評價夠高才會升到 Lv.2 資深團長，
# 可以開多天行程、人數上限也解除。等級不另外存欄位，每次都用「開團次數」+「收到的平均評價」即時算出。
TIER1_MAX_CAPACITY = 6
TIER2_HOSTED_REQUIRED = 3
TIER2_RATING_REQUIRED = 4.5
TIER_LABELS = {1: "新手團長", 2: "資深團長"}

# 雙向評價可選的標籤，團長、團員互評時都可以勾選
REVIEW_TAGS = ["準時好夥伴", "超會拍照", "氣氛帶動王", "熱心助人", "好相處", "溝通順暢", "守時可靠", "旅伴首選"]

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


@friend_groups_bp.before_request
def _block_when_feature_disabled():
    # 總開關關閉時，整個藍圖下的路由一律擋下（除了首頁）；避免像「發起揪團」這種動作型路由
    # 漏掉檢查，導致資料寫進去了、重導回首頁才被擋下，前後兩則訊息同時出現造成誤解。
    # 首頁現在同時顯示「依行程找旅伴」區塊，不受這個總開關管控，所以要放行，讓 index() 自己決定
    # 交友揪團那個區塊要不要顯示「尚未開放」。
    if session.get("role") != "member" or request.endpoint in {
        "friend_groups.index",
        "friend_groups.companion_trip_detail",
        "friend_groups.apply_companion_trip",
        "friend_groups.leave_companion_trip",
        "friend_groups.ai_plan",
        "friend_groups.save_ai_plan",
    }:
        return None
    connection = get_db_connection()
    if connection is None:
        return None
    cursor = connection.cursor(dictionary=True)
    try:
        if not _feature_enabled(cursor):
            flash("交友揪團功能目前尚未開放。", "error")
            return redirect(url_for("member.dashboard"))
        if request.endpoint != "friend_groups.group_detail" and not _has_line_bound(cursor, session["user_id"]):
            flash("請先綁定 LINE 帳號，才能使用交友揪團功能。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
    finally:
        cursor.close()
        connection.close()
    return None


def _has_line_bound(cursor, user_id):
    cursor.execute("SELECT line_sub FROM users WHERE user_id=%s", (user_id,))
    row = cursor.fetchone()
    return bool(row and row["line_sub"])


def _registration_deadline(cursor, group):
    cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                   (f"friend_group_deadline_{group['group_id']}",))
    row = cursor.fetchone()
    group["registration_lead_days"] = int(row["setting_value"]) if row and row["setting_value"] in ("2", "3") else 2
    return group["event_date"] - timedelta(days=group["registration_lead_days"])


def _latest_application(cursor, user_id):
    cursor.execute(
        "SELECT * FROM friend_group_applications WHERE user_id=%s ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    return cursor.fetchone()


def _has_attended_event(cursor, user_id):
    # 報到（status='attended'）只代表活動當天有到場簽到，活動本身是否已經結束是另一回事；
    # 要等活動日期真的過了，才算真正「參加完」一場官方活動，避免有人一簽到就馬上去開自己的揪團。
    cursor.execute(
        """SELECT 1 FROM friend_group_event_participants p
           JOIN friend_group_events e ON e.event_id = p.event_id
           WHERE p.user_id=%s AND p.status='attended' AND e.event_date < CURDATE() LIMIT 1""",
        (user_id,)
    )
    return cursor.fetchone() is not None


def _can_use_groups(cursor, user_id):
    application = _latest_application(cursor, user_id)
    if not application or application["status"] != "approved":
        return False
    return _has_attended_event(cursor, user_id)


def _has_completed_onboarding(cursor, user_id):
    cursor.execute("SELECT 1 FROM friend_group_onboarding WHERE user_id=%s", (user_id,))
    return cursor.fetchone() is not None


def _traveler_profile(cursor, user_id):
    cursor.execute("SELECT * FROM traveler_profiles WHERE user_id=%s", (user_id,))
    return cursor.fetchone()


def _host_tier(cursor, user_id):
    """算出這個人目前的團長等級：Lv.2 資深團長要「累積開團次數」跟「當團長收到的平均評價」都達標，
    不然都是 Lv.1 新手團長；順便回傳人數上限、能不能排多天，給開團表單跟驗證共用。"""
    cursor.execute(
        "SELECT COUNT(*) AS c FROM friend_groups WHERE host_user_id=%s AND status != 'cancelled' AND COALESCE(end_date,event_date) < CURDATE()",
        (user_id,)
    )
    hosted_count = cursor.fetchone()["c"]

    cursor.execute(
        """SELECT AVG(r.rating) AS avg_rating, COUNT(*) AS review_count
           FROM friend_group_reviews r JOIN friend_groups g ON g.group_id = r.group_id
           WHERE r.reviewee_id=%s AND g.host_user_id=%s""",
        (user_id, user_id)
    )
    row = cursor.fetchone()
    avg_rating = float(row["avg_rating"]) if row["avg_rating"] is not None else None
    review_count = row["review_count"] or 0

    level = 2 if (hosted_count >= TIER2_HOSTED_REQUIRED and avg_rating is not None and avg_rating >= TIER2_RATING_REQUIRED) else 1
    return {
        "level": level,
        "label": TIER_LABELS[level],
        "hosted_count": hosted_count,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "max_capacity": None if level == 2 else TIER1_MAX_CAPACITY,
        "allow_multi_day": level == 2,
        "hosted_required": TIER2_HOSTED_REQUIRED,
        "rating_required": TIER2_RATING_REQUIRED,
    }


def _review_targets(cursor, group, user_id):
    """回傳這個人在這個揪團裡可以評價的對象：團長評每一位已通過的團員；團員只評團長一個人。"""
    if group["host_user_id"] == user_id:
        cursor.execute(
            """SELECT u.user_id, u.nickname, u.full_name FROM friend_group_members m
               JOIN users u ON u.user_id = m.user_id
               WHERE m.group_id=%s AND m.status='approved' ORDER BY m.responded_at""",
            (group["group_id"],)
        )
        return cursor.fetchall()
    cursor.execute("SELECT user_id, nickname, full_name FROM users WHERE user_id=%s", (group["host_user_id"],))
    row = cursor.fetchone()
    return [row] if row else []


def _active_group_access(cursor, group_id, user_id):
    cursor.execute("SELECT * FROM friend_groups WHERE group_id=%s", (group_id,))
    group = cursor.fetchone()
    if not group:
        return None
    if group["host_user_id"] == user_id:
        return group
    cursor.execute("""
        SELECT 1 FROM friend_group_members m
        LEFT JOIN trip_members tm ON tm.trip_id=%s AND tm.user_id=m.user_id
        WHERE m.group_id=%s AND m.user_id=%s AND m.status='approved'
          AND (%s IS NULL OR tm.join_status='accepted')
    """, (group["trip_id"], group_id, user_id, group["trip_id"]))
    return group if cursor.fetchone() else None


@friend_groups_bp.route("/")
@login_required("member")
def index():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        friend_group_on = _feature_enabled(cursor)
        line_bound = False
        application = None
        unlocked = False
        profile = None
        events = []
        my_groups = []
        browse_groups = []
        tier = None
        onboarding_done = False
        filters = {
            "region": request.args.get("region", "").strip()[:80],
            "date": request.args.get("date", "").strip(),
            "budget": request.args.get("budget", "").strip(),
            "available": request.args.get("available") == "1",
        }

        max_budget = float(filters["budget"]) if filters["budget"].isdigit() else None
        def matches_filters(row, start_key="start_date", end_key="end_date", capacity_key="people_count", count_key="joined_count"):
            if filters["region"] and filters["region"].casefold() not in f"{row.get('country') or ''} {row.get('city') or ''} {row.get('location') or ''} {row.get('title') or ''} {row.get('description') or ''}".casefold():
                return False
            if filters["date"] and not (str(row.get(start_key) or "") <= filters["date"] <= str(row.get(end_key) or row.get(start_key) or "")):
                return False
            if max_budget is not None and float(row.get("total_budget") or 0) > max_budget:
                return False
            if filters["available"] and row.get(capacity_key) and row.get(count_key, 0) >= row[capacity_key]:
                return False
            return True
        if friend_group_on:
            line_bound = _has_line_bound(cursor, user_id)
            if line_bound:
                application = _latest_application(cursor, user_id)

            # 瀏覽公開招募的揪團不需要先完成官方活動；加入時仍由 apply_group 驗證資格。
            cursor.execute("""
                SELECT g.*, u.nickname, u.full_name, co.name AS country, ci.name AS city,
                       t.total_budget, t.currency,
                       (SELECT COUNT(*) FROM friend_group_members m WHERE m.group_id=g.group_id AND m.status='approved') AS member_count,
                       (SELECT status FROM friend_group_members m WHERE m.group_id=g.group_id AND m.user_id=%s) AS my_status
                FROM friend_groups g JOIN users u ON u.user_id=g.host_user_id
                LEFT JOIN trips t ON t.trip_id=g.trip_id
                LEFT JOIN countries co ON co.country_id=t.country_id
                LEFT JOIN cities ci ON ci.city_id=t.city_id
                WHERE g.status='open' AND g.host_user_id != %s
                ORDER BY g.event_date ASC
            """, (user_id, user_id))
            browse_groups = [g for g in cursor.fetchall() if matches_filters(g, "event_date", "end_date", "capacity", "member_count")]

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

            if events:
                event_ids = [e["event_id"] for e in events]
                format_strings = ",".join(["%s"] * len(event_ids))
                cursor.execute(f"""
                    SELECT * FROM friend_group_event_items
                    WHERE event_id IN ({format_strings})
                    ORDER BY event_id, sort_order
                """, tuple(event_ids))
                items_by_event = {}
                for item in cursor.fetchall():
                    items_by_event.setdefault(item["event_id"], []).append(item)
                for e in events:
                    e["schedule"] = items_by_event.get(e["event_id"], [])

            if unlocked:
                cursor.execute("""
                    SELECT g.*,
                           (SELECT COUNT(*) FROM friend_group_members m WHERE m.group_id=g.group_id AND m.status='approved') AS member_count,
                           (SELECT COUNT(*) FROM friend_group_members m WHERE m.group_id=g.group_id AND m.status='pending') AS pending_count
                    FROM friend_groups g
                    WHERE g.host_user_id=%s
                    ORDER BY g.created_at DESC
                """, (user_id,))
                my_groups = cursor.fetchall()
                tier = _host_tier(cursor, user_id)
                onboarding_done = _has_completed_onboarding(cursor, user_id)
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/index.html",
        friend_group_on=friend_group_on, line_bound=line_bound,
        application=application, unlocked=unlocked, profile=profile, tier=tier,
        events=events, my_groups=my_groups, onboarding_done=onboarding_done,
        browse_groups=browse_groups, filters=filters,
    )


@friend_groups_bp.route("/companions/<int:trip_id>")
@login_required("member")
def companion_trip_detail(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.public_trips"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        cursor.execute("""
            SELECT t.trip_id, t.owner_id, t.trip_name, t.visibility, co.name AS country, ci.name AS city,
                   t.start_date, t.end_date, t.people_count, t.total_budget, t.currency, t.introduction,
                   t.allow_copy, u.full_name AS owner_name, u.nickname AS owner_nickname,
                   DATEDIFF(t.end_date, t.start_date) + 1 AS days_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE t.trip_id=%s AND t.visibility='public'
              AND t.moderation_status='visible' AND t.deleted_at IS NULL
        """, (trip_id,))
        trip = cursor.fetchone()
        if not trip:
            flash("找不到這個行程，或行程目前不公開。", "error")
            return redirect(url_for("member.public_trips"))

        cursor.execute("""
            SELECT itinerary_date, title, start_time, end_time, address, estimated_cost
            FROM itineraries WHERE trip_id=%s ORDER BY itinerary_date ASC, start_time ASC
        """, (trip_id,))
        itinerary = cursor.fetchall()

        is_owner = trip["owner_id"] == user_id
        cursor.execute("SELECT join_status FROM trip_members WHERE trip_id=%s AND user_id=%s", (trip_id, user_id))
        membership = cursor.fetchone()
        member_status = membership["join_status"] if membership else None
        cursor.execute("SELECT COUNT(*) AS c FROM trip_members WHERE trip_id=%s AND join_status='accepted'", (trip_id,))
        joined_count = cursor.fetchone()["c"]

        cursor.execute("SELECT trip_id FROM favorites WHERE user_id=%s AND trip_id=%s AND target_type='trip'", (user_id, trip_id))
        is_favorited = cursor.fetchone() is not None

        cursor.execute("""
            SELECT 1 FROM reports WHERE reporter_id=%s AND target_type='trip' AND target_id=%s
              AND reason LIKE %s AND status IN ('pending','processing')
        """, (user_id, trip_id, ISSUE_PREFIX + "%"))
        already_reported = cursor.fetchone() is not None

        can_issue = (not is_owner) and not already_reported
    finally:
        cursor.close(); connection.close()
    return render_template(
        "member/friend_groups/companion_trip.html",
        trip=trip, itinerary=itinerary, is_owner=is_owner, member_status=member_status,
        joined_count=joined_count, is_favorited=is_favorited,
        can_issue=can_issue, issue_reasons=ISSUE_REASONS,
    )


@friend_groups_bp.route("/companions/<int:trip_id>/apply", methods=["POST"])
@login_required("member")
def apply_companion_trip(trip_id):
    flash("公開行程僅供瀏覽，無法申請加入。想參加揪團請到「依行程找旅伴」。", "error")
    return redirect(url_for("friend_groups.companion_trip_detail", trip_id=trip_id))


@friend_groups_bp.route("/companions/<int:trip_id>/leave", methods=["POST"])
@login_required("member")
def leave_companion_trip(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.public_trips"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT owner_id, trip_name FROM trips WHERE trip_id=%s AND deleted_at IS NULL", (trip_id,))
        trip = cursor.fetchone()
        if not trip or trip["owner_id"] == session["user_id"]:
            flash("無法退出這個行程。", "error")
            return redirect(url_for("member.public_trips"))
        cursor.execute("SELECT join_status FROM trip_members WHERE trip_id=%s AND user_id=%s", (trip_id, session["user_id"]))
        membership = cursor.fetchone()
        if not membership or membership["join_status"] not in ("requested", "accepted"):
            flash("你目前沒有待審核或已加入的資格。", "error")
            return redirect(url_for("friend_groups.companion_trip_detail", trip_id=trip_id))
        cursor.execute("UPDATE trip_members SET join_status='left' WHERE trip_id=%s AND user_id=%s", (trip_id, session["user_id"]))
        send_notification(cursor, trip["owner_id"], "trip", "trip_update", "旅伴退出行程",
                          f"有旅伴{'撤回申請' if membership['join_status'] == 'requested' else '退出'}「{trip['trip_name']}」。",
                          url_for("member.trip_detail", trip_id=trip_id), trip_id=trip_id)
        connection.commit()
        flash("已撤回申請。" if membership["join_status"] == "requested" else "已退出行程，聊天室權限已停止。", "success")
    except Exception as error:
        connection.rollback(); print("退出公開行程失敗：", error); flash("操作失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.companion_trip_detail", trip_id=trip_id))


@friend_groups_bp.route("/apply", methods=["POST"])
@login_required("member")
def apply():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        application = _latest_application(cursor, user_id)
        if application and application["status"] in ("pending", "approved"):
            flash("你已經申請過了。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        birthdate_raw = request.form.get("birthdate", "").strip()
        note = request.form.get("note", "").strip()
        if not birthdate_raw:
            flash("請填寫生日。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        try:
            birthdate = datetime.strptime(birthdate_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("生日格式不正確。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        today = date.today()
        if birthdate > today:
            flash("生日不能是未來的日期。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        if age < MIN_AGE:
            flash(f"這個功能限 {MIN_AGE} 歲以上會員申請。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

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
    return redirect(url_for("friend_groups.index") + "#friend-groups")


@friend_groups_bp.route("/questionnaire", methods=["GET", "POST"])
@login_required("member")
def questionnaire():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        application = _latest_application(cursor, user_id)
        if not application or application["status"] != "approved":
            flash("要先通過申請才能填問卷。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        if request.method == "POST":
            pace = request.form.get("pace")
            social_style = request.form.get("social_style")
            budget_style = request.form.get("budget_style", "moderate")
            diet = request.form.get("diet", "none")
            transport_pref = request.form.get("transport_pref", "any")
            walk_tolerance = request.form.get("walk_tolerance", "medium")
            like_activities = ",".join(request.form.getlist("like_activities"))
            dislike_activities = ",".join(request.form.getlist("dislike_activities"))
            public_intro = request.form.get("public_intro", "").strip()[:500]
            is_public = 1 if request.form.get("is_public") == "1" else 0

            if pace not in PACE_LABELS or social_style not in SOCIAL_LABELS:
                flash("請完整填寫問卷。", "error")
                return redirect(url_for("friend_groups.questionnaire"))

            traveler_type = TRAVELER_TYPE_NAMES.get((pace, social_style), "旅人")

            cursor.execute("""
                INSERT INTO traveler_profiles
                    (user_id, pace, social_style, budget_style, like_activities, dislike_activities,
                     diet, transport_pref, walk_tolerance, traveler_type, public_intro, is_public)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    pace=VALUES(pace), social_style=VALUES(social_style), budget_style=VALUES(budget_style),
                    like_activities=VALUES(like_activities), dislike_activities=VALUES(dislike_activities),
                    diet=VALUES(diet), transport_pref=VALUES(transport_pref), walk_tolerance=VALUES(walk_tolerance),
                    traveler_type=VALUES(traveler_type), public_intro=VALUES(public_intro), is_public=VALUES(is_public)
            """, (user_id, pace, social_style, budget_style, like_activities or None, dislike_activities or None,
                  diet, transport_pref, walk_tolerance, traveler_type, public_intro or None, is_public))
            connection.commit()
            flash(f"問卷已送出！你的旅遊人格是「{traveler_type}」。", "success")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

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
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        application = _latest_application(cursor, user_id)
        if not application or application["status"] != "approved":
            flash("要先通過申請才能報名活動。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        cursor.execute("SELECT * FROM friend_group_events WHERE event_id=%s AND status='open'", (event_id,))
        event = cursor.fetchone()
        if not event:
            flash("找不到這場活動，或活動已關閉。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        if event["capacity"]:
            cursor.execute(
                "SELECT COUNT(*) AS c FROM friend_group_event_participants WHERE event_id=%s AND status IN ('registered','attended')",
                (event_id,)
            )
            if cursor.fetchone()["c"] >= event["capacity"]:
                flash("這場活動人數已滿。", "error")
                return redirect(url_for("friend_groups.index") + "#friend-groups")

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
    return redirect(url_for("friend_groups.index") + "#friend-groups")


@friend_groups_bp.route("/events/<int:event_id>/cancel", methods=["POST"])
@login_required("member")
def cancel_event(event_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
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
    return redirect(url_for("friend_groups.index") + "#friend-groups")


def _event_participant_status(cursor, event_id, user_id):
    cursor.execute("SELECT status FROM friend_group_event_participants WHERE event_id=%s AND user_id=%s", (event_id, user_id))
    row = cursor.fetchone()
    return row["status"] if row else None


@friend_groups_bp.route("/events/<int:event_id>")
@login_required("member")
def event_detail(event_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        cursor.execute("""
            SELECT e.*,
                   (SELECT COUNT(*) FROM friend_group_event_participants p WHERE p.event_id=e.event_id AND p.status IN ('registered','attended')) AS registered_count
            FROM friend_group_events e WHERE e.event_id=%s
        """, (event_id,))
        event = cursor.fetchone()
        if not event:
            flash("找不到這場活動。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        cursor.execute("SELECT * FROM friend_group_event_items WHERE event_id=%s ORDER BY sort_order", (event_id,))
        schedule = cursor.fetchall()

        cursor.execute("""
            SELECT a.*, u.nickname, u.full_name FROM friend_group_event_announcements a
            JOIN users u ON u.user_id = a.posted_by
            WHERE a.event_id=%s ORDER BY a.created_at DESC
        """, (event_id,))
        announcements = cursor.fetchall()

        my_status = _event_participant_status(cursor, event_id, user_id)
        can_chat = my_status in ("registered", "attended")
    finally:
        cursor.close(); connection.close()
    return render_template(
        "member/friend_groups/event_detail.html",
        event=event, schedule=schedule, announcements=announcements,
        my_status=my_status, can_chat=can_chat,
    )


@friend_groups_bp.route("/events/<int:event_id>/chat")
@login_required("member")
def event_chat_feed(event_id):
    connection = get_db_connection()
    if connection is None: return jsonify(error="資料庫連線失敗"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        if _event_participant_status(cursor, event_id, user_id) not in ("registered", "attended"):
            return jsonify(error="你沒有這場活動的聊天權限。"), 403
        after = request.args.get("after", "0")
        after = int(after) if after.isdigit() else 0
        cursor.execute("""
            SELECT m.message_id, m.user_id, m.content, m.created_at, u.nickname, u.full_name
            FROM friend_group_event_chat_messages m JOIN users u ON u.user_id = m.user_id
            WHERE m.event_id=%s AND m.message_id > %s ORDER BY m.message_id ASC
        """, (event_id, after))
        messages = [{
            "id": row["message_id"], "user_id": row["user_id"],
            "name": row["nickname"] or row["full_name"],
            "content": row["content"], "created_at": row["created_at"].strftime("%H:%M"),
        } for row in cursor.fetchall()]
    finally:
        cursor.close(); connection.close()
    return jsonify(messages=messages)


@friend_groups_bp.route("/events/<int:event_id>/chat", methods=["POST"])
@login_required("member")
def event_chat_send(event_id):
    connection = get_db_connection()
    if connection is None: return jsonify(error="資料庫連線失敗"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        if _event_participant_status(cursor, event_id, user_id) not in ("registered", "attended"):
            return jsonify(error="你沒有這場活動的聊天權限。"), 403
        payload = request.get_json(silent=True)
        content = payload.get("content") if isinstance(payload, dict) else None
        content = content.strip() if isinstance(content, str) else ""
        if not content or len(content) > 1000:
            return jsonify(error="訊息不能是空的，且不能超過 1000 字。"), 400
        if blocked_term(cursor, content):
            return jsonify(error="訊息包含禁止內容，請修改後再送出。"), 400
        cursor.execute("INSERT INTO friend_group_event_chat_messages (event_id, user_id, content) VALUES (%s,%s,%s)", (event_id, user_id, content))
        connection.commit()
    finally:
        cursor.close(); connection.close()
    return jsonify(ok=True)


@friend_groups_bp.route("/onboarding", methods=["GET", "POST"])
@login_required("member")
def onboarding():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        if not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動才能使用這個功能。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        if _has_completed_onboarding(cursor, user_id):
            flash("你已經完成過新手開團引導了。", "success")
            return redirect(url_for("friend_groups.new_group"))

        if request.method == "POST":
            acknowledged = all(request.form.get(key) == "on" for key in ("ack_rules", "ack_disclaimer", "ack_safety"))
            if not acknowledged:
                flash("請詳閱並勾選全部三個項目才能完成引導。", "error")
                return redirect(url_for("friend_groups.onboarding"))

            cursor.execute(
                "INSERT INTO friend_group_onboarding (user_id, completed_at) VALUES (%s, NOW()) "
                "ON DUPLICATE KEY UPDATE completed_at=NOW()",
                (user_id,)
            )
            send_notification(cursor, user_id, "friend_group", "system", "🏅 解鎖「新手開團者」徽章",
                              "你已完成新手開團引導，現在可以發起你的第一個交友揪團了！",
                              url_for("friend_groups.new_group"))
            connection.commit()
            flash("新手開團引導已完成，獲得「新手開團者」徽章！", "success")
            return redirect(url_for("friend_groups.new_group"))
    finally:
        cursor.close(); connection.close()
    return render_template("member/friend_groups/onboarding.html")


@friend_groups_bp.route("/groups/browse")
@login_required("member")
def browse_groups():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        if not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動才能瀏覽其他會員的揪團。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        cursor.execute("""
            SELECT g.*, u.nickname, u.full_name,
                   (SELECT COUNT(*) FROM friend_group_members m WHERE m.group_id=g.group_id AND m.status='approved') AS member_count,
                   (SELECT status FROM friend_group_members m WHERE m.group_id=g.group_id AND m.user_id=%s) AS my_status
            FROM friend_groups g JOIN users u ON u.user_id=g.host_user_id
            WHERE g.status='open' AND g.host_user_id != %s
            ORDER BY g.event_date ASC
        """, (user_id, user_id))
        groups = cursor.fetchall()
        for g in groups:  # 附上每個揪團團主目前的等級，瀏覽時可以參考
            g["host_tier"] = _host_tier(cursor, g["host_user_id"])
    finally:
        cursor.close(); connection.close()
    return render_template("member/friend_groups/browse_groups.html", groups=groups)


@friend_groups_bp.route("/groups/new", methods=["GET", "POST"])
@login_required("member")
def new_group():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        if not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動才能發起揪團。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        if not _has_completed_onboarding(cursor, user_id):
            flash("發起揪團前，請先完成新手開團引導。", "error")
            return redirect(url_for("friend_groups.onboarding"))

        tier = _host_tier(cursor, user_id)
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.start_date, t.end_date, t.country_id, t.city_id,
                   t.total_budget, t.people_count
            FROM trips t WHERE t.owner_id=%s AND t.deleted_at IS NULL
              AND t.status != 'cancelled' AND t.visibility='private'
              AND NOT EXISTS (SELECT 1 FROM friend_groups g WHERE g.trip_id=t.trip_id AND g.status != 'cancelled')
              AND NOT EXISTS (SELECT 1 FROM trip_members tm WHERE tm.trip_id=t.trip_id AND tm.user_id != %s AND tm.join_status='accepted')
              AND NOT EXISTS (SELECT 1 FROM trip_invitations ti WHERE ti.trip_id=t.trip_id AND ti.status='pending')
            ORDER BY t.start_date DESC
        """, (user_id, user_id))
        own_trips = cursor.fetchall()

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            location = request.form.get("location", "").strip()
            event_date = request.form.get("event_date", "").strip()
            end_date = request.form.get("end_date", "").strip() or None
            start_time = request.form.get("start_time") or None
            end_time = request.form.get("end_time") or None
            capacity_raw = request.form.get("capacity", "").strip()
            lead_raw = request.form.get("registration_lead_days", "2")
            description = request.form.get("description", "").strip() or None
            pace_filter = request.form.get("pace_filter") or None
            social_style_filter = request.form.get("social_style_filter") or None
            country_id = request.form.get("country_id") or None
            city_id = request.form.get("city_id") or None
            existing_trip_id = request.form.get("existing_trip_id", "").strip()
            show_member_list = 1 if request.form.get("show_member_list") == "1" else 0

            linked_trip = None
            if existing_trip_id:
                if not existing_trip_id.isdigit():
                    flash("請選擇有效的既有行程。", "error")
                    return redirect(url_for("friend_groups.new_group"))
                cursor.execute("""
                    SELECT t.* FROM trips t WHERE t.trip_id=%s AND t.owner_id=%s
                      AND t.deleted_at IS NULL AND t.status != 'cancelled' AND t.visibility='private'
                      AND NOT EXISTS (SELECT 1 FROM friend_groups g WHERE g.trip_id=t.trip_id AND g.status != 'cancelled')
                      AND NOT EXISTS (SELECT 1 FROM trip_members tm WHERE tm.trip_id=t.trip_id AND tm.user_id != %s AND tm.join_status='accepted')
                      AND NOT EXISTS (SELECT 1 FROM trip_invitations ti WHERE ti.trip_id=t.trip_id AND ti.status='pending')
                """, (int(existing_trip_id), user_id, user_id))
                linked_trip = cursor.fetchone()
                if not linked_trip:
                    flash("這個行程無法用來開團，請選擇自己尚未開團的行程。", "error")
                    return redirect(url_for("friend_groups.new_group"))
                country_id, city_id = linked_trip["country_id"], linked_trip["city_id"]
                event_date, end_date = str(linked_trip["start_date"]), str(linked_trip["end_date"])
                title = title or linked_trip["trip_name"]

            if not title or not event_date:
                flash("請填寫揪團名稱與日期。", "error")
                return redirect(url_for("friend_groups.new_group"))
            try:
                start_day = date.fromisoformat(event_date)
                finish_day = date.fromisoformat(end_date or event_date)
            except ValueError:
                flash("日期格式不正確。", "error")
                return redirect(url_for("friend_groups.new_group"))
            if start_day < date.today() or finish_day < start_day:
                flash("揪團日期不能是過去，結束日期也不能早於開始日期。", "error")
                return redirect(url_for("friend_groups.new_group"))
            if lead_raw not in ("2", "3"):
                flash("請選擇提前 2 天或 3 天截止報名。", "error")
                return redirect(url_for("friend_groups.new_group"))
            if start_day - timedelta(days=int(lead_raw)) < date.today():
                flash("報名截止日不能早於今天，請選擇較晚的開始日期。", "error")
                return redirect(url_for("friend_groups.new_group"))
            if not country_id or not city_id:
                flash("請選擇目的地國家與城市，系統會同步建立一個對應的行程給這個揪團使用。", "error")
                return redirect(url_for("friend_groups.new_group"))
            if not _city_matches_country(cursor, country_id, city_id):
                flash("所選城市不屬於該國家，請重新選擇。", "error")
                return redirect(url_for("friend_groups.new_group"))

            # Lv.1 新手團長限制單日、人數上限；Lv.2 資深團長才能排多天行程、人數不設限
            if not tier["allow_multi_day"]:
                if end_date and end_date != event_date:
                    flash(f"你目前是 Lv.1 新手團長，只能開單日的揪團；累積辦滿 {tier['hosted_required']} 次、平均評價達 {tier['rating_required']} 顆星以上即可升級成 Lv.2 資深團長，開放多天行程。", "error")
                    return redirect(url_for("friend_groups.new_group"))
                end_date = None
                if not capacity_raw:
                    capacity = tier["max_capacity"]
                else:
                    try:
                        capacity = int(capacity_raw)
                    except ValueError:
                        flash("人數上限請輸入數字。", "error")
                        return redirect(url_for("friend_groups.new_group"))
                    if capacity <= 0 or capacity > tier["max_capacity"]:
                        flash(f"你目前是 Lv.1 新手團長，人數上限最多 {tier['max_capacity']} 人。", "error")
                        return redirect(url_for("friend_groups.new_group"))
            else:
                if end_date and end_date < event_date:
                    flash("結束日期不能早於開始日期。", "error")
                    return redirect(url_for("friend_groups.new_group"))
                capacity = int(capacity_raw) if capacity_raw.isdigit() and int(capacity_raw) > 0 else None

            if linked_trip:
                trip_id = linked_trip["trip_id"]
                if capacity:
                    cursor.execute("UPDATE trips SET people_count=%s WHERE trip_id=%s AND owner_id=%s",
                                   (capacity + 1, trip_id, user_id))
                cursor.execute("""
                    INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at)
                    VALUES (%s,%s,'owner','accepted',NOW())
                    ON DUPLICATE KEY UPDATE member_role='owner', join_status='accepted'
                """, (trip_id, user_id))
            else:
                # 將新揪團連到私人行程；找團頁會直接讀揪團，不需要公開私人行程。
                cursor.execute("""
                    INSERT INTO trips (owner_id, trip_name, country_id, city_id, start_date, end_date, people_count,
                                        introduction, visibility, status, share_token)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'private','planning',%s)
                """, (user_id, title, country_id, city_id, event_date, end_date or event_date,
                      (capacity + 1) if capacity else 2, description, secrets.token_urlsafe(16)))
                trip_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())",
                    (trip_id, user_id)
                )

            cursor.execute("""
                INSERT INTO friend_groups
                    (trip_id, host_user_id, title, description, location, event_date, end_date, start_time, end_time,
                     capacity, pace_filter, social_style_filter, show_member_list)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (trip_id, user_id, title, description, location or None, event_date, end_date, start_time, end_time,
                  capacity, pace_filter, social_style_filter, show_member_list))
            cursor.execute("""INSERT INTO app_settings (setting_key,setting_value,updated_by) VALUES (%s,%s,%s)""",
                           (f"friend_group_deadline_{cursor.lastrowid}", lead_raw, user_id))
            connection.commit()
            flash("揪團已發起，其他會員可在「參加別人的行程」看到；行程頁可排每日行程及使用聊天室。", "success")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/group_new.html", pace_labels=PACE_LABELS, social_labels=SOCIAL_LABELS,
        tier=tier, countries=countries, cities=cities, own_trips=own_trips,
    )


@friend_groups_bp.route("/groups/<int:group_id>")
@login_required("member")
def group_detail(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
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
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        is_host = group["host_user_id"] == user_id
        cursor.execute(
            "SELECT status, show_profile FROM friend_group_members WHERE group_id=%s AND user_id=%s",
            (group_id, user_id)
        )
        my_membership = cursor.fetchone()
        if group["status"] != "open" and not is_host and not (my_membership and my_membership["status"] == "approved"):
            flash("這個揪團目前沒有開放瀏覽。", "error")
            return redirect(url_for("friend_groups.index") + "#companions")
        registration_deadline = _registration_deadline(cursor, group)
        can_apply = (not is_host and group["status"] == "open" and date.today() <= registration_deadline
                     and _has_line_bound(cursor, user_id) and _can_use_groups(cursor, user_id))

        cursor.execute("""
            SELECT m.*, u.nickname, u.avatar_path, p.is_public
            FROM friend_group_members m JOIN users u ON u.user_id=m.user_id
            LEFT JOIN traveler_profiles p ON p.user_id=m.user_id
            WHERE m.group_id=%s AND m.status='approved'
            ORDER BY m.responded_at
        """, (group_id,))
        all_members = cursor.fetchall()
        total_members = len(all_members)

        host_tier = _host_tier(cursor, group["host_user_id"])
        is_approved_member = bool(my_membership and my_membership["status"] == "approved")
        can_view_members = is_host or is_approved_member or bool(group["show_member_list"])
        members = [m for m in all_members if is_host or (can_view_members and m["show_profile"])]
        itinerary = []
        if group["trip_id"]:
            cursor.execute("""
                SELECT itinerary_date, title, item_type, start_time, end_time, address
                FROM itineraries WHERE trip_id=%s ORDER BY itinerary_date, sort_order, start_time
            """, (group["trip_id"],))
            itinerary = cursor.fetchall()
        event_finished = (group["end_date"] or group["event_date"]) < date.today()
        can_review = event_finished and (is_host or is_approved_member)
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/group_detail.html",
        group=group, is_host=is_host, my_membership=my_membership, members=members,
        total_members=total_members, can_view_members=can_view_members, itinerary=itinerary,
        host_tier=host_tier, can_review=can_review, event_finished=event_finished,
        can_apply=can_apply, registration_deadline=registration_deadline, today=date.today(),
    )


@friend_groups_bp.route("/groups/<int:group_id>/reviews", methods=["GET", "POST"])
@login_required("member")
def group_reviews(group_id):
    """雙向評價（盲評）：團長評每位團員、團員評團長；雙方都評完了才會看到對方寫的內容，
    避免有人為了報復亂給負評。活動日期要過了才能互評。"""
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        cursor.execute("SELECT * FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group:
            flash("找不到這個揪團。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        is_host = group["host_user_id"] == user_id
        cursor.execute(
            "SELECT status FROM friend_group_members WHERE group_id=%s AND user_id=%s",
            (group_id, user_id)
        )
        membership = cursor.fetchone()
        is_approved_member = bool(membership and membership["status"] == "approved")

        if not is_host and not is_approved_member:
            flash("只有團長跟已通過審核的團員才能互評。", "error")
            return redirect(url_for("friend_groups.group_detail", group_id=group_id))
        if (group["end_date"] or group["event_date"]) >= date.today():
            flash("活動結束後才能互評。", "error")
            return redirect(url_for("friend_groups.group_detail", group_id=group_id))

        targets = _review_targets(cursor, group, user_id)

        if request.method == "POST":
            reviewee_id = request.form.get("reviewee_id", "").strip()
            rating = request.form.get("rating", "").strip()
            tags = ",".join(request.form.getlist("tags"))
            comment = request.form.get("comment", "").strip() or None

            valid_target_ids = {t["user_id"] for t in targets}
            if not reviewee_id.isdigit() or int(reviewee_id) not in valid_target_ids:
                flash("評價對象不正確。", "error")
            elif rating not in ("1", "2", "3", "4", "5"):
                flash("請選擇 1～5 顆星的評分。", "error")
            else:
                cursor.execute(
                    """INSERT INTO friend_group_reviews (group_id, reviewer_id, reviewee_id, rating, tags, comment)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE rating=VALUES(rating), tags=VALUES(tags), comment=VALUES(comment)""",
                    (group_id, user_id, int(reviewee_id), int(rating), tags or None, comment)
                )
                connection.commit()
                flash("評價已送出，等對方也評價你之後就能互相看到內容。", "success")
            return redirect(url_for("friend_groups.group_reviews", group_id=group_id))

        cursor.execute(
            "SELECT reviewee_id, rating, tags, comment FROM friend_group_reviews WHERE group_id=%s AND reviewer_id=%s",
            (group_id, user_id)
        )
        my_reviews = {r["reviewee_id"]: r for r in cursor.fetchall()}

        cursor.execute(
            """SELECT r.reviewer_id, r.rating, r.tags, r.comment, u.nickname, u.full_name
               FROM friend_group_reviews r JOIN users u ON u.user_id=r.reviewer_id
               WHERE r.group_id=%s AND r.reviewee_id=%s""",
            (group_id, user_id)
        )
        received_raw = {r["reviewer_id"]: r for r in cursor.fetchall()}
        # 盲評：只有「我評過這個人」而且「這個人也評過我」才看得到對方寫的內容，避免互相觀望、抄來抄去
        received_visible = {rid: r for rid, r in received_raw.items() if rid in my_reviews}
        received_pending_count = len(received_raw) - len(received_visible)
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/group_reviews.html",
        group=group, is_host=is_host, targets=targets, my_reviews=my_reviews,
        received_visible=received_visible, received_pending_count=received_pending_count,
        review_tags=REVIEW_TAGS,
    )


@friend_groups_bp.route("/groups/<int:group_id>/apply", methods=["POST"])
@login_required("member")
def apply_group(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        if not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動才能加入揪團。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        cursor.execute("SELECT * FROM friend_groups WHERE group_id=%s AND status='open'", (group_id,))
        group = cursor.fetchone()
        if not group:
            flash("找不到這個揪團，或已關閉。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        if date.today() > _registration_deadline(cursor, group):
            flash("這個揪團已截止報名。", "error")
            return redirect(url_for("friend_groups.group_detail", group_id=group_id))
        if group["host_user_id"] == user_id:
            flash("你是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.group_detail", group_id=group_id))

        cursor.execute("SELECT status FROM friend_group_members WHERE group_id=%s AND user_id=%s", (group_id, user_id))
        existing = cursor.fetchone()
        if existing and existing["status"] in ("pending", "approved"):
            flash("你已經送出申請，或已經加入這個揪團。", "error")
            return redirect(url_for("friend_groups.group_detail", group_id=group_id))
        if group["capacity"]:
            cursor.execute("SELECT COUNT(*) AS c FROM friend_group_members WHERE group_id=%s AND status='approved'", (group_id,))
            if cursor.fetchone()["c"] >= group["capacity"]:
                flash("這個揪團已額滿。", "error")
                return redirect(url_for("friend_groups.group_detail", group_id=group_id))

        cursor.execute(
            """INSERT INTO friend_group_members (group_id, user_id, application_note) VALUES (%s,%s,%s)
               ON DUPLICATE KEY UPDATE status='pending', application_note=VALUES(application_note),
                 applied_at=NOW(), responded_at=NULL""",
            (group_id, user_id, request.form.get("note", "").strip()[:300] or None)
        )
        cursor.execute("SELECT nickname, full_name FROM users WHERE user_id=%s", (user_id,))
        applicant = cursor.fetchone()
        send_notification(cursor, group["host_user_id"], "friend_group", "system", "有人申請加入你的揪團",
                          f"{applicant['nickname'] or applicant['full_name']} 申請加入「{group['title']}」，去審核一下吧。",
                          url_for("friend_groups.manage_group", group_id=group_id))
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
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("找不到這個揪團，或你不是團主。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

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


@friend_groups_bp.route("/groups/<int:group_id>/permissions")
@login_required("member")
def group_permissions(group_id):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT g.group_id, g.host_user_id, g.trip_id, g.title, t.owner_id AS trip_owner_id
            FROM friend_groups g LEFT JOIN trips t ON t.trip_id=g.trip_id
            WHERE g.group_id=%s
        """, (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("只有這個揪團的主揪可以設定團員權限。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        if group["trip_id"] and group["trip_owner_id"] != session["user_id"]:
            flash("只有行程建立者可以設定行程成員權限。", "error")
            return redirect(url_for("friend_groups.manage_group", group_id=group_id))

        members = []
        if group["trip_id"]:
            cursor.execute("""
                SELECT m.user_id, u.nickname, u.full_name, u.avatar_path, tm.member_role
                FROM friend_group_members m
                JOIN users u ON u.user_id=m.user_id
                JOIN trip_members tm ON tm.trip_id=%s AND tm.user_id=m.user_id
                WHERE m.group_id=%s AND m.status='approved'
                  AND tm.join_status='accepted' AND tm.member_role IN ('viewer','editor')
                ORDER BY m.responded_at, m.user_id
            """, (group["trip_id"], group_id))
            members = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
    return render_template("member/friend_groups/group_permissions.html", group=group, members=members)


@friend_groups_bp.route("/groups/<int:group_id>/permissions/<int:member_user_id>", methods=["POST"])
@login_required("member")
def save_group_permission(group_id, member_user_id):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT g.host_user_id, g.trip_id, t.owner_id AS trip_owner_id
            FROM friend_groups g LEFT JOIN trips t ON t.trip_id=g.trip_id
            WHERE g.group_id=%s
        """, (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("只有這個揪團的主揪可以設定團員權限。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        if group["trip_id"] and group["trip_owner_id"] != session["user_id"]:
            flash("只有行程建立者可以設定行程成員權限。", "error")
            return redirect(url_for("friend_groups.manage_group", group_id=group_id))

        new_role = request.form.get("member_role", "")
        if new_role not in ("viewer", "editor") or not group["trip_id"]:
            flash("請選擇有效的成員權限。", "error")
            return redirect(url_for("friend_groups.group_permissions", group_id=group_id))

        cursor.execute("""
            SELECT tm.trip_member_id
            FROM friend_group_members m
            JOIN trip_members tm ON tm.trip_id=%s AND tm.user_id=m.user_id
            WHERE m.group_id=%s AND m.user_id=%s AND m.status='approved'
              AND tm.join_status='accepted' AND tm.member_role IN ('viewer','editor')
            FOR UPDATE
        """, (group["trip_id"], group_id, member_user_id))
        member = cursor.fetchone()
        if not member:
            flash("找不到這位已加入的團員。", "error")
            return redirect(url_for("friend_groups.group_permissions", group_id=group_id))

        cursor.execute("UPDATE trip_members SET member_role=%s WHERE trip_member_id=%s", (new_role, member["trip_member_id"]))
        connection.commit()
        flash("已更新團員權限。", "success")
    except Exception:
        connection.rollback()
        current_app.logger.exception("更新揪團團員權限失敗 group_id=%s", group_id)
        flash("更新團員權限失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("friend_groups.group_permissions", group_id=group_id))


@friend_groups_bp.route("/groups/<int:group_id>/members/<int:member_user_id>/approve", methods=["POST"])
@login_required("member")
def approve_group_member(group_id, member_user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id, title, capacity, trip_id, status FROM friend_groups WHERE group_id=%s FOR UPDATE", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        if group["status"] != "open":
            flash("這個揪團目前沒有開放招募。", "error")
            return redirect(url_for("friend_groups.manage_group", group_id=group_id))
        cursor.execute("SELECT status FROM friend_group_members WHERE group_id=%s AND user_id=%s", (group_id, member_user_id))
        applicant = cursor.fetchone()
        if not applicant or applicant["status"] != "pending":
            flash("這筆申請已處理或已撤回。", "error")
            return redirect(url_for("friend_groups.manage_group", group_id=group_id))

        if group["capacity"]:
            cursor.execute(
                "SELECT COUNT(*) AS c FROM friend_group_members WHERE group_id=%s AND status='approved'",
                (group_id,)
            )
            if cursor.fetchone()["c"] >= group["capacity"]:
                flash("這個揪團人數已滿。", "error")
                return redirect(url_for("friend_groups.manage_group", group_id=group_id))

        cursor.execute(
            "UPDATE friend_group_members SET status='approved', responded_at=NOW() WHERE group_id=%s AND user_id=%s AND status='pending'",
            (group_id, member_user_id)
        )
        if not cursor.rowcount:
            connection.rollback()
            flash("這筆申請已撤回，無法核准。", "error")
            return redirect(url_for("friend_groups.manage_group", group_id=group_id))
        if group["trip_id"]:
            cursor.execute(
                "INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'viewer','accepted',NOW()) "
                "ON DUPLICATE KEY UPDATE member_role='viewer', join_status='accepted', joined_at=NOW()",
                (group["trip_id"], member_user_id)
            )
        send_notification(cursor, member_user_id, "friend_group", "system", "揪團申請已通過",
                          f"你申請加入的「{group['title']}」已經通過審核！",
                          url_for("friend_groups.group_detail", group_id=group_id))
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
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id, title FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

        cursor.execute(
            "UPDATE friend_group_members SET status='rejected', responded_at=NOW() WHERE group_id=%s AND user_id=%s AND status='pending'",
            (group_id, member_user_id)
        )
        if cursor.rowcount:
            send_notification(cursor, member_user_id, "friend_group", "system", "揪團申請未通過",
                              f"你申請的「{group['title']}」這次未通過審核。", url_for("friend_groups.group_detail", group_id=group_id))
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
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id, title FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        cursor.execute("UPDATE friend_groups SET status='cancelled' WHERE group_id=%s", (group_id,))
        cursor.execute("SELECT user_id FROM friend_group_members WHERE group_id=%s AND status='approved'", (group_id,))
        for member in cursor.fetchall():
            send_notification(cursor, member["user_id"], "friend_group", "system", "揪團已取消",
                              f"「{group['title']}」已由團主取消。", url_for("friend_groups.group_detail", group_id=group_id))
        connection.commit()
        flash("揪團已取消。", "success")
    except Exception:
        connection.rollback(); flash("取消失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.index") + "#friend-groups")


@friend_groups_bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@login_required("member")
def edit_group(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM friend_groups WHERE group_id=%s" + (" FOR UPDATE" if request.method == "POST" else ""), (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("只有團主可以修改揪團。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        if request.method == "GET":
            _registration_deadline(cursor, group)
            return render_template("member/friend_groups/group_edit.html", group=group)
        if group["status"] == "cancelled":
            flash("已取消的揪團不能修改。", "error")
            return redirect(url_for("friend_groups.manage_group", group_id=group_id))
        title = request.form.get("title", "").strip()[:150]
        description = request.form.get("description", "").strip()[:2000]
        location = request.form.get("location", "").strip()[:255]
        meeting_info = request.form.get("meeting_info", "").strip()[:1000]
        start_raw = request.form.get("event_date", "").strip()
        end_raw = request.form.get("end_date", "").strip() or start_raw
        capacity_raw = request.form.get("capacity", "").strip()
        lead_raw = request.form.get("registration_lead_days", "2")
        status = request.form.get("status", "open")
        if group["moderation_locked"] and status == "open":
            raise ValueError("此揪團已由管理員暫停招募，不能自行重新開放。")
        if not title or status not in ("open", "closed"):
            raise ValueError("請填寫名稱並選擇有效的招募狀態。")
        try:
            start_date = date.fromisoformat(start_raw)
            end_date = date.fromisoformat(end_raw)
        except ValueError as error:
            raise ValueError("請填寫有效日期。") from error
        if end_date < start_date:
            raise ValueError("結束日期不能早於開始日期。")
        if lead_raw not in ("2", "3"):
            raise ValueError("請選擇提前 2 天或 3 天截止報名。")
        if status == "open" and start_date - timedelta(days=int(lead_raw)) < date.today():
            raise ValueError("報名截止日已過，請選擇較晚的開始日期或暫停招募。")
        tier = _host_tier(cursor, session["user_id"])
        if not tier["allow_multi_day"] and end_date != start_date:
            raise ValueError("新手團長只能開單日揪團。")
        if capacity_raw and (not capacity_raw.isdigit() or int(capacity_raw) < 1):
            raise ValueError("人數上限必須是正整數。")
        capacity = int(capacity_raw) if capacity_raw else None
        if not tier["allow_multi_day"] and (capacity is None or capacity > TIER1_MAX_CAPACITY):
            raise ValueError(f"新手團長人數上限須為 1～{TIER1_MAX_CAPACITY} 人。")
        cursor.execute("SELECT COUNT(*) AS c FROM friend_group_members WHERE group_id=%s AND status='approved'", (group_id,))
        if capacity and capacity < cursor.fetchone()["c"]:
            raise ValueError("人數上限不能小於已加入的人數。")
        if group["trip_id"]:
            cursor.execute("""
                SELECT 1 FROM itineraries WHERE trip_id=%s AND (itinerary_date < %s OR itinerary_date > %s) LIMIT 1
            """, (group["trip_id"], start_date, end_date))
            if cursor.fetchone():
                raise ValueError("行程中有日期超出新範圍的項目，請先調整每日行程。")
        _registration_deadline(cursor, group)
        changed = (title != group["title"] or location != (group["location"] or "")
                   or start_date != group["event_date"] or end_date != (group["end_date"] or group["event_date"])
                   or status != group["status"] or meeting_info != (group["meeting_info"] or "")
                   or int(lead_raw) != (group.get("registration_lead_days") or 2))
        cursor.execute("""
            UPDATE friend_groups SET title=%s, description=%s, location=%s, meeting_info=%s,
              event_date=%s, end_date=%s, capacity=%s, status=%s, show_member_list=%s
            WHERE group_id=%s
        """, (title, description or None, location or None, meeting_info or None,
              start_date, end_date, capacity, status, 1 if request.form.get("show_member_list") == "1" else 0, group_id))
        cursor.execute("""INSERT INTO app_settings (setting_key,setting_value,updated_by) VALUES (%s,%s,%s)
                          ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value), updated_by=VALUES(updated_by)""",
                       (f"friend_group_deadline_{group_id}", lead_raw, session["user_id"]))
        if group["trip_id"]:
            cursor.execute("""
                UPDATE trips SET trip_name=%s, start_date=%s, end_date=%s, people_count=%s
                WHERE trip_id=%s AND owner_id=%s
            """, (title, start_date, end_date, (capacity + 1) if capacity else max(2, (group["capacity"] or 1) + 1),
                  group["trip_id"], session["user_id"]))
        if changed:
            cursor.execute("SELECT user_id FROM friend_group_members WHERE group_id=%s AND status='approved'", (group_id,))
            for member in cursor.fetchall():
                send_notification(cursor, member["user_id"], "friend_group", "system", "揪團資訊有異動",
                                  f"「{title}」的日期、地點或招募資訊已更新，請重新查看。",
                                  url_for("friend_groups.group_detail", group_id=group_id))
        connection.commit()
        flash("揪團資料已更新。", "success")
    except ValueError as error:
        connection.rollback()
        flash(str(error), "error")
    except Exception as error:
        connection.rollback()
        print("修改揪團失敗：", error)
        flash("修改失敗，請確認資料庫已執行揪團功能遷移檔。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.manage_group", group_id=group_id))


@friend_groups_bp.route("/groups/<int:group_id>/leave", methods=["POST"])
@login_required("member")
def leave_group(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT group_id, trip_id, host_user_id, title FROM friend_groups WHERE group_id=%s FOR UPDATE", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] == session["user_id"]:
            flash("找不到可退出的揪團。", "error")
            return redirect(url_for("friend_groups.index"))
        cursor.execute("SELECT status FROM friend_group_members WHERE group_id=%s AND user_id=%s", (group_id, session["user_id"]))
        membership = cursor.fetchone()
        if not membership or membership["status"] not in ("pending", "approved"):
            flash("你目前沒有待審核或已加入的資格。", "error")
            return redirect(url_for("friend_groups.group_detail", group_id=group_id))
        cursor.execute("UPDATE friend_group_members SET status='left', show_profile=0, responded_at=NOW() WHERE group_id=%s AND user_id=%s",
                       (group_id, session["user_id"]))
        if membership["status"] == "approved" and group["trip_id"]:
            cursor.execute("UPDATE trip_members SET join_status='left' WHERE trip_id=%s AND user_id=%s AND member_role != 'owner'",
                           (group["trip_id"], session["user_id"]))
        send_notification(cursor, group["host_user_id"], "friend_group", "system", "揪團成員退出",
                          f"有成員{'撤回申請' if membership['status'] == 'pending' else '退出'}「{group['title']}」。",
                          url_for("friend_groups.manage_group", group_id=group_id))
        connection.commit()
        flash("已撤回申請。" if membership["status"] == "pending" else "已退出揪團，行程和聊天室權限已移除。", "success")
    except Exception as error:
        connection.rollback(); print("退出揪團失敗：", error); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.group_detail", group_id=group_id))


@friend_groups_bp.route("/groups/<int:group_id>/members/<int:member_user_id>/remove", methods=["POST"])
@login_required("member")
def remove_group_member(group_id, member_user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id, trip_id, title FROM friend_groups WHERE group_id=%s FOR UPDATE", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("只有團主可以移除成員。", "error")
            return redirect(url_for("friend_groups.index"))
        cursor.execute("UPDATE friend_group_members SET status='left', show_profile=0, responded_at=NOW() WHERE group_id=%s AND user_id=%s AND status='approved'",
                       (group_id, member_user_id))
        if not cursor.rowcount:
            flash("找不到已加入的成員。", "error")
            return redirect(url_for("friend_groups.manage_group", group_id=group_id))
        if group["trip_id"]:
            cursor.execute("UPDATE trip_members SET join_status='removed' WHERE trip_id=%s AND user_id=%s AND member_role != 'owner'",
                           (group["trip_id"], member_user_id))
        send_notification(cursor, member_user_id, "friend_group", "system", "已被移出揪團",
                          f"你已被移出「{group['title']}」，行程與聊天室權限已停止。", url_for("friend_groups.index"))
        connection.commit()
        flash("已移除成員與相關權限。", "success")
    except Exception as error:
        connection.rollback(); print("移除揪團成員失敗：", error); flash("操作失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.manage_group", group_id=group_id))


@friend_groups_bp.route("/groups/<int:group_id>/visibility", methods=["POST"])
@login_required("member")
def set_member_visibility(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            UPDATE friend_group_members SET show_profile=%s
            WHERE group_id=%s AND user_id=%s AND status='approved'
        """, (1 if request.form.get("show_profile") == "1" else 0, group_id, session["user_id"]))
        if cursor.rowcount:
            connection.commit(); flash("已更新本團名單顯示設定。", "success")
        else:
            flash("只有已加入的團員能修改此設定。", "error")
    except Exception as error:
        connection.rollback(); print("修改名單隱私失敗：", error); flash("設定失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.group_detail", group_id=group_id))


@friend_groups_bp.route("/travelers/<int:user_id>")
@login_required("member")
def public_profile(user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        if user_id != session["user_id"] and not _can_use_groups(cursor, session["user_id"]):
            flash("完成官方活動後才能查看其他旅伴的簡介。", "error")
            return redirect(url_for("friend_groups.index"))
        cursor.execute("""
            SELECT u.user_id, u.nickname, u.avatar_path, p.pace, p.social_style,
                   p.budget_style, p.traveler_type, p.public_intro, p.is_public
            FROM users u JOIN traveler_profiles p ON p.user_id=u.user_id
            WHERE u.user_id=%s AND u.role='member' AND u.status='active'
        """, (user_id,))
        profile = cursor.fetchone()
        if not profile or (not profile["is_public"] and user_id != session["user_id"]):
            flash("這位旅伴尚未公開個人簡介。", "error")
            return redirect(url_for("friend_groups.index"))
    finally:
        cursor.close(); connection.close()
    return render_template("member/friend_groups/public_profile.html", profile=profile,
                           pace_labels=PACE_LABELS, social_labels=SOCIAL_LABELS, budget_labels=BUDGET_LABELS)


@friend_groups_bp.route("/groups/<int:group_id>/trip-reviews", methods=["GET", "POST"])
@login_required("member")
def trip_reviews(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        group = _active_group_access(cursor, group_id, session["user_id"])
        if not group:
            flash("只有目前的團員可以查看或撰寫行程心得。", "error")
            return redirect(url_for("friend_groups.index"))
        if (group["end_date"] or group["event_date"]) >= date.today():
            flash("旅行結束後才能撰寫行程心得。", "error")
            return redirect(url_for("friend_groups.group_detail", group_id=group_id))
        if request.method == "POST":
            rating = request.form.get("rating", "")
            comment = request.form.get("comment", "").strip()[:1000]
            if rating not in ("1", "2", "3", "4", "5"):
                flash("請選擇 1～5 顆星。", "error")
            else:
                cursor.execute("""
                    INSERT INTO friend_group_trip_reviews (group_id,user_id,rating,comment)
                    VALUES (%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE rating=VALUES(rating), comment=VALUES(comment)
                """, (group_id, session["user_id"], int(rating), comment or None))
                connection.commit(); flash("行程心得已儲存。", "success")
            return redirect(url_for("friend_groups.trip_reviews", group_id=group_id))
        cursor.execute("""
            SELECT r.*, u.nickname FROM friend_group_trip_reviews r
            JOIN users u ON u.user_id=r.user_id WHERE r.group_id=%s ORDER BY r.created_at DESC
        """, (group_id,))
        reviews = cursor.fetchall()
        my_review = next((r for r in reviews if r["user_id"] == session["user_id"]), None)
    finally:
        cursor.close(); connection.close()
    return render_template("member/friend_groups/trip_reviews.html", group=group, reviews=reviews, my_review=my_review)


def _group_album_path(stored_name):
    return os.path.join(current_app.instance_path, "group_album", stored_name)


def _album_image_type(raw):
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "webp"
    return None


@friend_groups_bp.route("/groups/<int:group_id>/album", methods=["GET", "POST"])
@login_required("member")
def group_album(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    saved_path = None
    try:
        group = _active_group_access(cursor, group_id, session["user_id"])
        if not group:
            flash("只有目前的團員可以查看相簿。", "error")
            return redirect(url_for("friend_groups.index"))
        if request.method == "POST":
            upload = request.files.get("photo")
            if not upload or not upload.filename:
                raise ValueError("請選擇照片。")
            raw = upload.read(5 * 1024 * 1024 + 1)
            if len(raw) > 5 * 1024 * 1024:
                raise ValueError("照片不能超過 5 MB。")
            image_type = _album_image_type(raw)
            if image_type not in ("jpeg", "png", "webp", "gif"):
                raise ValueError("請上傳有效的 JPG、PNG、WEBP 或 GIF 圖片。")
            stored_name = secrets.token_hex(20) + (".jpg" if image_type == "jpeg" else "." + image_type)
            saved_path = _group_album_path(stored_name)
            os.makedirs(os.path.dirname(saved_path), exist_ok=True)
            with open(saved_path, "wb") as image_file:
                image_file.write(raw)
            cursor.execute("""
                INSERT INTO friend_group_album_photos (group_id,uploaded_by,stored_name,caption)
                VALUES (%s,%s,%s,%s)
            """, (group_id, session["user_id"], stored_name, request.form.get("caption", "").strip()[:300] or None))
            connection.commit()
            flash("照片已加入本團相簿。", "success")
            return redirect(url_for("friend_groups.group_album", group_id=group_id))
        cursor.execute("""
            SELECT p.*, u.nickname FROM friend_group_album_photos p JOIN users u ON u.user_id=p.uploaded_by
            WHERE p.group_id=%s ORDER BY p.created_at DESC
        """, (group_id,))
        photos = cursor.fetchall()
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("friend_groups.group_album", group_id=group_id))
    except Exception as error:
        connection.rollback()
        if saved_path and os.path.isfile(saved_path): os.remove(saved_path)
        print("相簿操作失敗：", error)
        flash("相簿操作失敗，請確認已套用資料庫遷移檔。", "error")
        return redirect(url_for("friend_groups.group_detail", group_id=group_id))
    finally:
        cursor.close(); connection.close()
    return render_template("member/friend_groups/group_album.html", group=group, photos=photos)


@friend_groups_bp.route("/groups/<int:group_id>/album/<int:photo_id>/image")
@login_required("member")
def group_album_image(group_id, photo_id):
    connection = get_db_connection()
    if connection is None: return ("暫時無法讀取照片", 503)
    cursor = connection.cursor(dictionary=True)
    try:
        if not _active_group_access(cursor, group_id, session["user_id"]):
            return ("沒有權限", 403)
        cursor.execute("SELECT stored_name FROM friend_group_album_photos WHERE group_id=%s AND photo_id=%s", (group_id, photo_id))
        photo = cursor.fetchone()
        if not photo: return ("找不到照片", 404)
        if not re.fullmatch(r"[0-9a-f]{40}\.(?:jpg|png|webp|gif)", photo["stored_name"]):
            return ("找不到照片", 404)
        path = _group_album_path(photo["stored_name"])
        if not os.path.isfile(path): return ("找不到照片", 404)
        image_type = os.path.splitext(photo["stored_name"])[1].lower()
        mime = {".jpg":"image/jpeg", ".png":"image/png", ".webp":"image/webp", ".gif":"image/gif"}.get(image_type)
        if not mime: return ("不支援的照片", 404)
        response = send_file(path, mimetype=mime)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    finally:
        cursor.close(); connection.close()


@friend_groups_bp.route("/groups/<int:group_id>/report", methods=["POST"])
@login_required("member")
def report_group_content(group_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT group_id, host_user_id FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or not _can_use_groups(cursor, session["user_id"]):
            flash("無法檢舉此揪團。", "error")
            return redirect(url_for("friend_groups.index"))
        reason = request.form.get("reason", "").strip()[:255]
        description = request.form.get("description", "").strip()[:1000]
        photo_raw = request.form.get("photo_id", "").strip()
        photo_id = int(photo_raw) if photo_raw.isdigit() else None
        if not reason:
            raise ValueError("請填寫檢舉原因。")
        if photo_id:
            if not _active_group_access(cursor, group_id, session["user_id"]):
                raise ValueError("只有團員可檢舉相簿照片。")
            cursor.execute("SELECT 1 FROM friend_group_album_photos WHERE group_id=%s AND photo_id=%s", (group_id, photo_id))
            if not cursor.fetchone(): raise ValueError("找不到這張照片。")
        cursor.execute("""
            INSERT INTO friend_group_content_reports (group_id,photo_id,reporter_id,reason,description)
            VALUES (%s,%s,%s,%s,%s)
        """, (group_id, photo_id, session["user_id"], reason, description or None))
        connection.commit(); flash("檢舉已送出，將由旅遊管理員審查。", "success")
    except ValueError as error:
        flash(str(error), "error")
    except Exception as error:
        connection.rollback(); print("揪團檢舉失敗：", error); flash("檢舉失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.group_album" if request.form.get("photo_id") else "friend_groups.group_detail", group_id=group_id))


@friend_groups_bp.route("/ai-plan", methods=["GET", "POST"])
@login_required("member")
def ai_plan():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    countries = []
    cities = []
    form_values = request.form if request.method == "POST" else {}
    try:
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        if request.method == "POST":
            if not (GEMINI_API_KEY or ANTHROPIC_API_KEY):
                raise ValueError("尚未設定 AI 服務金鑰，請先在伺服器設定 GEMINI_API_KEY 或 ANTHROPIC_API_KEY。")
            country_raw = request.form.get("country_id", "")
            city_raw = request.form.get("city_id", "")
            user_request = request.form.get("user_request", "").strip()[:1000]
            try:
                start_date = date.fromisoformat(request.form.get("start_date", ""))
                end_date = date.fromisoformat(request.form.get("end_date", ""))
                people_count = int(request.form.get("people_count", "1"))
                budget = float(request.form.get("budget", "0") or 0)
            except (ValueError, TypeError) as error:
                raise ValueError("請填寫有效的日期、人數與預算。") from error
            if not country_raw.isdigit() or not city_raw.isdigit() or not _city_matches_country(cursor, country_raw, city_raw):
                raise ValueError("請選擇有效的國家與城市。")
            if start_date < date.today() or end_date < start_date or (end_date - start_date).days > 6:
                raise ValueError("AI 規劃目前支援從今天起、最多 7 天的行程。")
            if not 1 <= people_count <= 30 or not 0 <= budget <= 100_000_000 or not user_request:
                raise ValueError("請填寫需求，並確認人數與預算在有效範圍內。")
            cursor.execute("SELECT name FROM countries WHERE country_id=%s", (country_raw,))
            country = cursor.fetchone()["name"]
            cursor.execute("SELECT name FROM cities WHERE city_id=%s", (city_raw,))
            city = cursor.fetchone()["name"]
            cursor.execute("""
                SELECT COUNT(*) AS table_count FROM information_schema.tables
                WHERE table_schema=DATABASE() AND table_name='friend_group_ai_drafts'
            """)
            if not cursor.fetchone()["table_count"]:
                raise ValueError("AI 草稿資料表尚未建立，請先執行 database/migrate_1102_group_features.sql。")
            plan = generate_plan(user_request, country, city, start_date, end_date, people_count, budget)
            cursor.execute("""
                INSERT INTO friend_group_ai_drafts
                  (user_id,country_id,city_id,start_date,end_date,people_count,budget,user_request,draft_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (session["user_id"], int(country_raw), int(city_raw), start_date, end_date,
                  people_count, budget, user_request, json.dumps(plan, ensure_ascii=False)))
            draft_id = cursor.lastrowid
            connection.commit()
            return redirect(url_for("friend_groups.ai_plan", draft_id=draft_id))
        draft = None
        draft_raw = request.args.get("draft_id", "")
        if draft_raw.isdigit():
            cursor.execute("""
                SELECT * FROM friend_group_ai_drafts
                WHERE draft_id=%s AND user_id=%s AND consumed_at IS NULL
                  AND created_at >= NOW() - INTERVAL 1 DAY
            """, (int(draft_raw), session["user_id"]))
            draft = cursor.fetchone()
            if draft:
                draft["plan"] = json.loads(draft["draft_json"])
        return render_template("member/friend_groups/ai_plan.html", countries=countries, cities=cities,
                               draft=draft, ai_ready=bool(GEMINI_API_KEY or ANTHROPIC_API_KEY), form_values=form_values,
                               form_error=None)
    except ValueError as error:
        connection.rollback()
        message = str(error)
    except Exception as error:
        connection.rollback(); print("AI 規劃失敗：", error)
        message = "AI 規劃暫時失敗，請確認服務設定與資料庫遷移後再試。"
    finally:
        cursor.close(); connection.close()
    if request.method == "POST":
        return render_template("member/friend_groups/ai_plan.html", countries=countries, cities=cities,
                               draft=None, ai_ready=bool(GEMINI_API_KEY or ANTHROPIC_API_KEY), form_values=form_values,
                               form_error=message), 400
    flash(message, "error")
    return redirect(url_for("friend_groups.ai_plan"))


@friend_groups_bp.route("/ai-plan/<int:draft_id>/save", methods=["POST"])
@login_required("member")
def save_ai_plan(draft_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM friend_group_ai_drafts
            WHERE draft_id=%s AND user_id=%s AND consumed_at IS NULL
              AND created_at >= NOW() - INTERVAL 1 DAY FOR UPDATE
        """, (draft_id, session["user_id"]))
        draft = cursor.fetchone()
        if not draft:
            raise ValueError("草稿已過期、已使用，或不屬於你的帳號。")
        title = request.form.get("title", "").strip()[:150]
        if not title:
            raise ValueError("請替行程取一個名稱。")
        plan = normalize_plan(json.loads(draft["draft_json"]), draft["start_date"], draft["end_date"])
        cursor.execute("""
            INSERT INTO trips (owner_id,trip_name,country_id,city_id,start_date,end_date,
                               people_count,total_budget,introduction,visibility,status,share_token)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'private','planning',%s)
        """, (session["user_id"], title, draft["country_id"], draft["city_id"],
              draft["start_date"], draft["end_date"], draft["people_count"], draft["budget"],
              plan["summary"] or draft["user_request"], secrets.token_urlsafe(16)))
        trip_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at)
            VALUES (%s,%s,'owner','accepted',NOW())
        """, (trip_id, session["user_id"]))
        for sort_order, item in enumerate(plan["items"], 1):
            cursor.execute("""
                INSERT INTO itineraries
                  (trip_id,created_by,itinerary_date,item_type,title,start_time,address,estimated_cost,notes,sort_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (trip_id, session["user_id"], item["date"], item["type"], item["title"],
                  item["start_time"], item["address"], item["estimated_cost"], item["notes"], sort_order))
        cursor.execute("UPDATE friend_group_ai_drafts SET consumed_at=NOW() WHERE draft_id=%s", (draft_id,))
        connection.commit()
        flash("行程已存為私人行程。請逐項確認交通、住宿、價格與時間。", "success")
        return redirect(url_for("member.trip_detail", trip_id=trip_id))
    except ValueError as error:
        connection.rollback(); flash(str(error), "error")
    except Exception as error:
        connection.rollback(); print("儲存 AI 行程失敗：", error); flash("儲存失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.ai_plan", draft_id=draft_id))
