from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal, InvalidOperation
import secrets

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from auth import login_required
from db import get_db_connection
from utils import delete_uploaded_image, get_cities, get_countries, save_uploaded_attachment, save_uploaded_image
import theme_parks
import weather


member_bp = Blueprint("member", __name__, url_prefix="/member")

# item_type 的中文顯示名稱與圖示，給樣板統一用，避免畫面直接印出英文代碼(例如 free_time)
ITEM_TYPE_LABELS = {
    "attraction": {"label": "景點", "icon": "📍"},
    "restaurant": {"label": "餐廳", "icon": "🍽️"},
    "accommodation": {"label": "住宿", "icon": "🏨"},
    "transport": {"label": "交通", "icon": "🚗"},
    "shopping": {"label": "購物", "icon": "🛍️"},
    "meeting": {"label": "集合", "icon": "🤝"},
    "free_time": {"label": "自由活動", "icon": "⏱️"},
    "amusement_park": {"label": "遊樂園", "icon": "🎢"},
    "other": {"label": "其他", "icon": "📌"},
}

TIME_MODES = ("range", "all_day", "start_only", "end_only")

ISSUE_REASONS = (
    "內容品質不佳／資訊太少",
    "資訊錯誤或誤導",
    "含有不當內容（暴力、色情、仇恨言論等）",
    "疑似抄襲或未經授權使用",
    "含有個資或敏感資訊",
    "內容含有商業宣傳或廣告導流",
    "其它",
)
ISSUE_PREFIX = "問題回報："
TRIP_TRASH_DAYS = 30  # 軟刪除的行程保留天數，過期後自動永久刪除


def _connection_or_home():
    connection = get_db_connection()
    if connection is None:
        flash("目前無法連線資料庫，請稍後再試。", "error")
        return None
    return connection


def _member_access(cursor, trip_id, user_id):
    cursor.execute("""
        SELECT t.*, co.name AS country, ci.name AS city, tm.member_role, tm.join_status
        FROM trips t
        JOIN countries co ON co.country_id = t.country_id
        JOIN cities ci ON ci.city_id = t.city_id
        LEFT JOIN trip_members tm ON tm.trip_id = t.trip_id AND tm.user_id = %s
        WHERE t.trip_id = %s AND t.deleted_at IS NULL
    """, (user_id, trip_id))
    trip = cursor.fetchone()
    if not trip or trip["join_status"] != "accepted":
        return None
    return trip


def _can_edit(trip):
    return trip["member_role"] in ("owner", "editor")


def _load_votes(cursor, trip_id, user_id):
    cursor.execute("""
        SELECT v.*, u.full_name AS creator_name, u.nickname AS creator_nickname,
               (SELECT COUNT(*) FROM vote_records vr WHERE vr.vote_id=v.vote_id) AS total_votes
        FROM votes v JOIN users u ON u.user_id=v.created_by
        WHERE v.trip_id=%s ORDER BY v.created_at DESC
    """, (trip_id,))
    votes = cursor.fetchall()

    for v in votes:
        cursor.execute("""
            SELECT o.option_id, o.option_text, o.sort_order,
                   (SELECT COUNT(*) FROM vote_records vr WHERE vr.option_id=o.option_id) AS vote_count
            FROM vote_options o WHERE o.vote_id=%s ORDER BY o.sort_order
        """, (v["vote_id"],))
        v["options"] = cursor.fetchall()

        cursor.execute("SELECT user_id FROM vote_records WHERE vote_id=%s", (v["vote_id"],))
        v["voter_ids"] = [row["user_id"] for row in cursor.fetchall()]

        cursor.execute("SELECT option_id, approval_choice, reason FROM vote_records WHERE vote_id=%s AND user_id=%s", (v["vote_id"], user_id))
        my_vote = cursor.fetchone()
        v["my_option_id"] = my_vote["option_id"] if my_vote else None
        v["my_approval_choice"] = my_vote["approval_choice"] if my_vote else None
        v["my_reason"] = my_vote["reason"] if my_vote else None

        if v["vote_type"] == "approval":
            cursor.execute("""
                SELECT approval_choice, COUNT(*) AS c FROM vote_records
                WHERE vote_id=%s AND approval_choice IS NOT NULL GROUP BY approval_choice
            """, (v["vote_id"],))
            tally = {row["approval_choice"]: row["c"] for row in cursor.fetchall()}
            v["agree_count"] = tally.get("agree", 0)
            v["disagree_count"] = tally.get("disagree", 0)
            v["neutral_count"] = tally.get("neutral", 0)

            cursor.execute("""
                SELECT u.nickname, u.full_name, vr.reason FROM vote_records vr
                JOIN users u ON u.user_id = vr.user_id
                WHERE vr.vote_id=%s AND vr.approval_choice='disagree' AND vr.reason IS NOT NULL AND vr.reason != ''
                ORDER BY vr.updated_at DESC
            """, (v["vote_id"],))
            v["disagree_reasons"] = cursor.fetchall()

    return votes


def _load_comments(cursor, trip_id):
    cursor.execute("""
        SELECT c.*, u.full_name, u.nickname
        FROM comments c JOIN users u ON u.user_id = c.user_id
        WHERE c.trip_id=%s AND c.itinerary_id IS NULL AND c.proposal_id IS NULL AND c.status='visible'
        ORDER BY c.created_at ASC
    """, (trip_id,))
    rows = cursor.fetchall()

    replies_by_parent = {}
    for r in rows:
        if r["parent_comment_id"] is not None:
            replies_by_parent.setdefault(r["parent_comment_id"], []).append(r)

    top_level = [r for r in rows if r["parent_comment_id"] is None]
    for c in top_level:
        c["replies"] = replies_by_parent.get(c["comment_id"], [])

    return top_level


def _load_expenses(cursor, trip_id):
    cursor.execute("""
        SELECT e.*, u.full_name AS payer_name, u.nickname AS payer_nickname
        FROM expenses e JOIN users u ON u.user_id = e.payer_id
        WHERE e.trip_id=%s ORDER BY e.expense_date DESC, e.created_at DESC
    """, (trip_id,))
    expenses = cursor.fetchall()

    for e in expenses:
        cursor.execute("""
            SELECT es.*, u.full_name, u.nickname
            FROM expense_splits es JOIN users u ON u.user_id = es.user_id
            WHERE es.expense_id=%s ORDER BY es.user_id
        """, (e["expense_id"],))
        e["splits"] = cursor.fetchall()

        cursor.execute("SELECT * FROM expense_items WHERE expense_id=%s ORDER BY sort_order, item_id", (e["expense_id"],))
        e["items"] = cursor.fetchall()

    return expenses


RECEIPT_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}


def _parse_expense_items(form, files, default_date):
    """讀取表單裡的發票明細（日期／明細／金額／收據照片），整列空白就略過；格式錯誤時丟 ValueError。
    每列用 item_key 編號對應欄位（item_desc_3、item_receipt_3…），避免空白的檔案欄位讓列對不上。"""
    items = []
    for key in form.getlist("item_key"):
        if not key.isdigit():
            continue
        description = form.get(f"item_desc_{key}", "").strip()
        amount = form.get(f"item_amount_{key}", "").strip()
        receipt = files.get(f"item_receipt_{key}")
        if receipt is not None and not receipt.filename:
            receipt = None
        if not description and not amount and receipt is None:
            continue
        if not description:
            raise ValueError("每一列發票明細都要填寫「明細」內容。")
        try:
            amount = Decimal(amount or "0")
            if amount < 0: raise InvalidOperation
        except InvalidOperation:
            raise ValueError(f"明細「{description}」的金額格式不正確。")
        try:
            item_date = date.fromisoformat(form.get(f"item_date_{key}", "").strip() or default_date)
        except ValueError:
            raise ValueError(f"明細「{description}」的日期格式不正確。")
        if receipt is not None and receipt.filename.rsplit(".", 1)[-1].lower() not in RECEIPT_EXTENSIONS:
            raise ValueError(f"明細「{description}」的收據請上傳圖片（png、jpg、gif、webp）或 PDF。")
        items.append({"date": item_date, "description": description[:255], "amount": amount, "receipt": receipt})
    return items


def _load_attachments(cursor, trip_id):
    cursor.execute("""
        SELECT a.*, u.full_name, u.nickname
        FROM attachments a JOIN users u ON u.user_id = a.uploaded_by
        WHERE a.trip_id=%s AND a.itinerary_id IS NULL AND a.proposal_id IS NULL
        ORDER BY a.created_at DESC
    """, (trip_id,))
    return cursor.fetchall()


def _load_balance_summary(cursor, trip_id):
    cursor.execute("""
        SELECT u.user_id, u.full_name, u.nickname,
               COALESCE(SUM(CASE WHEN es.settlement_status='unpaid' THEN es.split_amount ELSE 0 END),0) AS unpaid_total
        FROM trip_members tm
        JOIN users u ON u.user_id = tm.user_id
        LEFT JOIN expense_splits es ON es.user_id = tm.user_id
            AND es.expense_id IN (SELECT expense_id FROM expenses WHERE trip_id=%s)
        WHERE tm.trip_id=%s AND tm.join_status='accepted'
        GROUP BY u.user_id, u.full_name, u.nickname
        HAVING unpaid_total > 0
        ORDER BY unpaid_total DESC
    """, (trip_id, trip_id))
    return cursor.fetchall()


def _city_matches_country(cursor, country_id, city_id):
    cursor.execute("SELECT 1 FROM cities WHERE city_id=%s AND country_id=%s", (city_id, country_id))
    return cursor.fetchone() is not None


def _parse_itinerary_time(form):
    # 時間模式：指定時段(range)／整天(all_day)／只選開始(start_only)／只選結束(end_only)
    # 依模式決定實際要存進去的 start_time / end_time，避免畫面上已經隱藏的欄位還殘留舊值被存進去
    mode = form.get("time_mode", "range")
    if mode not in TIME_MODES:
        mode = "range"
    start = form.get("start_time") or None
    end = form.get("end_time") or None
    is_all_day = False
    if mode == "all_day":
        start, end, is_all_day = None, None, True
    elif mode == "start_only":
        end = None
    elif mode == "end_only":
        start = None
    errors = []
    if start and end and end < start:
        errors.append("結束時間不能早於開始時間。")
    try:
        transport_minutes = int(form.get("transport_minutes") or 0)
        if transport_minutes < 0:
            raise ValueError
    except ValueError:
        errors.append("交通／移動時間需為 0 以上的整數分鐘。")
        transport_minutes = 0
    return start, end, is_all_day, transport_minutes, errors


def _parse_trip(form):
    values = {
        "trip_name": form.get("trip_name", "").strip(),
        "country_id": form.get("country_id", "").strip(),
        "city_id": form.get("city_id", "").strip(),
        "start_date": form.get("start_date", "").strip(),
        "end_date": form.get("end_date", "").strip(),
        "people_count": form.get("people_count", "1").strip(),
        "total_budget": form.get("total_budget", "0").strip(),
        "currency": form.get("currency", "TWD").strip().upper(),
        "introduction": form.get("introduction", "").strip(),
        "visibility": form.get("visibility", "private").strip(),
    }
    errors = []
    if not all(values[k] for k in ("trip_name", "country_id", "city_id", "start_date", "end_date")):
        errors.append("請填寫行程名稱、目的地與旅遊日期。")
    try:
        start, end = date.fromisoformat(values["start_date"]), date.fromisoformat(values["end_date"])
        if end < start:
            errors.append("結束日期不能早於開始日期。")
    except ValueError:
        errors.append("請輸入正確的日期。")
    try:
        values["people_count"] = int(values["people_count"])
        if values["people_count"] < 1:
            raise ValueError
    except ValueError:
        errors.append("旅遊人數至少要 1 人。")
    try:
        values["total_budget"] = Decimal(values["total_budget"])
        if values["total_budget"] < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors.append("預算必須是大於或等於 0 的金額。")
    if values["visibility"] not in ("private", "public", "link_only"):
        values["visibility"] = "private"
    if len(values["currency"]) != 3:
        values["currency"] = "TWD"
    return values, errors


@member_bp.route("/")
@login_required("member")
def dashboard():
    connection = _connection_or_home()
    if connection is None:
        return render_template(
            "visitor.html", is_member=True, trips=[], invitations=[], member_stats={},
            announcements=[], public_trips=[], companions=[], trips_timeline_json={},
            city_weather={}, notifications=[], issue_reasons=ISSUE_REASONS,
            favorited_trips=[], favorite_trip_ids=set()
        )
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        try:
            cursor.execute("DELETE FROM trips WHERE owner_id=%s AND deleted_at < NOW() - INTERVAL %s DAY", (user_id, TRIP_TRASH_DAYS))
            connection.commit()
        except Exception as error:
            connection.rollback(); print("清除過期的已刪除行程失敗：", error)
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.start_date, t.end_date, t.cover_image_path, t.deleted_at,
                   co.name AS country, ci.name AS city,
                   GREATEST(0, %s - DATEDIFF(NOW(), t.deleted_at)) AS days_left
            FROM trips t
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE t.owner_id=%s AND t.deleted_at IS NOT NULL
            ORDER BY t.deleted_at DESC
        """, (TRIP_TRASH_DAYS, user_id))
        deleted_trips = cursor.fetchall()
        cursor.execute("""
            SELECT t.*, co.name AS country, ci.name AS city, tm.member_role,
                   (SELECT COUNT(*) FROM itineraries i WHERE i.trip_id=t.trip_id) AS itinerary_count,
                   (SELECT COUNT(*) FROM trip_members tm2 WHERE tm2.trip_id=t.trip_id AND tm2.join_status='accepted') AS member_count
            FROM trip_members tm
            JOIN trips t ON t.trip_id = tm.trip_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE tm.user_id=%s AND tm.join_status='accepted' AND t.deleted_at IS NULL
            ORDER BY t.start_date ASC, t.created_at DESC
        """, (user_id,))
        trips = cursor.fetchall()
        today = date.today()
        for t in trips:
            if t["end_date"] < today:
                t["phase"] = "completed"
            elif t["start_date"] <= today <= t["end_date"]:
                t["phase"] = "ongoing"
            else:
                t["phase"] = "upcoming"
        cursor.execute("""
            SELECT ti.*, t.trip_name, t.start_date, t.end_date, u.full_name AS inviter_name
            FROM trip_invitations ti JOIN trips t ON t.trip_id=ti.trip_id
            JOIN users u ON u.user_id=ti.inviter_id
            WHERE ti.invitee_id=%s AND ti.status='pending' AND t.deleted_at IS NULL ORDER BY ti.created_at DESC
        """, (user_id,))
        invitations = cursor.fetchall()
        cursor.execute("""
            SELECT notification_id, trip_id, title, message, target_url, created_at
            FROM notifications
            WHERE user_id=%s AND is_read=FALSE
              AND title NOT IN ('你的公開行程被回報', '你的公開行程被舉報', '你的公開行程被檢舉')
            ORDER BY created_at DESC
            LIMIT 10
        """, (user_id,))
        notifications = cursor.fetchall()
        cursor.execute("""
            SELECT announcement_id, title, content, is_pinned, publish_at, created_at
            FROM announcements
            WHERE status = 'published'
              AND (publish_at IS NULL OR publish_at <= NOW())
            ORDER BY is_pinned DESC, publish_at DESC, created_at DESC
            LIMIT 6
        """)
        announcements = cursor.fetchall()
        member_stats = {"total": len(trips), "upcoming": sum(t["phase"] == "upcoming" for t in trips),
                        "ongoing": sum(t["phase"] == "ongoing" for t in trips),
                        "completed": sum(t["phase"] == "completed" for t in trips),
                        "pending": len(invitations)}

        cursor.execute("""
            SELECT t.trip_id, t.owner_id, t.trip_name, co.name AS country, ci.name AS city,
                   t.start_date, t.end_date, t.people_count,
                   t.total_budget, t.currency, t.introduction,
                   t.cover_image_path, t.visibility, c.category_name,
                   u.full_name AS owner_name, u.nickname AS owner_nickname,
                   DATEDIFF(t.end_date, t.start_date) + 1 AS days_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            LEFT JOIN categories c ON c.category_id = t.category_id
            WHERE t.visibility = 'public' AND t.deleted_at IS NULL
            ORDER BY t.trip_id DESC
        """)
        public_trips = cursor.fetchall()
        city_weather = weather.get_weather_by_cities(
            [trip["city"] for trip in public_trips if trip.get("city")]
        )

        cursor.execute("""
            SELECT t.trip_id, t.trip_name, co.name AS country, ci.name AS city,
                   t.people_count, t.total_budget, t.currency, t.introduction,
                   u.full_name AS owner_name, u.nickname AS owner_nickname,
                   COUNT(tm.user_id) AS joined_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            LEFT JOIN trip_members tm ON tm.trip_id = t.trip_id AND tm.join_status = 'accepted'
            WHERE (t.visibility = 'public' OR t.people_count > 1) AND t.deleted_at IS NULL
            GROUP BY t.trip_id, t.trip_name, co.name, ci.name, t.people_count,
                     t.total_budget, t.currency, t.introduction, u.full_name, u.nickname
            ORDER BY t.trip_id DESC
            LIMIT 6
        """)
        companions = cursor.fetchall()

        cursor.execute("""
            SELECT target_id FROM reports
            WHERE reporter_id = %s AND target_type = 'trip' AND reason LIKE %s
              AND status IN ('pending', 'processing')
        """, (user_id, ISSUE_PREFIX + "%"))
        reported_trip_ids = {row["target_id"] for row in cursor.fetchall()}

        cursor.execute("SELECT trip_id FROM favorites WHERE user_id=%s AND target_type='trip'", (user_id,))
        favorite_trip_ids = {row["trip_id"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT t.trip_id, t.trip_name, co.name AS country, ci.name AS city,
                   t.start_date, t.end_date, t.people_count, t.total_budget, t.currency,
                   t.cover_image_path, u.full_name AS owner_name, u.nickname AS owner_nickname,
                   DATEDIFF(t.end_date, t.start_date) + 1 AS days_count
            FROM favorites f
            JOIN trips t ON t.trip_id = f.trip_id
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE f.user_id=%s AND f.target_type='trip' AND t.deleted_at IS NULL
            ORDER BY f.created_at DESC
        """, (user_id,))
        favorited_trips = cursor.fetchall()

        trips_timeline_json = {}
        if public_trips:
            trip_ids = [trip["trip_id"] for trip in public_trips]
            placeholders = ",".join(["%s"] * len(trip_ids))
            cursor.execute(f"""
                SELECT trip_id, itinerary_date, title, start_time, end_time,
                       address, estimated_cost
                FROM itineraries
                WHERE trip_id IN ({placeholders})
                ORDER BY itinerary_date ASC, start_time ASC
            """, tuple(trip_ids))
            all_itineraries = cursor.fetchall()
            for trip in public_trips:
                timeline = []
                items = [item for item in all_itineraries if item["trip_id"] == trip["trip_id"]]
                for index, item in enumerate(items, 1):
                    date_text = str(item["itinerary_date"]) if item["itinerary_date"] else f"第 {index} 天"
                    time_text = f" ({item['start_time']} - {item['end_time']})" if item["start_time"] else ""
                    address_text = f" ｜ 地址: {item['address']}" if item["address"] else ""
                    cost_text = f" (預估金額: NT$ {item['estimated_cost']:,.0f})" if item["estimated_cost"] else ""
                    timeline.append({"day": f"📍 {date_text}{time_text}",
                                     "desc": f"{item['title']}{address_text}{cost_text}"})
                trips_timeline_json[str(trip["trip_id"])] = {
                    "title": trip["trip_name"],
                    "author": trip["owner_nickname"] or trip["owner_name"],
                    "days": f"{trip['days_count']} 天",
                    "budget": (f"{trip['currency']} {trip['total_budget']:,.0f}"
                               if trip["total_budget"] is not None else "未提供預算"),
                    "timeline": timeline,
                    "can_issue": trip["owner_id"] != user_id and trip["trip_id"] not in reported_trip_ids,
                    "is_favorited": trip["trip_id"] in favorite_trip_ids,
                }
    finally:
        cursor.close(); connection.close()
    return render_template(
        "visitor.html", is_member=True, trips=trips, invitations=invitations,
        member_stats=member_stats, announcements=announcements,
        public_trips=public_trips, companions=companions,
        trips_timeline_json=trips_timeline_json, city_weather=city_weather,
        notifications=notifications, issue_reasons=ISSUE_REASONS,
        favorited_trips=favorited_trips, favorite_trip_ids=favorite_trip_ids,
        deleted_trips=deleted_trips, trip_trash_days=TRIP_TRASH_DAYS
    )


@member_bp.route("/public-trips/<int:trip_id>/issues", methods=["POST"])
@login_required("member")
def submit_trip_issue(trip_id):
    reason = request.form.get("reason", "").strip()
    description = request.form.get("description", "").strip()
    if reason not in ISSUE_REASONS:
        flash("請選擇問題類型。", "error")
        return redirect(url_for("member.dashboard") + "#trips")
    if len(description) > 1000 or (reason == "其它" and not description):
        flash("請填寫其它問題的詳細說明，且不得超過 1000 字。", "error")
        return redirect(url_for("member.dashboard") + "#trips")

    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard") + "#trips")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT trip_id, owner_id FROM trips
            WHERE trip_id = %s AND visibility = 'public' AND deleted_at IS NULL
        """, (trip_id,))
        trip = cursor.fetchone()
        if not trip:
            flash("找不到這筆公開行程。", "error")
        elif trip["owner_id"] == session["user_id"]:
            flash("不能回報自己建立的行程。", "error")
        else:
            cursor.execute("""
                SELECT report_id FROM reports
                WHERE reporter_id = %s AND target_type = 'trip' AND target_id = %s
                  AND reason LIKE %s AND status IN ('pending', 'processing')
                LIMIT 1
            """, (session["user_id"], trip_id, ISSUE_PREFIX + "%"))
            if cursor.fetchone():
                flash("你已回報這筆行程，管理員正在處理。", "error")
            else:
                cursor.execute("""
                    INSERT INTO reports (reporter_id, target_type, target_id, reason, description)
                    VALUES (%s, 'trip', %s, %s, %s)
                """, (session["user_id"], trip_id, ISSUE_PREFIX + reason, description or None))
                connection.commit()
                flash("問題已送出，系統管理員會查看。", "success")
    except Exception as error:
        connection.rollback()
        print("送出問題回報失敗：", error)
        flash("問題送出失敗，請稍後再試。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("member.dashboard") + "#trips")


@member_bp.route("/trips/<int:trip_id>/favorite", methods=["POST"])
@login_required("member")
def toggle_trip_favorite(trip_id):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard") + "#trips")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT trip_id FROM trips WHERE trip_id=%s AND visibility='public' AND deleted_at IS NULL", (trip_id,))
        if not cursor.fetchone():
            flash("只能收藏公開行程。", "error")
        else:
            user_id = session["user_id"]
            cursor.execute("SELECT favorite_id FROM favorites WHERE user_id=%s AND trip_id=%s", (user_id, trip_id))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("DELETE FROM favorites WHERE favorite_id=%s", (existing["favorite_id"],))
                connection.commit()
                flash("已取消收藏。", "success")
            else:
                cursor.execute("INSERT INTO favorites (user_id, target_type, trip_id) VALUES (%s,'trip',%s)", (user_id, trip_id))
                connection.commit()
                flash("已加入收藏。", "success")
    except Exception as error:
        connection.rollback()
        print("收藏行程失敗：", error)
        flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()

    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.dashboard") + "#trips"
    return redirect(next_url)


@member_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required("member")
def mark_notification_read(notification_id):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE notifications
            SET is_read=TRUE, read_at=NOW()
            WHERE notification_id=%s AND user_id=%s
        """, (notification_id, session["user_id"]))
        connection.commit()
    except Exception as error:
        connection.rollback()
        print("更新通知狀態失敗：", error)
        flash("通知狀態更新失敗。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("member.dashboard") + "#member-notifications")


def _addable_trips(cursor, user_id):
    """可以把景點加進去的行程：自己是建立者或編輯者，且尚未結束。"""
    cursor.execute("""
        SELECT t.trip_id, t.trip_name, t.city_id, t.start_date, t.end_date, ci.name AS city
        FROM trip_members tm
        JOIN trips t ON t.trip_id = tm.trip_id
        JOIN cities ci ON ci.city_id = t.city_id
        WHERE tm.user_id=%s AND tm.join_status='accepted' AND tm.member_role IN ('owner','editor') AND t.deleted_at IS NULL
              AND t.end_date >= CURDATE()
        ORDER BY t.start_date ASC, t.created_at DESC
    """, (user_id,))
    return cursor.fetchall()


@member_bp.route("/attractions")
@login_required("member")
def browse_attractions():
    keyword = request.args.get("keyword", "").strip()
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    favorites_only = request.args.get("favorites_only") == "1"

    connection = _connection_or_home()
    if connection is None:
        return render_template("member/attractions.html", attractions=[], countries=[], cities=[],
                                keyword=keyword, country_id=country_id, city_id=city_id, favorites_only=favorites_only)
    cursor = connection.cursor(dictionary=True)
    try:
        conditions = ["a.status = 'active'", "a.deleted_at IS NULL"]
        params = [session["user_id"]]

        if keyword:
            conditions.append("(a.name LIKE %s OR a.address LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if country_id:
            conditions.append("a.country_id = %s")
            params.append(country_id)
        if city_id:
            conditions.append("a.city_id = %s")
            params.append(city_id)
        if favorites_only:
            conditions.append("f.favorite_id IS NOT NULL")

        where_clause = " AND ".join(conditions)
        cursor.execute(f"""
            SELECT a.attraction_id, a.city_id, a.name, a.address, a.latitude, a.longitude, a.ticket_price, a.image_path,
                   a.is_popular, cat.category_name, co.name AS country, ci.name AS city,
                   (f.favorite_id IS NOT NULL) AS is_favorited
            FROM attractions a
            LEFT JOIN categories cat ON cat.category_id = a.category_id
            JOIN countries co ON co.country_id = a.country_id
            JOIN cities ci ON ci.city_id = a.city_id
            LEFT JOIN favorites f ON f.attraction_id = a.attraction_id AND f.user_id = %s
            WHERE {where_clause}
            ORDER BY a.attraction_id DESC
        """, params)
        attractions = cursor.fetchall()
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        addable_trips = _addable_trips(cursor, session["user_id"])
    finally:
        cursor.close(); connection.close()

    return render_template("member/attractions.html", attractions=attractions, countries=countries, cities=cities,
                            keyword=keyword, country_id=country_id, city_id=city_id, favorites_only=favorites_only,
                            addable_trips=addable_trips)


@member_bp.route("/attractions/<int:attraction_id>")
@login_required("member")
def attraction_detail(attraction_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.browse_attractions"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT a.*, cat.category_name, co.name AS country, ci.name AS city,
                   (f.favorite_id IS NOT NULL) AS is_favorited
            FROM attractions a
            LEFT JOIN categories cat ON cat.category_id = a.category_id
            JOIN countries co ON co.country_id = a.country_id
            JOIN cities ci ON ci.city_id = a.city_id
            LEFT JOIN favorites f ON f.attraction_id = a.attraction_id AND f.user_id = %s
            WHERE a.attraction_id = %s AND a.status = 'active' AND a.deleted_at IS NULL
        """, (session["user_id"], attraction_id))
        attraction = cursor.fetchone()
        addable_trips = _addable_trips(cursor, session["user_id"]) if attraction else []
    finally:
        cursor.close(); connection.close()

    if not attraction:
        flash("找不到這個景點，或已被下架。", "error")
        return redirect(url_for("member.browse_attractions"))

    return render_template("member/attraction_detail.html", a=attraction, addable_trips=addable_trips)


@member_bp.route("/attractions/<int:attraction_id>/add-to-trip", methods=["POST"])
@login_required("member")
def add_attraction_to_trip(attraction_id):
    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.browse_attractions")

    trip_id = request.form.get("trip_id", "").strip()
    day = request.form.get("itinerary_date", "").strip()
    start = request.form.get("start_time") or None
    end = request.form.get("end_time") or None
    if not trip_id.isdigit() or not day:
        flash("請選擇要加入的行程與日期。", "error"); return redirect(next_url)
    if start and end and end < start:
        flash("結束時間不能早於開始時間。", "error"); return redirect(next_url)
    try:
        day_value = date.fromisoformat(day)
    except ValueError:
        flash("請輸入正確的日期。", "error"); return redirect(next_url)

    connection = _connection_or_home()
    if connection is None: return redirect(next_url)
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, int(trip_id), session["user_id"])
        if not trip or not _can_edit(trip):
            flash("你沒有編輯這個行程的權限。", "error"); return redirect(next_url)
        if not trip["start_date"] <= day_value <= trip["end_date"]:
            flash(f"日期必須在行程期間內（{trip['start_date']} ～ {trip['end_date']}）。", "error"); return redirect(next_url)
        cursor.execute("""SELECT name, address, ticket_price FROM attractions
                          WHERE attraction_id=%s AND status='active' AND deleted_at IS NULL""", (attraction_id,))
        attraction = cursor.fetchone()
        if not attraction:
            flash("找不到這個景點，或已被下架。", "error"); return redirect(next_url)
        cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s", (trip["trip_id"], day_value))
        order = cursor.fetchone()["next_order"]
        cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,address,transport_method,estimated_cost,notes,attraction_id,sort_order)
                          VALUES (%s,%s,%s,'attraction',%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                       (trip["trip_id"], session["user_id"], day_value, attraction["name"][:150], start, end, attraction["address"],
                        request.form.get("transport_method", "").strip() or None,
                        attraction["ticket_price"] or 0, request.form.get("notes", "").strip() or None, attraction_id, order))
        connection.commit()
        flash(f"已將「{attraction['name']}」加入「{trip['trip_name']}」的 {day_value} 行程。", "success")
    except Exception:
        current_app.logger.exception("加入景點到行程失敗 user_id=%s", session.get("user_id"))
        connection.rollback(); flash("加入行程失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(next_url)


@member_bp.route("/attractions/<int:attraction_id>/favorite", methods=["POST"])
@login_required("member")
def toggle_favorite(attraction_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.browse_attractions"))
    cursor = connection.cursor()
    try:
        user_id = session["user_id"]
        cursor.execute("SELECT favorite_id FROM favorites WHERE user_id=%s AND attraction_id=%s", (user_id, attraction_id))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("DELETE FROM favorites WHERE favorite_id=%s", (existing[0],))
            connection.commit()
            flash("已取消收藏。", "success")
        else:
            cursor.execute("INSERT INTO favorites (user_id, target_type, attraction_id) VALUES (%s,'attraction',%s)", (user_id, attraction_id))
            connection.commit()
            flash("已加入收藏。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()

    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.browse_attractions")
    return redirect(next_url)


@member_bp.route("/trips/new", methods=["GET", "POST"])
@login_required("member")
def create_trip():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        if request.method == "POST":
            form, errors = _parse_trip(request.form)
            if not errors and not _city_matches_country(cursor, form["country_id"], form["city_id"]):
                errors.append("所選城市不屬於該國家，請重新選擇。")
            cover_image_path = None
            image_file = request.files.get("cover_image")
            if not errors and image_file and image_file.filename:
                try:
                    cover_image_path = save_uploaded_image(image_file, "trips")
                except ValueError as error:
                    errors.append(str(error))
            if errors:
                for error in errors: flash(error, "error")
                return render_template("member/trip_form.html", trip=form, mode="create", countries=countries, cities=cities)
            try:
                cursor.execute("""INSERT INTO trips (owner_id,trip_name,cover_image_path,country_id,city_id,start_date,end_date,people_count,total_budget,currency,introduction,visibility,status,share_token)
                                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'planning',%s)""",
                               (session["user_id"], form["trip_name"], cover_image_path, form["country_id"], form["city_id"], form["start_date"], form["end_date"], form["people_count"], form["total_budget"], form["currency"], form["introduction"] or None, form["visibility"], secrets.token_urlsafe(16)))
                trip_id = cursor.lastrowid
                cursor.execute("INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())", (trip_id, session["user_id"]))
                connection.commit()
                flash("已建立新行程，現在可以邀請旅伴並安排每日活動。", "success")
                return redirect(url_for("member.trip_detail", trip_id=trip_id))
            except Exception:
                current_app.logger.exception("建立行程失敗 user_id=%s", session.get("user_id"))
                connection.rollback(); flash("建立行程失敗，請再試一次。", "error")
        return render_template("member/trip_form.html", trip=None, mode="create", countries=countries, cities=cities)
    finally:
        cursor.close(); connection.close()


def _summarize_transport_time(itinerary):
    """統計整趟行程裡，各種交通方式總共花費的通勤時間(分鐘)。"""
    totals = {}
    for item in itinerary:
        minutes = item.get("transport_minutes") or 0
        if minutes <= 0:
            continue
        method = item.get("transport_method") or "未標註交通方式"
        totals[method] = totals.get(method, 0) + minutes
    summary = [{"method": method, "minutes": minutes} for method, minutes in totals.items()]
    summary.sort(key=lambda row: row["minutes"], reverse=True)
    return summary


def _load_place_options(cursor, city_id):
    """新增行程項目時可直接選擇的景點、餐廳、住宿（同城市、已上架）。"""
    queries = {
        "attraction": "SELECT name, address, ticket_price AS cost FROM attractions",
        "restaurant": "SELECT name, address, 0 AS cost FROM restaurants",
        "accommodation": "SELECT name, address, price_per_night AS cost FROM accommodations",
    }
    options = {}
    for item_type, sql in queries.items():
        cursor.execute(sql + " WHERE city_id=%s AND status='active' AND deleted_at IS NULL ORDER BY name", (city_id,))
        options[item_type] = [{"name": r["name"], "address": r["address"] or "", "cost": float(r["cost"] or 0)} for r in cursor.fetchall()]
    return options


@member_bp.route("/trips/<int:trip_id>")
@login_required("member")
def trip_detail(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            flash("你沒有查看此行程的權限。", "error"); return redirect(url_for("member.dashboard"))
        cursor.execute("""SELECT i.*, u.nickname, u.full_name,
                                 a.attraction_id AS detail_attraction_id, a.image_path AS attraction_image,
                                 a.description AS attraction_description, a.opening_hours AS attraction_hours,
                                 a.suggested_duration_minutes AS attraction_duration
                          FROM itineraries i JOIN users u ON u.user_id=i.created_by
                          LEFT JOIN attractions a ON a.attraction_id=i.attraction_id
                              AND i.item_type='attraction' AND a.status='active' AND a.deleted_at IS NULL
                          WHERE i.trip_id=%s ORDER BY i.itinerary_date,i.start_time,i.sort_order""", (trip_id,)); itinerary = cursor.fetchall()
        city_weather_days = {}
        city_weather = weather.get_weather_by_cities([trip["city"]]) if trip.get("city") else {}
        if trip.get("city") in city_weather:
            city_weather_days = {day["date"]: day for day in city_weather[trip["city"]]["days"]}
        cursor.execute("""SELECT tm.*, u.full_name,u.nickname,u.username FROM trip_members tm JOIN users u ON u.user_id=tm.user_id
                          WHERE tm.trip_id=%s AND tm.join_status='accepted' ORDER BY FIELD(tm.member_role,'owner','editor','viewer'),u.full_name""", (trip_id,)); members = cursor.fetchall()
        cursor.execute("""SELECT ti.*, u.full_name AS invitee_name, u.nickname AS invitee_nickname
                          FROM trip_invitations ti JOIN users u ON u.user_id=ti.invitee_id
                          WHERE ti.trip_id=%s AND ti.status='pending' ORDER BY ti.created_at DESC""", (trip_id,)); pending_invitations = cursor.fetchall()
        cursor.execute("""SELECT p.*,u.full_name AS proposer_name FROM proposals p JOIN users u ON u.user_id=p.proposer_id
                          WHERE p.trip_id=%s ORDER BY p.created_at DESC""", (trip_id,)); proposals = cursor.fetchall()
        votes = _load_votes(cursor, trip_id, session["user_id"])
        comments = _load_comments(cursor, trip_id)
        expenses = _load_expenses(cursor, trip_id)
        balance_summary = _load_balance_summary(cursor, trip_id)
        attachments = _load_attachments(cursor, trip_id)
        place_options = _load_place_options(cursor, trip["city_id"])
        cursor.execute("""
            SELECT a.attraction_id, a.name, a.address, a.ticket_price, a.image_path, a.city_id,
                   cat.category_name, ci.name AS city, a.description,
                   a.opening_hours, a.suggested_duration_minutes
            FROM attractions a
            LEFT JOIN categories cat ON cat.category_id = a.category_id
            JOIN cities ci ON ci.city_id = a.city_id
            WHERE a.country_id = %s AND a.status = 'active' AND a.deleted_at IS NULL
            ORDER BY (a.city_id = %s) DESC, a.is_popular DESC, a.attraction_id DESC
            LIMIT 20
        """, (trip["country_id"], trip["city_id"])); popular_attractions = cursor.fetchall()
        cursor.execute("SELECT COALESCE(SUM(amount),0) AS actual FROM expenses WHERE trip_id=%s AND expense_type='actual'", (trip_id,)); actual = cursor.fetchone()["actual"]
        transport_summary = _summarize_transport_time(itinerary)
    finally:
        cursor.close(); connection.close()
    return render_template("member/trip_detail.html", trip=trip, itinerary=itinerary, place_options=place_options, popular_attractions=popular_attractions, addable_trips=[trip], city_weather_days=city_weather_days, members=members, pending_invitations=pending_invitations, proposals=proposals, votes=votes, comments=comments, expenses=expenses, balance_summary=balance_summary, attachments=attachments, actual=actual, can_edit=_can_edit(trip), is_owner=trip["member_role"] == "owner", now=datetime.now(), item_type_labels=ITEM_TYPE_LABELS, disney_parks=theme_parks.get_disney_parks(), transport_summary=transport_summary)


@member_bp.route("/trips/<int:trip_id>/park-hours")
@login_required("member")
def park_hours(trip_id):
    connection = _connection_or_home()
    if connection is None: return {"error": "資料庫連線失敗"}, 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
    finally:
        cursor.close(); connection.close()
    if not trip:
        return {"error": "找不到這趟行程"}, 404

    park_id = request.args.get("park", "").strip()
    target_date = request.args.get("date", "").strip()
    try:
        date.fromisoformat(target_date)
    except ValueError:
        return {"error": "日期格式不正確"}, 400

    hours = theme_parks.get_park_hours(park_id, target_date)
    if not hours:
        return {"error": "查不到這個日期的開放時間，樂園當天可能休園或尚未公布班表"}, 404
    return hours


@member_bp.route("/trips/<int:trip_id>/edit", methods=["GET", "POST"])
@login_required("member")
def edit_trip(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有行程建立者可以修改整份行程。", "error"); return redirect(url_for("member.dashboard"))
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        if request.method == "POST":
            form, errors = _parse_trip(request.form)
            if not errors and not _city_matches_country(cursor, form["country_id"], form["city_id"]):
                errors.append("所選城市不屬於該國家，請重新選擇。")
            cover_image_path = trip["cover_image_path"]
            image_file = request.files.get("cover_image")
            if not errors and image_file and image_file.filename:
                try:
                    uploaded_path = save_uploaded_image(image_file, "trips")
                    delete_uploaded_image(trip["cover_image_path"])
                    cover_image_path = uploaded_path
                except ValueError as error:
                    errors.append(str(error))
            elif not errors and request.form.get("remove_cover") == "1":
                delete_uploaded_image(trip["cover_image_path"])
                cover_image_path = None
            if errors:
                for error in errors: flash(error, "error")
                form["trip_id"] = trip_id; return render_template("member/trip_form.html", trip=form, mode="edit", countries=countries, cities=cities)
            cursor.execute("""UPDATE trips SET trip_name=%s,cover_image_path=%s,country_id=%s,city_id=%s,start_date=%s,end_date=%s,people_count=%s,total_budget=%s,currency=%s,introduction=%s,visibility=%s WHERE trip_id=%s""", (form["trip_name"],cover_image_path,form["country_id"],form["city_id"],form["start_date"],form["end_date"],form["people_count"],form["total_budget"],form["currency"],form["introduction"] or None,form["visibility"],trip_id))
            connection.commit(); flash("行程資料已更新。", "success"); return redirect(url_for("member.trip_detail", trip_id=trip_id))
        return render_template("member/trip_form.html", trip=trip, mode="edit", countries=countries, cities=cities)
    finally:
        cursor.close(); connection.close()


@member_bp.route("/trips/<int:trip_id>/delete", methods=["POST"])
@login_required("member")
def delete_trip(trip_id):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT trip_name FROM trips WHERE trip_id=%s AND owner_id=%s AND deleted_at IS NULL",
            (trip_id, session["user_id"]),
        )
        trip = cursor.fetchone()
        if not trip:
            flash("只有行程建立者可以刪除行程。", "error")
            return redirect(url_for("member.dashboard"))

        # 軟刪除：只標記刪除時間，資料都還在，建立者可以在「最近刪除」復原
        cursor.execute(
            "UPDATE trips SET deleted_at=NOW(), deleted_by=%s WHERE trip_id=%s AND owner_id=%s",
            (session["user_id"], trip_id, session["user_id"]),
        )
        connection.commit()
        flash(f"行程「{trip['trip_name']}」已移到「最近刪除」，{TRIP_TRASH_DAYS} 天內可以復原。", "success")
    except Exception as error:
        connection.rollback()
        print("刪除行程失敗：", error)
        flash("刪除行程失敗，請稍後再試。", "error")
        return redirect(url_for("member.trip_detail", trip_id=trip_id))
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("member.dashboard") + "#trip-trash")


def _owned_deleted_trip(cursor, trip_id):
    cursor.execute(
        "SELECT trip_id, trip_name FROM trips WHERE trip_id=%s AND owner_id=%s AND deleted_at IS NOT NULL",
        (trip_id, session["user_id"]),
    )
    return cursor.fetchone()


@member_bp.route("/trips/<int:trip_id>/restore", methods=["POST"])
@login_required("member")
def restore_trip(trip_id):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _owned_deleted_trip(cursor, trip_id)
        if not trip:
            flash("找不到這個已刪除的行程。", "error")
            return redirect(url_for("member.dashboard") + "#trip-trash")
        cursor.execute("UPDATE trips SET deleted_at=NULL, deleted_by=NULL WHERE trip_id=%s", (trip_id,))
        connection.commit()
        flash(f"行程「{trip['trip_name']}」已復原。", "success")
    except Exception as error:
        connection.rollback()
        print("復原行程失敗：", error)
        flash("復原行程失敗，請稍後再試。", "error")
        return redirect(url_for("member.dashboard") + "#trip-trash")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id))


@member_bp.route("/trips/<int:trip_id>/purge", methods=["POST"])
@login_required("member")
def purge_trip(trip_id):
    """永久刪除：只能刪「最近刪除」裡的行程，相關資料會跟著 CASCADE 刪除，無法復原。"""
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _owned_deleted_trip(cursor, trip_id)
        if not trip:
            flash("找不到這個已刪除的行程。", "error")
        else:
            cursor.execute("DELETE FROM trips WHERE trip_id=%s", (trip_id,))
            connection.commit()
            flash(f"行程「{trip['trip_name']}」已永久刪除。", "success")
    except Exception as error:
        connection.rollback()
        print("永久刪除行程失敗：", error)
        flash("永久刪除失敗，請稍後再試。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("member.dashboard") + "#trip-trash")


@member_bp.route("/trips/<int:trip_id>/duplicate", methods=["POST"])
@login_required("member")
def duplicate_trip(trip_id):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM trips WHERE trip_id=%s AND deleted_at IS NULL", (trip_id,))
        trip = cursor.fetchone()
        if not trip:
            flash("找不到這個行程。", "error")
            return redirect(url_for("member.dashboard"))
        if trip["owner_id"] != session["user_id"] and trip["visibility"] != "public":
            flash("只能複製自己的行程，或是公開行程。", "error")
            return redirect(url_for("member.dashboard"))

        cursor.execute("""
            INSERT INTO trips (owner_id,trip_name,country_id,city_id,start_date,end_date,
                                people_count,total_budget,currency,introduction,visibility,status,share_token)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'private','planning',%s)
        """, (session["user_id"], trip["trip_name"] + "（複製）", trip["country_id"], trip["city_id"],
              trip["start_date"], trip["end_date"], trip["people_count"], trip["total_budget"], trip["currency"],
              trip["introduction"], secrets.token_urlsafe(16)))
        new_trip_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())",
            (new_trip_id, session["user_id"])
        )

        cursor.execute("SELECT * FROM itineraries WHERE trip_id=%s ORDER BY itinerary_date, sort_order", (trip_id,))
        items = cursor.fetchall()
        for item in items:
            cursor.execute("""
                INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,
                                          address,transport_method,transport_minutes,estimated_cost,notes,
                                          attraction_id,restaurant_id,accommodation_id,sort_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (new_trip_id, session["user_id"], item["itinerary_date"], item["item_type"], item["title"],
                  item["start_time"], item["end_time"], item["is_all_day"], item["address"], item["transport_method"],
                  item["transport_minutes"], item["estimated_cost"], item["notes"],
                  item["attraction_id"], item["restaurant_id"], item["accommodation_id"], item["sort_order"]))

        connection.commit()
        flash("行程已複製，你可以開始編輯這份新的行程。", "success")
        return redirect(url_for("member.trip_detail", trip_id=new_trip_id))
    except Exception as error:
        connection.rollback()
        print("複製行程失敗：", error)
        flash("複製行程失敗，請再試一次。", "error")
        return redirect(url_for("member.dashboard"))
    finally:
        cursor.close()
        connection.close()


@member_bp.route("/trips/<int:trip_id>/itinerary", methods=["POST"])
@login_required("member")
def add_itinerary(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            flash("你沒有編輯行程項目的權限。", "error"); return redirect(url_for("member.dashboard"))
        title = request.form.get("title", "").strip(); item_type=request.form.get("item_type", "other")
        day = request.form.get("itinerary_date", "")
        start, end, is_all_day, transport_minutes, time_errors = _parse_itinerary_time(request.form)
        if not title or not day: flash("請填寫項目名稱與日期。", "error")
        elif time_errors:
            for error in time_errors: flash(error, "error")
        else:
            cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s", (trip_id,day)); order=cursor.fetchone()["next_order"]
            cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,address,transport_method,transport_minutes,estimated_cost,notes,sort_order)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (trip_id,session["user_id"],day,item_type,title,start,end,is_all_day,request.form.get("address","").strip() or None,request.form.get("transport_method","").strip() or None,transport_minutes,request.form.get("estimated_cost") or 0,request.form.get("notes","").strip() or None,order))
            connection.commit(); flash("已加入每日行程。", "success")
    except Exception:
        connection.rollback(); flash("儲存行程項目失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#itinerary")


@member_bp.route("/trips/<int:trip_id>/itinerary/<int:itinerary_id>/edit", methods=["POST"])
@login_required("member")
def edit_itinerary(trip_id, itinerary_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            flash("你沒有編輯行程項目的權限。", "error"); return redirect(url_for("member.dashboard"))
        cursor.execute("SELECT itinerary_id FROM itineraries WHERE itinerary_id=%s AND trip_id=%s", (itinerary_id, trip_id))
        if not cursor.fetchone():
            flash("找不到這個行程項目。", "error")
        else:
            title = request.form.get("title", "").strip(); item_type = request.form.get("item_type", "other")
            day = request.form.get("itinerary_date", "")
            start, end, is_all_day, transport_minutes, time_errors = _parse_itinerary_time(request.form)
            if not title or not day: flash("請填寫項目名稱與日期。", "error")
            elif time_errors:
                for error in time_errors: flash(error, "error")
            else:
                cursor.execute("""UPDATE itineraries SET itinerary_date=%s,item_type=%s,title=%s,start_time=%s,end_time=%s,is_all_day=%s,
                                   address=%s,transport_method=%s,transport_minutes=%s,estimated_cost=%s,notes=%s WHERE itinerary_id=%s""",
                               (day, item_type, title, start, end, is_all_day, request.form.get("address", "").strip() or None,
                                request.form.get("transport_method", "").strip() or None, transport_minutes, request.form.get("estimated_cost") or 0,
                                request.form.get("notes", "").strip() or None, itinerary_id))
                connection.commit(); flash("行程項目已更新。", "success")
    except Exception:
        connection.rollback(); flash("更新行程項目失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#itinerary")


@member_bp.route("/trips/<int:trip_id>/itinerary/<int:itinerary_id>/delete", methods=["POST"])
@login_required("member")
def delete_itinerary(trip_id, itinerary_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            flash("你沒有刪除行程項目的權限。", "error"); return redirect(url_for("member.dashboard"))
        cursor.execute("DELETE FROM itineraries WHERE itinerary_id=%s AND trip_id=%s", (itinerary_id, trip_id))
        connection.commit()
        flash("行程項目已刪除。", "success")
    except Exception:
        connection.rollback(); flash("刪除行程項目失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#itinerary")


@member_bp.route("/trips/<int:trip_id>/proposals", methods=["POST"])
@login_required("member")
def add_proposal(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        title = request.form.get("title", "").strip()
        proposal_type = request.form.get("proposal_type", "other")
        if not trip: flash("你沒有新增提案的權限。", "error")
        elif not title: flash("請填寫提案名稱。", "error")
        elif proposal_type not in ("attraction", "restaurant", "accommodation", "activity", "transport", "date", "other"): flash("提案類型無效。", "error")
        else:
            cursor.execute("""INSERT INTO proposals (trip_id,proposer_id,proposal_type,title,location,description,estimated_cost,proposed_date,content_review_status)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'not_required')""", (trip_id, session["user_id"], proposal_type, title, request.form.get("location", "").strip() or None, request.form.get("description", "").strip() or None, request.form.get("estimated_cost") or 0, request.form.get("proposed_date") or None))
            connection.commit(); flash("提案已送出，旅伴現在可以一起討論。", "success")
    except Exception:
        connection.rollback(); flash("送出提案失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/votes", methods=["POST"])
@login_required("member")
def add_vote(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        title = request.form.get("title", "").strip()
        vote_type = request.form.get("vote_type", "approval")
        if vote_type not in ("approval", "single_choice"): vote_type = "approval"
        deadline_at = request.form.get("deadline_at", "").strip().replace("T", " ")
        option_texts = [text.strip() for text in request.form.getlist("option_text") if text.strip()]

        proposal_id = request.form.get("proposal_id", "").strip() or None
        proposal = None
        if proposal_id:
            cursor.execute("SELECT * FROM proposals WHERE proposal_id=%s AND trip_id=%s", (proposal_id, trip_id))
            proposal = cursor.fetchone()

        if not trip: flash("你沒有建立投票的權限。", "error")
        elif not title or not deadline_at: flash("請填寫投票標題與截止時間。", "error")
        elif vote_type == "single_choice" and len(option_texts) < 2: flash("單選投票至少需要填寫 2 個選項。", "error")
        elif proposal_id and (not proposal or proposal["status"] != "discussing"): flash("這個提案目前無法發起投票。", "error")
        else:
            cursor.execute("""INSERT INTO votes (trip_id,proposal_id,created_by,title,vote_type,deadline_at)
                              VALUES (%s,%s,%s,%s,%s,%s)""", (trip_id, proposal_id, session["user_id"], title, vote_type, deadline_at))
            vote_id = cursor.lastrowid
            if vote_type == "single_choice":
                for idx, text in enumerate(option_texts, 1):
                    cursor.execute("INSERT INTO vote_options (vote_id,option_text,sort_order) VALUES (%s,%s,%s)", (vote_id, text, idx))
            if proposal_id:
                cursor.execute("UPDATE proposals SET status='voting' WHERE proposal_id=%s", (proposal_id,))
            connection.commit()
            flash("投票已建立。", "success")
    except Exception:
        connection.rollback(); flash("建立投票失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/votes/<int:vote_id>/cast", methods=["POST"])
@login_required("member")
def cast_vote(trip_id, vote_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            flash("你沒有查看此行程的權限。", "error")
            return redirect(url_for("member.dashboard"))

        cursor.execute("SELECT * FROM votes WHERE vote_id=%s AND trip_id=%s", (vote_id, trip_id))
        vote = cursor.fetchone()

        if not vote:
            flash("找不到這個投票。", "error")
        elif vote["status"] != "open" or vote["deadline_at"] < datetime.now():
            flash("這個投票已經結束了。", "error")
        else:
            cursor.execute("SELECT vote_record_id FROM vote_records WHERE vote_id=%s AND user_id=%s", (vote_id, session["user_id"]))
            existing = cursor.fetchone()

            if existing and not vote["allow_change"]:
                flash("這個投票不允許更改，你已經投過票了。", "error")
            elif vote["vote_type"] == "approval":
                choice = request.form.get("approval_choice")
                reason = request.form.get("reason", "").strip() or None
                if choice == "cancel":
                    if existing:
                        cursor.execute("DELETE FROM vote_records WHERE vote_record_id=%s", (existing["vote_record_id"],))
                        connection.commit(); flash("已取消你的投票。", "success")
                    else:
                        flash("你還沒有投票。", "error")
                elif choice not in ("agree", "disagree", "neutral"):
                    flash("請選擇有效的投票選項。", "error")
                else:
                    saved_reason = reason if choice == "disagree" else None
                    if existing:
                        cursor.execute("UPDATE vote_records SET approval_choice=%s, option_id=NULL, reason=%s WHERE vote_record_id=%s", (choice, saved_reason, existing["vote_record_id"]))
                        connection.commit(); flash("已更新你的投票。", "success")
                    else:
                        cursor.execute("INSERT INTO vote_records (vote_id,user_id,approval_choice,reason) VALUES (%s,%s,%s,%s)", (vote_id, session["user_id"], choice, saved_reason))
                        connection.commit(); flash("已送出你的投票。", "success")
            else:
                option_id = request.form.get("option_id", "")
                cursor.execute("SELECT option_id FROM vote_options WHERE option_id=%s AND vote_id=%s", (option_id, vote_id))
                if not cursor.fetchone():
                    flash("請選擇有效的選項。", "error")
                elif existing:
                    cursor.execute("UPDATE vote_records SET option_id=%s, approval_choice=NULL WHERE vote_record_id=%s", (option_id, existing["vote_record_id"]))
                    connection.commit(); flash("已更新你的投票。", "success")
                else:
                    cursor.execute("INSERT INTO vote_records (vote_id,user_id,option_id) VALUES (%s,%s,%s)", (vote_id, session["user_id"], option_id))
                    connection.commit(); flash("已送出你的投票。", "success")
    except Exception:
        connection.rollback(); flash("投票失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/votes/<int:vote_id>/close", methods=["POST"])
@login_required("member")
def close_vote(trip_id, vote_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM votes WHERE vote_id=%s AND trip_id=%s", (vote_id, trip_id))
        vote = cursor.fetchone()

        if not trip or not vote:
            flash("找不到這個投票。", "error")
        elif vote["created_by"] != session["user_id"] and trip["member_role"] != "owner":
            flash("只有發起人或行程建立者可以結束投票。", "error")
        else:
            cursor.execute("UPDATE votes SET status='closed' WHERE vote_id=%s", (vote_id,))

            if vote["proposal_id"] and vote["vote_type"] == "approval":
                cursor.execute("""
                    SELECT approval_choice, COUNT(*) AS c FROM vote_records
                    WHERE vote_id=%s AND approval_choice IS NOT NULL GROUP BY approval_choice
                """, (vote_id,))
                tally = {row["approval_choice"]: row["c"] for row in cursor.fetchall()}
                new_status = "approved" if tally.get("agree", 0) > tally.get("disagree", 0) else "rejected"
                cursor.execute("UPDATE proposals SET status=%s WHERE proposal_id=%s", (new_status, vote["proposal_id"]))

            connection.commit()
            flash("投票已結束。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/comments", methods=["POST"])
@login_required("member")
def add_comment(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        content = request.form.get("content", "").strip()
        parent_id = request.form.get("parent_comment_id", "").strip() or None

        if not trip: flash("你沒有留言的權限。", "error")
        elif not content: flash("留言內容不能是空的。", "error")
        else:
            if parent_id:
                cursor.execute("SELECT comment_id FROM comments WHERE comment_id=%s AND trip_id=%s", (parent_id, trip_id))
                if not cursor.fetchone():
                    parent_id = None
            cursor.execute("""INSERT INTO comments (trip_id,user_id,parent_comment_id,content)
                              VALUES (%s,%s,%s,%s)""", (trip_id, session["user_id"], parent_id, content))
            connection.commit()
            flash("留言已送出。", "success")
    except Exception:
        connection.rollback(); flash("留言失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#discussion")


@member_bp.route("/trips/<int:trip_id>/comments/<int:comment_id>/delete", methods=["POST"])
@login_required("member")
def delete_comment(trip_id, comment_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM comments WHERE comment_id=%s AND trip_id=%s", (comment_id, trip_id))
        comment = cursor.fetchone()

        if not trip or not comment:
            flash("找不到這則留言。", "error")
        elif comment["user_id"] != session["user_id"] and trip["member_role"] != "owner":
            flash("只有留言者本人或行程建立者可以刪除留言。", "error")
        else:
            cursor.execute("UPDATE comments SET status='deleted' WHERE comment_id=%s", (comment_id,))
            connection.commit()
            flash("留言已刪除。", "success")
    except Exception:
        connection.rollback(); flash("刪除失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#discussion")


CHAT_MAX_LENGTH = 1000


def _display_name(row):
    return row["nickname"] or row["full_name"]


def _chat_members(cursor, trip_id):
    """行程成員與各自在聊天室讀到哪一則訊息（沒進過聊天室視為 0）。"""
    cursor.execute("""
        SELECT tm.user_id, tm.member_role, u.full_name, u.nickname,
               COALESCE(r.last_read_message_id, 0) AS last_read_message_id, r.last_seen_at
        FROM trip_members tm JOIN users u ON u.user_id = tm.user_id
        LEFT JOIN trip_chat_reads r ON r.trip_id = tm.trip_id AND r.user_id = tm.user_id
        WHERE tm.trip_id=%s AND tm.join_status='accepted'
        ORDER BY FIELD(tm.member_role,'owner','editor','viewer'), u.full_name
    """, (trip_id,))
    return cursor.fetchall()


def _open_vote_progress(cursor, trip_id, members):
    """進行中的投票：所有已加入成員中，哪些已投、哪些還沒投。"""
    cursor.execute("""
        SELECT vote_id, title, deadline_at FROM votes
        WHERE trip_id=%s AND status='open' AND deadline_at >= NOW() ORDER BY deadline_at
    """, (trip_id,))
    votes = cursor.fetchall()
    voters = members
    progress = []
    for v in votes:
        cursor.execute("SELECT user_id FROM vote_records WHERE vote_id=%s", (v["vote_id"],))
        voted_ids = {row["user_id"] for row in cursor.fetchall()}
        progress.append({
            "vote_id": v["vote_id"],
            "title": v["title"],
            "deadline": v["deadline_at"].strftime("%m/%d %H:%M"),
            "voted": [{"user_id": m["user_id"], "name": _display_name(m)} for m in voters if m["user_id"] in voted_ids],
            "pending": [{"user_id": m["user_id"], "name": _display_name(m)} for m in voters if m["user_id"] not in voted_ids],
        })
    return progress


def _post_chat_message(cursor, trip_id, user_id, content):
    cursor.execute("INSERT INTO trip_chat_messages (trip_id,user_id,content) VALUES (%s,%s,%s)", (trip_id, user_id, content))
    message_id = cursor.lastrowid
    # 自己送出的訊息當然算自己已讀
    cursor.execute("""INSERT INTO trip_chat_reads (trip_id,user_id,last_read_message_id) VALUES (%s,%s,%s)
                      ON DUPLICATE KEY UPDATE last_read_message_id=GREATEST(last_read_message_id, VALUES(last_read_message_id))""",
                   (trip_id, user_id, message_id))
    return message_id


@member_bp.route("/trips/<int:trip_id>/chat")
@login_required("member")
def chat_feed(trip_id):
    """聊天室輪詢：回傳 after 之後的新訊息、每位成員的已讀位置、進行中投票的投票進度。"""
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        if not _member_access(cursor, trip_id, session["user_id"]):
            return jsonify(error="你沒有查看此行程的權限。"), 403
        after = request.args.get("after", 0, type=int)
        if after > 0:
            cursor.execute("""SELECT m.message_id, m.user_id, m.content, m.created_at, u.full_name, u.nickname
                              FROM trip_chat_messages m JOIN users u ON u.user_id = m.user_id
                              WHERE m.trip_id=%s AND m.message_id > %s ORDER BY m.message_id""", (trip_id, after))
            rows = cursor.fetchall()
        else:
            cursor.execute("""SELECT * FROM (
                                  SELECT m.message_id, m.user_id, m.content, m.created_at, u.full_name, u.nickname
                                  FROM trip_chat_messages m JOIN users u ON u.user_id = m.user_id
                                  WHERE m.trip_id=%s ORDER BY m.message_id DESC LIMIT 200
                              ) recent ORDER BY message_id""", (trip_id,))
            rows = cursor.fetchall()
        members = _chat_members(cursor, trip_id)
        cursor.execute("SELECT COALESCE(MAX(message_id),0) AS latest FROM trip_chat_messages WHERE trip_id=%s", (trip_id,))
        latest_id = int(cursor.fetchone()["latest"])
        payload = {
            "me": session["user_id"],
            "latest_id": latest_id,
            "messages": [{
                "id": r["message_id"], "user_id": r["user_id"], "name": _display_name(r),
                "content": r["content"], "time": r["created_at"].strftime("%m/%d %H:%M"),
            } for r in rows],
            "members": [{
                "user_id": m["user_id"], "name": _display_name(m), "role": m["member_role"],
                "last_read": int(m["last_read_message_id"]),
                "last_seen": m["last_seen_at"].strftime("%m/%d %H:%M") if m["last_seen_at"] else None,
            } for m in members],
            "votes": _open_vote_progress(cursor, trip_id, members),
        }
    finally:
        cursor.close(); connection.close()
    return jsonify(payload)


@member_bp.route("/trips/<int:trip_id>/chat", methods=["POST"])
@login_required("member")
def chat_send(trip_id):
    content = ((request.get_json(silent=True) or {}).get("content") or "").strip()
    if not content: return jsonify(error="訊息不能是空的。"), 400
    if len(content) > CHAT_MAX_LENGTH: return jsonify(error=f"訊息最多 {CHAT_MAX_LENGTH} 字。"), 400
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        if not _member_access(cursor, trip_id, session["user_id"]):
            return jsonify(error="你沒有這個行程的聊天權限。"), 403
        message_id = _post_chat_message(cursor, trip_id, session["user_id"], content)
        connection.commit()
    except Exception:
        connection.rollback(); return jsonify(error="訊息送出失敗，請再試一次。"), 500
    finally:
        cursor.close(); connection.close()
    return jsonify(ok=True, message_id=message_id)


@member_bp.route("/trips/<int:trip_id>/chat/read", methods=["POST"])
@login_required("member")
def chat_mark_read(trip_id):
    """把目前使用者的已讀位置往前推（只會前進，不會倒退）。"""
    last_read = (request.get_json(silent=True) or {}).get("last_read_message_id")
    if not isinstance(last_read, int) or last_read <= 0: return jsonify(error="已讀位置無效。"), 400
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        if not _member_access(cursor, trip_id, session["user_id"]):
            return jsonify(error="你沒有查看此行程的權限。"), 403
        cursor.execute("SELECT COALESCE(MAX(message_id),0) AS latest FROM trip_chat_messages WHERE trip_id=%s", (trip_id,))
        last_read = min(last_read, int(cursor.fetchone()["latest"]))
        cursor.execute("""INSERT INTO trip_chat_reads (trip_id,user_id,last_read_message_id) VALUES (%s,%s,%s)
                          ON DUPLICATE KEY UPDATE last_read_message_id=GREATEST(last_read_message_id, VALUES(last_read_message_id)), last_seen_at=NOW()""",
                       (trip_id, session["user_id"], last_read))
        connection.commit()
    except Exception:
        connection.rollback(); return jsonify(error="更新已讀失敗。"), 500
    finally:
        cursor.close(); connection.close()
    return jsonify(ok=True)


@member_bp.route("/trips/<int:trip_id>/chat/nudge/<int:vote_id>", methods=["POST"])
@login_required("member")
def chat_nudge_vote(trip_id, vote_id):
    """在聊天室發一則提醒，點名還沒投票的成員。"""
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        if not _member_access(cursor, trip_id, session["user_id"]):
            return jsonify(error="你沒有這個行程的聊天權限。"), 403
        progress = next((v for v in _open_vote_progress(cursor, trip_id, _chat_members(cursor, trip_id)) if v["vote_id"] == vote_id), None)
        if not progress: return jsonify(error="這個投票已結束或不存在。"), 404
        if not progress["pending"]: return jsonify(error="大家都投完票了！"), 400
        names = "、".join("@" + p["name"] for p in progress["pending"])
        content = f"📣 {names} 還沒投「{progress['title']}」喔，截止時間 {progress['deadline']}，記得去投票！"
        message_id = _post_chat_message(cursor, trip_id, session["user_id"], content)
        connection.commit()
    except Exception:
        connection.rollback(); return jsonify(error="提醒送出失敗，請再試一次。"), 500
    finally:
        cursor.close(); connection.close()
    return jsonify(ok=True, message_id=message_id)


@member_bp.route("/trips/<int:trip_id>/expenses", methods=["POST"])
@login_required("member")
def add_expense(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    saved_receipts = []
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        name = request.form.get("expense_name", "").strip(); amount = request.form.get("amount", "").strip()
        try:
            items = _parse_expense_items(request.form, request.files, request.form.get("expense_date", "")); item_error = None
        except ValueError as error:
            items = []; item_error = str(error)
        try:
            # 沒填金額但有發票明細時，用明細合計當金額
            amount = Decimal(amount) if amount else (sum((i["amount"] for i in items), Decimal("0")) if items else None)
            if amount is not None and amount < 0: raise InvalidOperation
        except (InvalidOperation, ValueError):
            amount = None
        # 分攤對象：勾選的旅程成員（只接受目前已加入行程的人）
        cursor.execute("SELECT user_id FROM trip_members WHERE trip_id=%s AND join_status='accepted'", (trip_id,))
        member_ids = {row["user_id"] for row in cursor.fetchall()}
        split_ids = sorted({int(uid) for uid in request.form.getlist("split_user_ids") if uid.isdigit()} & member_ids)
        # 只勾自己＝個人支出，不產生分帳
        scope = "personal" if split_ids == [session["user_id"]] else "shared"

        if not trip: flash("你沒有管理費用的權限。", "error")
        elif not split_ids: flash("請至少勾選一位分攤的成員。", "error")
        elif item_error: flash(item_error, "error")
        elif not name or amount is None or not request.form.get("expense_date"): flash("請完整填寫費用名稱、金額（或發票明細）與日期。", "error")
        else:
            payer_id = session["user_id"]
            cursor.execute("""INSERT INTO expenses (trip_id,created_by,payer_id,expense_name,expense_type,scope,amount,currency,expense_date,note)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (trip_id, payer_id, payer_id, name, request.form.get("expense_type", "actual"), scope, amount, trip["currency"], request.form["expense_date"], request.form.get("note", "").strip() or None))
            expense_id = cursor.lastrowid
            for idx, item in enumerate(items):
                receipt = save_uploaded_attachment(item["receipt"], "receipts")
                receipt_path = receipt["relative_path"] if receipt else None
                if receipt_path: saved_receipts.append(receipt_path)
                cursor.execute("INSERT INTO expense_items (expense_id,item_date,description,amount,receipt_path,sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
                               (expense_id, item["date"], item["description"], item["amount"], receipt_path, idx))

            if scope == "shared":
                member_count = len(split_ids)
                base_share = (amount / member_count).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                remainder_cents = int(((amount - base_share * member_count) * 100).to_integral_value())
                for idx, uid in enumerate(split_ids):
                    share = base_share + (Decimal("0.01") if idx < remainder_cents else Decimal("0"))
                    status = "paid" if uid == payer_id else "unpaid"
                    cursor.execute(
                        "INSERT INTO expense_splits (expense_id,user_id,split_amount,settlement_status,paid_at) VALUES (%s,%s,%s,%s,%s)",
                        (expense_id, uid, share, status, datetime.now() if status == "paid" else None)
                    )

            connection.commit(); flash(f"費用已記錄，由 {len(split_ids)} 位成員平均分攤。" if scope == "shared" else "費用已記錄（個人支出，不分攤）。", "success")
    except Exception:
        connection.rollback(); flash("儲存費用失敗。", "error")
        for path in saved_receipts: delete_uploaded_image(path)
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#budget")


@member_bp.route("/trips/<int:trip_id>/splits/<int:split_id>/mark-paid", methods=["POST"])
@login_required("member")
def mark_split_paid(trip_id, split_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("""
            SELECT es.*, e.payer_id, e.trip_id
            FROM expense_splits es JOIN expenses e ON e.expense_id = es.expense_id
            WHERE es.split_id=%s
        """, (split_id,))
        split = cursor.fetchone()

        if not trip or not split or split["trip_id"] != trip_id:
            flash("找不到這筆分帳紀錄。", "error")
        elif session["user_id"] not in (split["user_id"], split["payer_id"]) and trip["member_role"] != "owner":
            flash("只有本人、代墊者或行程建立者可以標記付款狀態。", "error")
        else:
            new_status = "unpaid" if split["settlement_status"] == "paid" else "paid"
            cursor.execute(
                "UPDATE expense_splits SET settlement_status=%s, paid_at=%s WHERE split_id=%s",
                (new_status, datetime.now() if new_status == "paid" else None, split_id)
            )
            connection.commit()
            flash("已更新付款狀態。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#budget")


@member_bp.route("/trips/<int:trip_id>/attachments", methods=["POST"])
@login_required("member")
def add_attachment(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        file_storage = request.files.get("file")

        if not trip:
            flash("你沒有查看此行程的權限。", "error")
        elif not file_storage or not file_storage.filename:
            flash("請選擇要上傳的檔案。", "error")
        else:
            try:
                saved = save_uploaded_attachment(file_storage, "attachments")
            except ValueError as error:
                flash(str(error), "error")
                saved = None

            if saved:
                cursor.execute("""
                    INSERT INTO attachments (uploaded_by,trip_id,file_name,stored_name,file_path,file_type,file_size)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (session["user_id"], trip_id, saved["file_name"], saved["stored_name"], saved["relative_path"], saved["file_type"], saved["file_size"]))
                connection.commit()
                flash("檔案已上傳。", "success")
    except Exception:
        connection.rollback(); flash("上傳失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#attachments")


@member_bp.route("/trips/<int:trip_id>/attachments/<int:attachment_id>/delete", methods=["POST"])
@login_required("member")
def delete_attachment(trip_id, attachment_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM attachments WHERE attachment_id=%s AND trip_id=%s", (attachment_id, trip_id))
        attachment = cursor.fetchone()

        if not trip or not attachment:
            flash("找不到這個附件。", "error")
        elif attachment["uploaded_by"] != session["user_id"] and trip["member_role"] != "owner":
            flash("只有上傳者本人或行程建立者可以刪除附件。", "error")
        else:
            cursor.execute("DELETE FROM attachments WHERE attachment_id=%s", (attachment_id,))
            connection.commit()
            delete_uploaded_image(attachment["file_path"])
            flash("附件已刪除。", "success")
    except Exception:
        connection.rollback(); flash("刪除失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#attachments")


@member_bp.route("/trips/<int:trip_id>/invite", methods=["POST"])
@login_required("member")
def invite_member(trip_id):
    username=request.form.get("username", "").strip(); role=request.form.get("assigned_role", "viewer")
    expires_at=request.form.get("expires_at", "").strip() or None
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor=connection.cursor(dictionary=True)
    try:
        trip=_member_access(cursor,trip_id,session["user_id"])
        if not trip or trip["member_role"] != "owner": flash("只有建立者可以邀請成員。", "error")
        elif role not in ("editor","viewer"): flash("請選擇有效的成員權限。", "error")
        else:
            cursor.execute("SELECT user_id,email FROM users WHERE username=%s AND role='member' AND status='active'", (username,)); invitee=cursor.fetchone()
            if not invitee: flash("找不到可邀請的一般會員帳號。", "error")
            else:
                cursor.execute("SELECT trip_member_id FROM trip_members WHERE trip_id=%s AND user_id=%s",(trip_id,invitee["user_id"]))
                if cursor.fetchone(): flash("此會員已經在行程中。", "error")
                else:
                    cursor.execute("SELECT invitation_id FROM trip_invitations WHERE trip_id=%s AND invitee_id=%s AND status='pending'",(trip_id,invitee["user_id"]))
                    if cursor.fetchone(): flash("已經有一筆待回覆的邀請了。", "error")
                    else:
                        code=secrets.token_urlsafe(8)
                        cursor.execute("INSERT INTO trip_invitations (trip_id,inviter_id,invitee_id,invitee_email,invite_code,assigned_role,expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",(trip_id,session["user_id"],invitee["user_id"],invitee["email"],code,role,expires_at))
                        cursor.execute("INSERT INTO notifications (user_id,trip_id,notification_type,title,message,target_url) VALUES (%s,%s,'invitation','收到旅程邀請',%s,%s)",(invitee["user_id"],trip_id,f"你被邀請加入「{trip['trip_name']}」",url_for('member.dashboard')))
                        connection.commit(); flash("邀請已送出。", "success")
    except Exception:
        connection.rollback(); flash("送出邀請失敗。", "error")
    finally: cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail",trip_id=trip_id)+"#members")


@member_bp.route("/trips/<int:trip_id>/invitations/<int:invitation_id>/cancel", methods=["POST"])
@login_required("member")
def cancel_invitation(trip_id, invitation_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有建立者可以取消邀請。", "error")
        else:
            cursor.execute("SELECT invitation_id FROM trip_invitations WHERE invitation_id=%s AND trip_id=%s AND status='pending'", (invitation_id, trip_id))
            if not cursor.fetchone():
                flash("找不到這筆待回覆的邀請。", "error")
            else:
                cursor.execute("UPDATE trip_invitations SET status='cancelled',responded_at=NOW() WHERE invitation_id=%s", (invitation_id,))
                connection.commit()
                flash("邀請已取消。", "success")
    except Exception:
        connection.rollback(); flash("取消邀請失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#members")


@member_bp.route("/trips/<int:trip_id>/members/<int:member_user_id>/remove", methods=["POST"])
@login_required("member")
def remove_member(trip_id, member_user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有建立者可以移除成員。", "error")
        elif member_user_id == session["user_id"]:
            flash("不能移除自己。", "error")
        else:
            cursor.execute("SELECT trip_member_id FROM trip_members WHERE trip_id=%s AND user_id=%s AND join_status='accepted' AND member_role != 'owner'", (trip_id, member_user_id))
            if not cursor.fetchone():
                flash("找不到這位成員。", "error")
            else:
                cursor.execute("UPDATE trip_members SET join_status='removed' WHERE trip_id=%s AND user_id=%s", (trip_id, member_user_id))
                cursor.execute("INSERT INTO notifications (user_id,trip_id,notification_type,title,message,target_url) VALUES (%s,%s,'trip_update','已被移出行程',%s,%s)", (member_user_id, trip_id, f"你已被移出行程「{trip['trip_name']}」", url_for('member.dashboard')))
                connection.commit()
                flash("已移除該成員。", "success")
    except Exception:
        connection.rollback(); flash("移除成員失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#members")


@member_bp.route("/trips/<int:trip_id>/members/<int:member_user_id>/role", methods=["POST"])
@login_required("member")
def update_member_role(trip_id, member_user_id):
    new_role = request.form.get("member_role", "")
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有建立者可以調整成員權限。", "error")
        elif new_role not in ("editor", "viewer"):
            flash("請選擇有效的成員權限。", "error")
        else:
            cursor.execute("SELECT trip_member_id FROM trip_members WHERE trip_id=%s AND user_id=%s AND join_status='accepted' AND member_role != 'owner'", (trip_id, member_user_id))
            if not cursor.fetchone():
                flash("找不到這位成員。", "error")
            else:
                cursor.execute("UPDATE trip_members SET member_role=%s WHERE trip_id=%s AND user_id=%s", (new_role, trip_id, member_user_id))
                connection.commit()
                flash("已更新成員權限。", "success")
    except Exception:
        connection.rollback(); flash("更新成員權限失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#members")


@member_bp.route("/invitations/<int:invitation_id>/<action>", methods=["POST"])
@login_required("member")
def respond_invitation(invitation_id, action):
    if action not in ("accept","reject"): return redirect(url_for("member.dashboard"))
    connection=_connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor=connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM trip_invitations WHERE invitation_id=%s AND invitee_id=%s AND status='pending'",(invitation_id,session["user_id"])); invite=cursor.fetchone()
        if invite:
            cursor.execute("SELECT deleted_at FROM trips WHERE trip_id=%s", (invite["trip_id"],)); invite_trip = cursor.fetchone()
            if not invite_trip or invite_trip["deleted_at"]: invite = None
        if not invite: flash("找不到有效邀請，行程可能已被刪除。", "error")
        elif invite["expires_at"] and invite["expires_at"] < datetime.now():
            cursor.execute("UPDATE trip_invitations SET status='expired' WHERE invitation_id=%s",(invitation_id,)); connection.commit(); flash("這筆邀請已經過期了。", "error")
        elif action == "reject":
            cursor.execute("UPDATE trip_invitations SET status='rejected',responded_at=NOW() WHERE invitation_id=%s",(invitation_id,)); connection.commit(); flash("已拒絕邀請。", "success")
        else:
            cursor.execute("UPDATE trip_invitations SET status='accepted',responded_at=NOW() WHERE invitation_id=%s",(invitation_id,))
            cursor.execute("INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,%s,'accepted',NOW())",(invite["trip_id"],session["user_id"],invite["assigned_role"]))
            connection.commit(); flash("已加入旅程！", "success")
    except Exception:
        connection.rollback(); flash("處理邀請失敗。", "error")
    finally: cursor.close(); connection.close()
    return redirect(url_for("member.dashboard"))


@member_bp.route("/profile", methods=["GET", "POST"])
@login_required("member")
def profile():
    connection=_connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor=connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id,username,full_name,nickname,email,avatar_path,created_at,status FROM users WHERE user_id=%s",(session["user_id"],)); user=cursor.fetchone()
        if user:
            user["status_label"] = {"active": "啟用", "disabled": "停用"}.get(user["status"], user["status"])
        if request.method == "POST":
            nickname=request.form.get("nickname","").strip(); email=request.form.get("email","").strip()
            if not email: flash("電子郵件不可空白。", "error")
            else:
                cursor.execute("SELECT user_id FROM users WHERE email=%s AND user_id<>%s",(email,session["user_id"])); existing=cursor.fetchone()
                if existing: flash("此電子郵件已被使用。", "error")
                else:
                    # 頭像：有選新圖片就換新圖；有勾「移除頭像」就清空，改回顯示暱稱第一個字
                    old_avatar = user["avatar_path"]; avatar_path = old_avatar
                    try:
                        uploaded_path = save_uploaded_image(request.files.get("avatar"), "avatars")
                    except ValueError as exc:
                        flash(str(exc), "error"); return redirect(url_for("member.profile"))
                    if uploaded_path: avatar_path = uploaded_path
                    elif request.form.get("remove_avatar") == "1": avatar_path = None
                    cursor.execute("UPDATE users SET nickname=%s,email=%s,avatar_path=%s WHERE user_id=%s",(nickname or None,email,avatar_path,session["user_id"])); connection.commit()
                    if old_avatar != avatar_path and old_avatar and not old_avatar.startswith("http"): delete_uploaded_image(old_avatar)
                    session["nickname"]=nickname; flash("個人資料已更新。", "success"); return redirect(url_for("member.profile"))
    finally: cursor.close(); connection.close()
    return render_template("member/profile.html", user=user)


@member_bp.route("/profile/password", methods=["GET", "POST"])
@login_required("member")
def change_password():
    if request.method == "GET":
        return render_template("member/change_password.html")

    current=request.form.get("current_password",""); new=request.form.get("new_password",""); confirm=request.form.get("confirm_password","")
    if len(new)<6 or new != confirm: flash("新密碼至少 6 碼，且兩次輸入必須一致。", "error"); return redirect(url_for("member.change_password"))
    connection=_connection_or_home()
    if connection is None: return redirect(url_for("member.change_password"))
    cursor=connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM users WHERE user_id=%s",(session["user_id"],)); user=cursor.fetchone()
        if not user or not check_password_hash(user["password_hash"],current): flash("目前密碼不正確。", "error"); return redirect(url_for("member.change_password"))
        else: cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s",(generate_password_hash(new),session["user_id"])); connection.commit(); flash("密碼已更新。", "success")
    finally: cursor.close(); connection.close()
    return redirect(url_for("member.profile"))
