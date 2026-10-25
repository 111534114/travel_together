from datetime import date, datetime
import secrets

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from auth import login_required
from blueprints.member import ISSUE_PREFIX, ISSUE_REASONS, _city_matches_country
from db import get_db_connection
from utils import get_cities, get_countries

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
        # 交友揪團要能追溯到真人，所以沒綁定 LINE 的會員一律擋下，導回首頁顯示綁定提示。
        if not _has_line_bound(cursor, session["user_id"]):
            flash("請先綁定 LINE 帳號，才能使用交友揪團功能。", "error")
            return redirect(url_for("friend_groups.index"))
    finally:
        cursor.close()
        connection.close()
    return None


def _has_line_bound(cursor, user_id):
    cursor.execute("SELECT line_sub FROM users WHERE user_id=%s", (user_id,))
    row = cursor.fetchone()
    return bool(row and row["line_sub"])


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
        "SELECT COUNT(*) AS c FROM friend_groups WHERE host_user_id=%s AND status != 'cancelled' AND event_date < CURDATE()",
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


@friend_groups_bp.route("/")
@login_required("member")
def index():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        friend_group_on = _feature_enabled(cursor)
        application = None
        unlocked = False
        profile = None
        events = []
        my_groups = []
        tier = None
        onboarding_done = False

        # 依行程找旅伴只列出公開行程，避免曝光私人多人行程的資料。
        cursor.execute("""
            SELECT t.trip_id, t.owner_id, t.trip_name, t.visibility, co.name AS country, ci.name AS city,
                   t.people_count, t.total_budget, t.currency, t.introduction, t.allow_copy,
                   u.full_name AS owner_name, u.nickname AS owner_nickname,
                   DATEDIFF(t.end_date, t.start_date) + 1 AS days_count,
                   COUNT(tm.user_id) AS joined_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            LEFT JOIN trip_members tm ON tm.trip_id = t.trip_id AND tm.join_status = 'accepted'
            WHERE t.visibility = 'public'
              AND t.moderation_status = 'visible' AND t.deleted_at IS NULL
            GROUP BY t.trip_id, t.owner_id, t.trip_name, t.visibility, co.name, ci.name, t.people_count,
                     t.total_budget, t.currency, t.introduction, t.allow_copy, u.full_name, u.nickname
            ORDER BY t.trip_id DESC
        """)
        companions = cursor.fetchall()

        cursor.execute("SELECT trip_id FROM favorites WHERE user_id=%s AND target_type='trip'", (user_id,))
        favorite_trip_ids = {row["trip_id"] for row in cursor.fetchall()}
        for comp in companions:
            comp["is_favorited"] = comp["trip_id"] in favorite_trip_ids

        line_bound = _has_line_bound(cursor, user_id)
        if friend_group_on and line_bound:
            application = _latest_application(cursor, user_id)

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
        companions=companions,
    )


@friend_groups_bp.route("/companions/<int:trip_id>")
@login_required("member")
def companion_trip_detail(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
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
            return redirect(url_for("friend_groups.index"))

        cursor.execute("""
            SELECT itinerary_date, title, start_time, end_time, address, estimated_cost
            FROM itineraries WHERE trip_id=%s ORDER BY itinerary_date ASC, start_time ASC
        """, (trip_id,))
        itinerary = cursor.fetchall()

        is_owner = trip["owner_id"] == user_id
        cursor.execute("SELECT join_status FROM trip_members WHERE trip_id=%s AND user_id=%s", (trip_id, user_id))
        membership = cursor.fetchone()
        member_status = membership["join_status"] if membership else None

        cursor.execute("SELECT trip_id FROM favorites WHERE user_id=%s AND trip_id=%s AND target_type='trip'", (user_id, trip_id))
        is_favorited = cursor.fetchone() is not None

        cursor.execute("""
            SELECT 1 FROM reports WHERE reporter_id=%s AND target_type='trip' AND target_id=%s
              AND reason LIKE %s AND status IN ('pending','processing')
        """, (user_id, trip_id, ISSUE_PREFIX + "%"))
        already_reported = cursor.fetchone() is not None

        can_apply = (not is_owner) and member_status not in ("accepted", "requested") and _can_use_groups(cursor, user_id)
        needs_official_event = (not is_owner) and member_status not in ("accepted", "requested") and not _can_use_groups(cursor, user_id)
        can_issue = (not is_owner) and not already_reported
    finally:
        cursor.close(); connection.close()
    return render_template(
        "member/friend_groups/companion_trip.html",
        trip=trip, itinerary=itinerary, is_owner=is_owner, member_status=member_status,
        is_favorited=is_favorited, can_apply=can_apply, needs_official_event=needs_official_event,
        can_issue=can_issue, issue_reasons=ISSUE_REASONS,
    )


@friend_groups_bp.route("/companions/<int:trip_id>/apply", methods=["POST"])
@login_required("member")
def apply_companion_trip(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        cursor.execute("""
            SELECT trip_id, owner_id, trip_name FROM trips
            WHERE trip_id=%s AND visibility='public'
              AND moderation_status='visible' AND deleted_at IS NULL
        """, (trip_id,))
        trip = cursor.fetchone()
        if not trip:
            flash("找不到這個行程，或行程目前不公開。", "error")
            return redirect(url_for("friend_groups.index"))
        if trip["owner_id"] == user_id:
            flash("這是你自己的行程。", "error")
            return redirect(url_for("friend_groups.companion_trip_detail", trip_id=trip_id))

        if not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動，才能申請加入其他會員的行程。", "error")
            return redirect(url_for("friend_groups.companion_trip_detail", trip_id=trip_id))

        cursor.execute("SELECT join_status FROM trip_members WHERE trip_id=%s AND user_id=%s", (trip_id, user_id))
        membership = cursor.fetchone()
        if membership and membership["join_status"] in ("accepted", "requested"):
            flash("你已經是成員，或已經送出過申請了。", "error")
            return redirect(url_for("friend_groups.companion_trip_detail", trip_id=trip_id))

        note = request.form.get("note", "").strip()[:300]
        cursor.execute("""
            INSERT INTO trip_members (trip_id, user_id, member_role, join_status)
            VALUES (%s,%s,'viewer','requested')
            ON DUPLICATE KEY UPDATE join_status='requested', member_role='viewer', joined_at=NULL
        """, (trip_id, user_id))
        cursor.execute(
            "INSERT INTO notifications (user_id, notification_type, title, message, target_url) "
            "VALUES (%s,'system','有人想加入你的行程',%s,%s)",
            (trip["owner_id"], f"有會員申請加入「{trip['trip_name']}」" + (f"：{note}" if note else ""),
             url_for("member.trip_detail", trip_id=trip_id))
        )
        connection.commit()
        flash("申請已送出，等待對方審核。", "success")
    except Exception as error:
        connection.rollback()
        print("申請加入行程失敗：", error)
        flash("申請失敗，請再試一次。", "error")
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
            cursor.execute(
                "INSERT INTO notifications (user_id, notification_type, title, message, target_url) "
                "VALUES (%s,'system','🏅 解鎖「新手開團者」徽章','你已完成新手開團引導，現在可以發起你的第一個交友揪團了！',%s)",
                (user_id, url_for("friend_groups.new_group"))
            )
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

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            location = request.form.get("location", "").strip()
            event_date = request.form.get("event_date", "").strip()
            end_date = request.form.get("end_date", "").strip() or None
            start_time = request.form.get("start_time") or None
            end_time = request.form.get("end_time") or None
            capacity_raw = request.form.get("capacity", "").strip()
            description = request.form.get("description", "").strip() or None
            pace_filter = request.form.get("pace_filter") or None
            social_style_filter = request.form.get("social_style_filter") or None
            country_id = request.form.get("country_id") or None
            city_id = request.form.get("city_id") or None

            if not title or not event_date:
                flash("請填寫揪團名稱與日期。", "error")
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

            # 每個揪團都同步建立一個關聯的「行程」，讓團長可以直接沿用行程既有的每日行程、聊天室、記帳分帳功能，
            # 不用再為揪團另外做一套；這個行程預設不公開，避免跟「依行程找旅伴」的瀏覽清單混在一起。
            cursor.execute("""
                INSERT INTO trips (owner_id, trip_name, country_id, city_id, start_date, end_date, people_count,
                                    introduction, visibility, status, share_token)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'private','planning',%s)
            """, (user_id, title, country_id, city_id, event_date, end_date or event_date,
                  capacity or 2, description, secrets.token_urlsafe(16)))
            trip_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())",
                (trip_id, user_id)
            )

            cursor.execute("""
                INSERT INTO friend_groups
                    (trip_id, host_user_id, title, description, location, event_date, end_date, start_time, end_time,
                     capacity, pace_filter, social_style_filter)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (trip_id, user_id, title, description, location or None, event_date, end_date, start_time, end_time,
                  capacity, pace_filter, social_style_filter))
            connection.commit()
            flash("揪團已發起，也幫你建立了對應的行程，可以開始排每日行程、用聊天室跟記帳分帳。", "success")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/group_new.html", pace_labels=PACE_LABELS, social_labels=SOCIAL_LABELS,
        tier=tier, countries=countries, cities=cities,
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
        if not is_host and not _can_use_groups(cursor, user_id):
            flash("要先出席過一場官方活動才能查看其他人的揪團。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

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

        host_tier = _host_tier(cursor, group["host_user_id"])
        is_approved_member = bool(my_membership and my_membership["status"] == "approved")
        event_finished = group["event_date"] < date.today()
        can_review = event_finished and (is_host or is_approved_member)
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/friend_groups/group_detail.html",
        group=group, is_host=is_host, my_membership=my_membership, members=members,
        host_tier=host_tier, can_review=can_review, event_finished=event_finished,
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
        if group["event_date"] >= date.today():
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


@friend_groups_bp.route("/groups/<int:group_id>/members/<int:member_user_id>/approve", methods=["POST"])
@login_required("member")
def approve_group_member(group_id, member_user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id, title, capacity, trip_id FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

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
        if group["trip_id"]:
            cursor.execute(
                "INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'viewer','accepted',NOW()) "
                "ON DUPLICATE KEY UPDATE join_status='accepted', joined_at=NOW()",
                (group["trip_id"], member_user_id)
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
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")

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
    if connection is None: return redirect(url_for("friend_groups.index") + "#friend-groups")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT host_user_id FROM friend_groups WHERE group_id=%s", (group_id,))
        group = cursor.fetchone()
        if not group or group["host_user_id"] != session["user_id"]:
            flash("你不是這個揪團的團主。", "error")
            return redirect(url_for("friend_groups.index") + "#friend-groups")
        cursor.execute("UPDATE friend_groups SET status='cancelled' WHERE group_id=%s", (group_id,))
        connection.commit()
        flash("揪團已取消。", "success")
    except Exception:
        connection.rollback(); flash("取消失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("friend_groups.index") + "#friend-groups")
