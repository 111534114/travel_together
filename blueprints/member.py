from collections import Counter
from datetime import date, datetime, timedelta, time as dt_time
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from io import BytesIO
import json
import weather
import os
import re
import secrets

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash, generate_password_hash

from auth import login_required
from blueprints.home_banners import fetch_active_banners  # 首頁圖片跑馬燈(後台可修改)
from attraction_rankings import TAIWAN_COUNTIES, count_attraction_rankings, fetch_attraction_rankings
from restaurant_rankings import fetch_restaurant_rankings
from accommodation_rankings import fetch_accommodation_rankings
from nearby_attractions import find_nearby_attractions
from notification_preferences import NOTIFICATION_CATEGORIES, get_preferences, save_preferences, send_notification
import trip_preferences
from db import get_db_connection
from utils import delete_uploaded_image, format_hm, get_cities, get_countries, google_maps_url, save_uploaded_attachment, save_uploaded_image
from content_moderation import is_image_explicit
from chat_moderation import REMOVED_CHAT_CONTENT, blocked_term, remove_trip_message
import smart_trip
import trip_request
import proposal_review
import pre_trip_check
import pending_actions
import booking_compare
from place_matching import SITE_PLACE_COLUMNS, find_site_place, search_site_places
import currency_rates
import theme_parks
import weather
from ai_client import AIUnavailable, ai_ready, ask_json


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
PREFERENCE_ACTIVITY_TAGS = ["觀光景點", "在地美食", "購物", "戶外活動", "文化體驗", "夜生活", "拍照打卡", "放鬆度假"]
PREFERENCE_INTENSITY_LABELS = [("relaxed", "輕鬆型"), ("standard", "標準型"), ("packed", "充實型"), ("family", "親子型"), ("senior_friendly", "長輩友善型")]

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
COMMENT_REPORT_REASONS = (
    "含有不當內容（辱罵、歧視、仇恨言論等）",
    "騷擾或人身攻擊",
    "廣告或垃圾訊息",
    "含有個資或敏感資訊",
    "其它",
)
COMMENT_REPORT_PREFIX = "留言檢舉："
TRIP_TRASH_DAYS = 30  # 軟刪除的行程保留天數，過期後自動永久刪除
MAX_POST_IMAGES = 6


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


def _linked_active_friend_group(cursor, trip_id):
    cursor.execute("SELECT group_id FROM friend_groups WHERE trip_id=%s AND status != 'cancelled' LIMIT 1", (trip_id,))
    return cursor.fetchone()


def _build_trips_timeline(cursor, trip_rows, user_id, favorite_trip_ids=None, reported_trip_ids=None):
    """把一組行程資料組成給「查看行程」彈窗用的 JSON：每日明細 + 是否能複製/回報/收藏。"""
    favorite_trip_ids = favorite_trip_ids or set()
    reported_trip_ids = reported_trip_ids or set()
    timeline_json = {}
    if not trip_rows:
        return timeline_json
    trip_ids = [t["trip_id"] for t in trip_rows]
    placeholders = ",".join(["%s"] * len(trip_ids))
    cursor.execute(f"""
        SELECT trip_id, itinerary_date, title, start_time, end_time, address, estimated_cost
        FROM itineraries WHERE trip_id IN ({placeholders})
        ORDER BY itinerary_date ASC, start_time ASC
    """, tuple(trip_ids))
    all_itineraries = cursor.fetchall()
    for trip in trip_rows:
        timeline = []
        items = [item for item in all_itineraries if item["trip_id"] == trip["trip_id"]]
        for index, item in enumerate(items, 1):
            date_text = str(item["itinerary_date"]) if item["itinerary_date"] else f"第 {index} 天"
            time_text = f" ({format_hm(item['start_time'])} - {format_hm(item['end_time'])})" if item["start_time"] else ""
            address_text = f" ｜ 地址: {item['address']}" if item["address"] else ""
            cost_text = f" (預估金額: NT$ {item['estimated_cost']:,.0f})" if item["estimated_cost"] else ""
            timeline.append({"day": f"📍 {date_text}{time_text}", "desc": f"{item['title']}{address_text}{cost_text}"})
        timeline_json[str(trip["trip_id"])] = {
            "title": trip["trip_name"],
            "author": trip.get("owner_nickname") or trip.get("owner_name"),
            "days": f"{trip['days_count']} 天",
            "budget": (f"{trip['currency']} {trip['total_budget']:,.0f}" if trip.get("total_budget") is not None else "未提供預算"),
            "timeline": timeline,
            "can_issue": trip["owner_id"] != user_id and trip["trip_id"] not in reported_trip_ids,
            "can_duplicate": trip["owner_id"] == user_id or bool(trip.get("allow_copy")),
            "is_favorited": trip["trip_id"] in favorite_trip_ids,
        }
    return timeline_json


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


def _load_proposal_comments(cursor, trip_id):
    """提案底下的留言。(整趟行程的留言討論、每日行程項目底下的留言都已拿掉，旅伴改用聊天室)"""
    cursor.execute("""
        SELECT c.*, u.full_name, u.nickname
        FROM comments c JOIN users u ON u.user_id = c.user_id
        WHERE c.trip_id=%s AND c.status='visible' AND c.proposal_id IS NOT NULL
        ORDER BY c.created_at ASC
    """, (trip_id,))
    proposal_comments = {}
    for row in cursor.fetchall():
        proposal_comments.setdefault(row["proposal_id"], []).append(row)
    return proposal_comments


# 留言 @提及：@暱稱（或本名）提及特定旅伴，@ALL／@所有人 通知全部旅伴
MENTION_ALL_KEYWORDS = ("ALL", "所有人")


def _load_mention_members(cursor, trip_id):
    cursor.execute("""SELECT u.user_id, u.full_name, u.nickname FROM trip_members tm JOIN users u ON u.user_id=tm.user_id
                      WHERE tm.trip_id=%s AND tm.join_status='accepted'""", (trip_id,))
    return cursor.fetchall()


def _mention_pattern(members):
    """回傳 (正則, 名稱→user_id 集合)。名稱由長到短排，避免「小明」先吃掉「小明明」。"""
    lookup = {}
    for m in members:
        for name in (m.get("nickname"), m.get("full_name")):
            if name and name.strip():
                lookup.setdefault(name.strip().casefold(), set()).add(m["user_id"])
    alternatives = [re.escape(k) for k in MENTION_ALL_KEYWORDS] + [re.escape(name) for name in lookup]
    alternatives.sort(key=len, reverse=True)
    # ALL 後面不能緊接英數字，免得 @allen 被當成 @ALL
    alternatives = [a + r"(?![A-Za-z0-9_])" if a == "ALL" else a for a in alternatives]
    return re.compile("@(" + "|".join(alternatives) + ")", re.IGNORECASE), lookup


def _mentioned_user_ids(content, members):
    pattern, lookup = _mention_pattern(members)
    all_keywords = {k.casefold() for k in MENTION_ALL_KEYWORDS}
    user_ids = set()
    for match in pattern.finditer(content or ""):
        token = match.group(1).casefold()
        if token in all_keywords:
            return {m["user_id"] for m in members}
        user_ids |= lookup.get(token, set())
    return user_ids


def _notify_mentions(cursor, trip, members, content, anchor, author_id, exclude_ids=(), place="留言"):
    target_ids = _mentioned_user_ids(content, members) - {author_id} - set(exclude_ids)
    if not target_ids: return
    author = next((m for m in members if m["user_id"] == author_id), {})
    author_name = author.get("nickname") or author.get("full_name") or "旅伴"
    snippet = content if len(content) <= 60 else content[:60] + "…"
    title = f"有人在{place}中提及你"
    message = f"{author_name} 在「{trip['trip_name']}」的{place}中提及了你：{snippet}"
    target_url = url_for("member.trip_detail", trip_id=trip["trip_id"]) + anchor
    for user_id in target_ids:
        send_notification(cursor, user_id, "mention", "comment", title, message, target_url, trip_id=trip["trip_id"])


@member_bp.app_template_filter("mentions")
def render_mentions(content, members):
    """把留言裡的 @提及 包成 <span class="mention">，其餘文字照常跳脫。"""
    content = content or ""
    if not members: return escape(content)
    pattern, _ = _mention_pattern(members)
    parts, last = [], 0
    for match in pattern.finditer(content):
        parts.append(escape(content[last:match.start()]))
        parts.append(Markup('<span class="mention">{}</span>').format(match.group(0)))
        last = match.end()
    parts.append(escape(content[last:]))
    return Markup("").join(parts)


def _load_trip_preferences(cursor, trip_id, user_id):
    """載入這趟行程所有成員已經填過的旅伴偏好，順便即時算出團體統計(不是寫死的範例資料)。"""
    # 先容許程式碼部署、稍後才套用資料表遷移；缺表時其他行程功能仍可正常開啟。
    cursor.execute("SHOW TABLES LIKE 'trip_preferences'")
    if cursor.fetchone() is None:
        return {"available": False, "my_pref": None, "submitted_count": 0}
    cursor.execute("SELECT * FROM trip_preferences WHERE trip_id=%s", (trip_id,))
    rows = cursor.fetchall()
    my_pref = next((r for r in rows if r["user_id"] == user_id), None)

    like_counter = Counter()
    intensity_counter = Counter()
    budgets = []
    must_visit_items = []
    avoid_items = []
    for row in rows:
        if row["like_activities"]:
            like_counter.update(tag for tag in row["like_activities"].split(",") if tag)
        if row["intensity"]:
            intensity_counter[row["intensity"]] += 1
        if row["budget_limit"]:
            budgets.append(row["budget_limit"])
        if row["must_visit"]:
            must_visit_items.extend(line.strip() for line in row["must_visit"].splitlines() if line.strip())
        if row["avoid_places"]:
            avoid_items.extend(line.strip() for line in row["avoid_places"].splitlines() if line.strip())

    max_like_count = max(like_counter.values()) if like_counter else 0
    like_stats = sorted(
        ((tag, like_counter.get(tag, 0), round(like_counter.get(tag, 0) / max_like_count * 100) if max_like_count else 0)
         for tag in PREFERENCE_ACTIVITY_TAGS),
        key=lambda item: -item[1],
    )

    max_intensity_count = max(intensity_counter.values()) if intensity_counter else 0
    intensity_stats = [
        (label, intensity_counter.get(value, 0), round(intensity_counter.get(value, 0) / max_intensity_count * 100) if max_intensity_count else 0)
        for value, label in PREFERENCE_INTENSITY_LABELS
    ]

    return {
        "available": True,
        "my_pref": my_pref,
        "submitted_count": len(rows),
        "like_stats": like_stats,
        "intensity_stats": intensity_stats,
        "avg_budget": (sum(budgets) / len(budgets)) if budgets else None,
        "must_visit_items": must_visit_items,
        "avoid_items": avoid_items,
    }


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
        "introduction": "" if form.get("introduction", "").strip() == "None" else form.get("introduction", "").strip(),  # 舊版表單會把空的介紹送成「None」
        "visibility": form.get("visibility", "private").strip(),
        "allow_copy": 1 if form.get("allow_copy") == "on" else 0,
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
            "visitor.html", is_member=True, line_status=None,
            trips_timeline_json={}, city_weather={}, issue_reasons=ISSUE_REASONS,
        )
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        # LINE 官方帳號好友狀態：用來決定首頁要不要顯示「加入官方帳號」提示
        cursor.execute("SELECT line_sub IS NOT NULL AS linked, line_friend FROM users WHERE user_id=%s", (user_id,))
        line_status = cursor.fetchone()
        home_banners = fetch_active_banners(cursor)
        featured_trips, trips_timeline_json = _fetch_featured_public_trips(cursor, user_id)
        planning_trips = _fetch_planning_trips(cursor, user_id)
        quick_cities = get_cities(cursor)
    finally:
        cursor.close(); connection.close()
    return render_template(
        "visitor.html", is_member=True, line_status=line_status,
        trips_timeline_json=trips_timeline_json, issue_reasons=ISSUE_REASONS,
        home_banners=home_banners, featured_trips=featured_trips, planning_trips=planning_trips,
        quick_cities=quick_cities,
        pending_ai_query=session.pop("pending_ai_query", None),  # 訪客登入前打好的 AI 排行程需求(只用一次)
    )


WEEKDAY_LABELS = "一二三四五六日"


def _weather_default_cities(all_weather):
    """還沒自選縣市時預設顯示的縣市：公開行程的目的地(只有台灣縣市查得到)，都沒有就顯示台北市。"""
    connection = get_db_connection()
    if connection is None:
        return ["台北市"] if "台北市" in all_weather else list(all_weather)[:1]
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT DISTINCT ci.name AS city
            FROM trips t JOIN cities ci ON ci.city_id = t.city_id
            WHERE t.visibility = 'public' AND t.moderation_status = 'visible' AND t.deleted_at IS NULL
        """)
        names = [weather.normalize_city_name(row["city"]) for row in cursor.fetchall() if row.get("city")]
    except Exception as error:
        print("目的地天氣預設縣市查詢失敗：", error)
        names = []
    finally:
        cursor.close(); connection.close()
    defaults = [name for name in dict.fromkeys(names) if name in all_weather]
    if not defaults and all_weather:
        defaults = ["台北市"] if "台北市" in all_weather else list(all_weather)[:1]
    return defaults


@member_bp.route("/weather")  # 訪客不用登入也能看(跟旅遊相簿一致)：自選縣市的中央氣象署 7 天預報
def weather_page():
    all_weather = weather.get_all_county_weather()
    for data in all_weather.values():  # 幫每一天加上「週幾」，頁面顯示用
        for day in data["days"]:
            try:
                day["weekday"] = "週" + WEEKDAY_LABELS[datetime.strptime(day["date"], "%Y-%m-%d").weekday()]
            except (TypeError, ValueError):
                day["weekday"] = ""
    regions = [(region, [name for name in names if name in all_weather]) for region, names in weather.COUNTY_REGIONS]
    return render_template(
        "member/weather.html",
        city_weather=all_weather,
        weather_regions=[(region, names) for region, names in regions if names],
        weather_defaults=_weather_default_cities(all_weather),
        weather_summary={  # 地圖滑過縣市時的提示文字，例如「☀️ 晴時多雲 22°～28°」
            name: f"{data['today']['emoji']} {data['today']['weather']} {data['today']['min']}°～{data['today']['max']}°"
            for name, data in all_weather.items()
        },
    )


def _fetch_planning_trips(cursor, user_id, limit=3):
    """會員首頁 STEP 2：自己建立或已加入、還沒結束的行程，方便直接進去微調路線與時間。"""
    try:
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, co.name AS country, ci.name AS city,
                   t.start_date, t.end_date, t.owner_id,
                   DATEDIFF(t.end_date, t.start_date) + 1 AS days_count,
                   (SELECT COUNT(*) FROM itineraries i WHERE i.trip_id = t.trip_id) AS item_count
            FROM trips t
            JOIN trip_members tm ON tm.trip_id = t.trip_id AND tm.user_id = %s AND tm.join_status = 'accepted'
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE t.deleted_at IS NULL AND t.moderation_status = 'visible' AND t.end_date >= CURDATE()
            ORDER BY t.start_date ASC, t.trip_id DESC
            LIMIT %s
        """, (user_id, limit))
        return cursor.fetchall()
    except Exception as error:  # 查詢失敗不影響首頁其他區塊
        print("會員首頁規劃中行程查詢失敗：", error)
        return []


def _fetch_featured_public_trips(cursor, user_id, limit=6):
    """會員首頁的熱門公開行程：依收藏數、加入人數排序，並附上「查看行程」彈窗用的明細。"""
    try:
        cursor.execute("""
            SELECT t.trip_id, t.owner_id, t.trip_name, co.name AS country, ci.name AS city,
                   t.start_date, t.end_date, t.people_count, t.total_budget, t.currency,
                   t.introduction, t.cover_image_path, t.allow_copy,
                   u.full_name AS owner_name, u.nickname AS owner_nickname,
                   DATEDIFF(t.end_date, t.start_date) + 1 AS days_count,
                   (SELECT COUNT(*) FROM itineraries i WHERE i.trip_id = t.trip_id) AS item_count,
                   (SELECT COUNT(*) FROM favorites f WHERE f.target_type = 'trip' AND f.trip_id = t.trip_id) AS favorite_count,
                   (SELECT COUNT(*) FROM trip_members tm WHERE tm.trip_id = t.trip_id AND tm.join_status = 'accepted') AS joined_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE t.visibility = 'public' AND t.moderation_status = 'visible' AND t.deleted_at IS NULL
            ORDER BY favorite_count DESC, joined_count DESC, t.trip_id DESC
            LIMIT %s
        """, (limit,))
        trips = cursor.fetchall()
        cursor.execute("SELECT trip_id FROM favorites WHERE user_id=%s AND target_type='trip'", (user_id,))
        favorite_ids = {row["trip_id"] for row in cursor.fetchall()}
        cursor.execute("""
            SELECT target_id FROM reports
            WHERE reporter_id = %s AND target_type = 'trip' AND reason LIKE %s
              AND status IN ('pending', 'processing')
        """, (user_id, ISSUE_PREFIX + "%"))
        reported_ids = {row["target_id"] for row in cursor.fetchall()}
        for trip in trips:
            trip["is_favorited"] = trip["trip_id"] in favorite_ids
            trip["can_duplicate"] = trip["owner_id"] == user_id or bool(trip.get("allow_copy"))
        return trips, _build_trips_timeline(cursor, trips, user_id, favorite_ids, reported_ids)
    except Exception as error:  # 熱門行程查詢失敗不影響首頁其他區塊
        print("會員首頁熱門行程查詢失敗：", error)
        return [], {}


def _trip_unread_counts(cursor, user_id, trip_ids):
    """我的旅程每張卡片用：每趟旅程的未讀通知數、聊天室未讀訊息數。查詢失敗就當 0，不影響我的旅程頁。"""
    unread, chat_unread = {}, {}
    if not trip_ids:
        return unread, chat_unread
    marks = ",".join(["%s"] * len(trip_ids))
    try:
        cursor.execute(f"""
            SELECT trip_id, COUNT(*) AS n FROM notifications
            WHERE user_id=%s AND is_read=FALSE AND trip_id IN ({marks}) GROUP BY trip_id
        """, (user_id, *trip_ids))
        unread = {row["trip_id"]: int(row["n"]) for row in cursor.fetchall()}
    except Exception as error:
        print("讀取旅程未讀通知失敗：", error)
    try:
        # 聊天室未讀：別人傳的、比我「讀到的最後一則」還新的訊息(被團長移除的不算)
        cursor.execute(f"""
            SELECT m.trip_id, COUNT(*) AS n
            FROM trip_chat_messages m
            LEFT JOIN trip_chat_reads r ON r.trip_id = m.trip_id AND r.user_id = %s
            WHERE m.trip_id IN ({marks}) AND m.user_id <> %s
              AND m.message_id > COALESCE(r.last_read_message_id, 0) AND m.content <> %s
            GROUP BY m.trip_id
        """, (user_id, *trip_ids, user_id, REMOVED_CHAT_CONTENT))
        chat_unread = {row["trip_id"]: int(row["n"]) for row in cursor.fetchall()}
    except Exception as error:
        print("讀取聊天室未讀數失敗：", error)
    return unread, chat_unread


@member_bp.route("/trips")
@login_required("member")
def my_trips():
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        try:
            cursor.execute("DELETE FROM trips WHERE owner_id=%s AND moderation_status='visible' AND deleted_at < NOW() - INTERVAL %s DAY", (user_id, TRIP_TRASH_DAYS))
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
            WHERE t.owner_id=%s AND t.moderation_status='visible' AND t.deleted_at IS NOT NULL
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
        notice_unread, chat_unread = _trip_unread_counts(cursor, user_id, [t["trip_id"] for t in trips])
        today = date.today()
        for t in trips:
            t["notice_unread"] = notice_unread.get(t["trip_id"], 0)
            t["chat_unread"] = chat_unread.get(t["trip_id"], 0)
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
        member_stats = {"total": len(trips), "upcoming": sum(t["phase"] == "upcoming" for t in trips),
                        "ongoing": sum(t["phase"] == "ongoing" for t in trips),
                        "completed": sum(t["phase"] == "completed" for t in trips),
                        "pending": len(invitations)}

        cursor.execute("""
            SELECT target_id FROM reports
            WHERE reporter_id = %s AND target_type = 'trip' AND reason LIKE %s
              AND status IN ('pending', 'processing')
        """, (user_id, ISSUE_PREFIX + "%"))
        reported_trip_ids = {row["target_id"] for row in cursor.fetchall()}

        cursor.execute("SELECT trip_id FROM favorites WHERE user_id=%s AND target_type='trip'", (user_id,))
        favorite_trip_ids = {row["trip_id"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT t.trip_id, t.owner_id, t.trip_name, co.name AS country, ci.name AS city,
                   t.start_date, t.end_date, t.people_count, t.total_budget, t.currency,
                   t.cover_image_path, t.allow_copy, u.full_name AS owner_name, u.nickname AS owner_nickname,
                   DATEDIFF(t.end_date, t.start_date) + 1 AS days_count
            FROM favorites f
            JOIN trips t ON t.trip_id = f.trip_id
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE f.user_id=%s AND f.target_type='trip'
              AND t.moderation_status='visible' AND t.deleted_at IS NULL
            ORDER BY f.created_at DESC
        """, (user_id,))
        favorited_trips = cursor.fetchall()
        trips_timeline_json = _build_trips_timeline(cursor, favorited_trips, user_id, favorite_trip_ids, reported_trip_ids)
    finally:
        cursor.close(); connection.close()
    return render_template(
        "member/trips.html", trips=trips, invitations=invitations,
        member_stats=member_stats, favorited_trips=favorited_trips,
        trips_timeline_json=trips_timeline_json, issue_reasons=ISSUE_REASONS,
        deleted_trips=deleted_trips, trip_trash_days=TRIP_TRASH_DAYS,
    )


@member_bp.route("/companions")
@login_required("member")
def companions_page():
    """Keep older shared links working after moving companion search into the group page."""
    return redirect(url_for("friend_groups.index") + "#companions")


@member_bp.route("/public-trips")
@login_required("member")
def public_trips():
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT t.trip_id, t.owner_id, t.trip_name, co.name AS country, ci.name AS city,
                   t.people_count, t.total_budget, t.currency, t.introduction, t.start_date, t.end_date,
                   u.full_name AS owner_name, u.nickname AS owner_nickname,
                   COUNT(tm.user_id) AS joined_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            LEFT JOIN trip_members tm ON tm.trip_id = t.trip_id AND tm.join_status = 'accepted'
            WHERE t.visibility = 'public'
              AND t.moderation_status = 'visible' AND t.deleted_at IS NULL
            GROUP BY t.trip_id, t.owner_id, t.trip_name, co.name, ci.name, t.start_date, t.end_date,
                     t.people_count, t.total_budget, t.currency, t.introduction, u.full_name, u.nickname
            ORDER BY t.trip_id DESC
        """)
        trips = cursor.fetchall()
        cursor.execute("SELECT trip_id FROM favorites WHERE user_id=%s AND target_type='trip'", (session["user_id"],))
        favorite_ids = {row["trip_id"] for row in cursor.fetchall()}
    finally:
        cursor.close()
        connection.close()

    filters = {
        "region": request.args.get("region", "").strip()[:80],
        "date": request.args.get("date", "").strip(),
        "budget": request.args.get("budget", "").strip(),
    }
    max_budget = float(filters["budget"]) if filters["budget"].isdigit() else None
    visible_trips = []
    for trip in trips:
        if filters["region"] and filters["region"].casefold() not in f"{trip.get('country') or ''} {trip.get('city') or ''}".casefold():
            continue
        if filters["date"] and not (str(trip.get("start_date") or "") <= filters["date"] <= str(trip.get("end_date") or "")):
            continue
        if max_budget is not None and float(trip.get("total_budget") or 0) > max_budget:
            continue
        trip["is_favorited"] = trip["trip_id"] in favorite_ids
        visible_trips.append(trip)
    return render_template("member/public_trips.html", trips=visible_trips, filters=filters)


@member_bp.route("/announcements")  # 訪客不用登入也能看(跟旅遊相簿一致)，只顯示已發布的公告
def announcements_page():
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT announcement_id, title, content, is_pinned, publish_at, created_at
            FROM announcements
            WHERE status = 'published'
              AND (publish_at IS NULL OR publish_at <= NOW())
            ORDER BY is_pinned DESC, publish_at DESC, created_at DESC
            LIMIT 50
        """)
        announcements = cursor.fetchall()
    finally:
        cursor.close(); connection.close()
    return render_template("member/announcements.html", announcements=announcements)


@member_bp.route("/album")  # 訪客不用登入也能瀏覽(跟探索景點/餐廳/住宿一致)，純粹展示公開核准的相簿貼文，沒有個人化內容
def album_page():
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT p.post_id, pi.image_path, p.caption,
                   a.attraction_id, a.name AS attraction_name,
                   u.nickname, u.full_name
            FROM attraction_posts p
            JOIN (SELECT post_id, MIN(sort_order) AS min_order
                  FROM attraction_post_images GROUP BY post_id) first_img
              ON first_img.post_id = p.post_id
            JOIN attraction_post_images pi
              ON pi.post_id = p.post_id AND pi.sort_order = first_img.min_order
            JOIN attractions a ON a.attraction_id = p.attraction_id
            JOIN users u ON u.user_id = p.user_id
            WHERE p.review_status = 'approved'
            ORDER BY p.created_at DESC LIMIT 60
        """)
        album_posts = cursor.fetchall()
    finally:
        cursor.close(); connection.close()
    return render_template("member/album.html", album_posts=album_posts)


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
            WHERE trip_id = %s AND visibility = 'public' AND moderation_status = 'visible' AND deleted_at IS NULL
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


@member_bp.route("/pending-action")
@login_required("member")
def run_pending_action():
    """訪客登入前按的收藏／加入行程／上傳照片(pending_actions)：登入後自動完成，再帶回原本的頁面。只會執行一次。"""
    action = session.pop("pending_action", None)
    if not action:
        return redirect(url_for("member.dashboard"))
    connection = _connection_or_home()
    if connection is None:
        return redirect(pending_actions.safe_back(action.get("back")) or url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        message, category, back = pending_actions.run(cursor, session["user_id"], action)
        connection.commit()
    except Exception as error:
        connection.rollback()
        print("登入後自動完成動作失敗：", error)
        message, category, back = "剛剛的動作沒有完成，請再按一次。", "error", pending_actions.safe_back(action.get("back")) or url_for("member.dashboard")
    finally:
        cursor.close()
        connection.close()
    if message:
        flash(message, category)
    return redirect(back)


@member_bp.route("/trips/<int:trip_id>/favorite-after-login")
@login_required("member")
def favorite_trip_after_login(trip_id):
    """訪客在首頁按「☆ 收藏」→ 登入後自動來這裡收藏那趟行程。只加入、不會取消(已經收藏過就維持)。
    只有 session 裡記著同一趟行程時才會收藏(是訪客自己按的)，別人傳來的連結不會幫你亂收藏。"""
    back = redirect(url_for("member.dashboard") + "#featured-trips")
    if session.pop("pending_favorite_trip_id", None) != trip_id:
        return back
    connection = _connection_or_home()
    if connection is None:
        return back
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT trip_name FROM trips WHERE trip_id=%s AND visibility='public' AND moderation_status='visible' AND deleted_at IS NULL", (trip_id,))
        trip = cursor.fetchone()
        if not trip:
            flash("只能收藏公開行程。", "error")
            return back
        cursor.execute("SELECT favorite_id FROM favorites WHERE user_id=%s AND trip_id=%s", (session["user_id"], trip_id))
        if cursor.fetchone():
            flash(f"「{trip['trip_name']}」已經在你的收藏裡了。", "success")
            return back
        cursor.execute("INSERT INTO favorites (user_id, target_type, trip_id) VALUES (%s,'trip',%s)", (session["user_id"], trip_id))
        connection.commit()
        flash(f"已經幫你收藏「{trip['trip_name']}」！可以到「我的旅程」的收藏裡找到它。", "success")
    except Exception as error:
        connection.rollback()
        print("登入後收藏行程失敗：", error)
        flash("收藏失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return back


@member_bp.route("/trips/<int:trip_id>/favorite", methods=["POST"])
@login_required("member")
def toggle_trip_favorite(trip_id):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard") + "#trips")
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT trip_id FROM trips WHERE trip_id=%s AND visibility='public' AND moderation_status='visible' AND deleted_at IS NULL", (trip_id,))
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


def _my_trips_unread(cursor, user_id):
    """左邊選單「我的旅程」旁邊的數字：所有(還在、已加入的)旅程的未讀通知＋聊天室未讀訊息。
    算法跟我的旅程頁每張卡片一樣，加起來會對得上。查詢失敗就當 0，不影響鈴鐺。"""
    notices = chat = 0
    try:
        cursor.execute("""
            SELECT COUNT(*) AS n FROM notifications n
            JOIN trip_members tm ON tm.trip_id = n.trip_id AND tm.user_id = n.user_id AND tm.join_status = 'accepted'
            JOIN trips t ON t.trip_id = n.trip_id AND t.deleted_at IS NULL
            WHERE n.user_id=%s AND n.is_read=FALSE
        """, (user_id,))
        notices = int(cursor.fetchone()["n"])
    except Exception as error:
        print("計算旅程未讀通知失敗：", error)
    try:
        cursor.execute("""
            SELECT COUNT(*) AS n FROM trip_chat_messages m
            JOIN trip_members tm ON tm.trip_id = m.trip_id AND tm.user_id = %s AND tm.join_status = 'accepted'
            JOIN trips t ON t.trip_id = m.trip_id AND t.deleted_at IS NULL
            LEFT JOIN trip_chat_reads r ON r.trip_id = m.trip_id AND r.user_id = %s
            WHERE m.user_id <> %s AND m.message_id > COALESCE(r.last_read_message_id, 0) AND m.content <> %s
        """, (user_id, user_id, user_id, REMOVED_CHAT_CONTENT))
        chat = int(cursor.fetchone()["n"])
    except Exception as error:
        print("計算聊天室未讀失敗：", error)
    return notices, chat


@member_bp.route("/notifications/unread")
@login_required("member")
def unread_notifications():
    if "notification_login_id" not in session:
        session["notification_login_id"] = secrets.token_hex(8)
    connection = get_db_connection()
    if connection is None:
        return jsonify({"error": "目前無法讀取通知。"}), 503
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM notifications WHERE user_id=%s AND is_read=FALSE",
            (session["user_id"],),
        )
        total = cursor.fetchone()["total"]
        # 已讀的通知也一起回傳，標為已讀後仍留在清單裡，只是改成已讀樣式
        cursor.execute("""
            SELECT n.notification_id, n.title, n.message, n.target_url, n.created_at, n.is_read,
                   CASE WHEN t.deleted_at IS NULL THEN t.trip_name END AS trip_name
            FROM notifications n LEFT JOIN trips t ON t.trip_id = n.trip_id
            WHERE n.user_id=%s
            ORDER BY n.created_at DESC, n.notification_id DESC LIMIT 30
        """, (session["user_id"],))
        notifications = cursor.fetchall()
        for notification in notifications:
            notification["created_at"] = notification["created_at"].strftime("%Y/%m/%d %H:%M")
            notification["is_read"] = bool(notification["is_read"])
        trip_notices, trip_chat = _my_trips_unread(cursor, session["user_id"])
        return jsonify({"total": total, "notifications": notifications,
                        "login_id": session["notification_login_id"],
                        "my_trips": {"notices": trip_notices, "chat": trip_chat, "total": trip_notices + trip_chat}})
    finally:
        cursor.close()
        connection.close()


@member_bp.route("/notifications/read-all", methods=["POST"])
@login_required("member")
def mark_all_notifications_read():
    connection = get_db_connection()
    if connection is None:
        return jsonify({"error": "目前無法更新通知。"}), 503
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE notifications SET is_read=TRUE, read_at=NOW()
            WHERE user_id=%s AND is_read=FALSE
        """, (session["user_id"],))
        connection.commit()
        return jsonify({"ok": True})
    except Exception:
        connection.rollback()
        return jsonify({"error": "更新通知失敗。"}), 500
    finally:
        cursor.close()
        connection.close()


@member_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required("member")
def mark_notification_read(notification_id):
    connection = _connection_or_home()
    if connection is None:
        if request.accept_mimetypes.best == "application/json":
            return jsonify({"error": "目前無法更新通知。"}), 503
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
        if request.accept_mimetypes.best == "application/json":
            return jsonify({"error": "更新通知失敗。"}), 500
        flash("通知狀態更新失敗。", "error")
    finally:
        cursor.close()
        connection.close()
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True})
    return redirect(url_for("member.dashboard"))


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


@member_bp.route("/attractions")  # 訪客不用登入也能瀏覽；收藏、加入行程等個人化動作各自的路由還是要求登入
def browse_attractions():
    user_id = session.get("user_id")
    keyword = request.args.get("keyword", "").strip()
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    favorites_only = request.args.get("favorites_only") == "1" and bool(user_id)

    connection = _connection_or_home()
    if connection is None:
        return render_template("member/attractions.html", attractions=[], countries=[], cities=[],
                                keyword=keyword, country_id=country_id, city_id=city_id,
                                favorites_only=favorites_only, ranking_preview=[], addable_trips=[],
                                taiwan_counties=TAIWAN_COUNTIES)
    cursor = connection.cursor(dictionary=True)
    try:
        conditions = ["a.status = 'active'", "a.deleted_at IS NULL"]
        params = [user_id]

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
        ranking_preview = fetch_attraction_rankings(
            cursor, country_id=country_id, city_id=city_id, keyword=keyword,
            limit=3,
        )
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        addable_trips = _addable_trips(cursor, user_id) if user_id else []
    finally:
        cursor.close(); connection.close()

    return render_template("member/attractions.html", attractions=attractions, countries=countries, cities=cities,
                            keyword=keyword, country_id=country_id, city_id=city_id, favorites_only=favorites_only,
                            ranking_preview=ranking_preview, addable_trips=addable_trips,
                            taiwan_counties=TAIWAN_COUNTIES)


@member_bp.route("/attractions/rankings")
@login_required("member")
def attraction_rankings():
    keyword = request.args.get("keyword", "").strip()[:100]
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    country_id = country_id if country_id.isdecimal() and int(country_id) > 0 else ""
    city_id = city_id if city_id.isdecimal() and int(city_id) > 0 else ""
    try:
        requested_page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        requested_page = 1

    connection = _connection_or_home()
    if connection is None:
        return render_template("member/attraction_rankings.html", rankings=[], countries=[], cities=[],
                               keyword=keyword, country_id=country_id, city_id=city_id,
                               total=0, page=1, page_count=1, rank_offset=0)
    cursor = connection.cursor(dictionary=True)
    try:
        filters = dict(country_id=country_id, city_id=city_id, keyword=keyword)
        total = count_attraction_rankings(cursor, **filters)
        page_count = max(1, (total + 19) // 20)
        page = min(requested_page, page_count)
        rank_offset = (page - 1) * 20
        rankings = fetch_attraction_rankings(cursor, **filters, limit=20, offset=rank_offset)
        countries = get_countries(cursor)
        cities = get_cities(cursor)
    finally:
        cursor.close(); connection.close()
    return render_template("member/attraction_rankings.html", rankings=rankings,
                           countries=countries, cities=cities, keyword=keyword,
                           country_id=country_id, city_id=city_id, total=total,
                           page=page, page_count=page_count, rank_offset=rank_offset)


@member_bp.route("/attractions/rankings/data")  # 排行榜彈窗用的 AJAX，純公開統計資料，訪客不用登入也能看
def attraction_rankings_data():
    """Return one ranking page for the Explore page's in-place dialog."""
    keyword = request.args.get("keyword", "").strip()[:100]
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    country_id = country_id if country_id.isdecimal() and int(country_id) > 0 else ""
    city_id = city_id if city_id.isdecimal() and int(city_id) > 0 else ""
    top_mode = request.args.get("view") == "top"
    metric = request.args.get("metric", "itineraries").strip()
    county = request.args.get("county", "").strip().replace("臺", "台")
    if top_mode and (metric not in ("itineraries", "favorites") or
                     (county and county not in TAIWAN_COUNTIES)):
        return jsonify({"error": "無效的排行榜篩選"}), 400
    try:
        requested_page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        requested_page = 1

    connection = get_db_connection()
    if connection is None:
        return jsonify({"error": "排行榜暫時無法載入，請稍後再試。"}), 503
    cursor = connection.cursor(dictionary=True)
    try:
        if top_mode:
            rankings = fetch_attraction_rankings(
                cursor, country_id=None if county else country_id or None,
                county_name=county or None,
                favorites_only=metric == "favorites",
                positive_only=metric == "itineraries", sort_by=metric, limit=5)
            return jsonify({"rankings": [{
                "rank": index, "name": row["name"], "country": row["country"],
                "city": row["city"], "itinerary_count": row["itinerary_count"],
                "favorite_count": row["favorite_count"],
                "detail_url": url_for("member.attraction_detail", attraction_id=row["attraction_id"]),
            } for index, row in enumerate(rankings, start=1)]})
        filters = dict(country_id=country_id, city_id=city_id, keyword=keyword)
        total = count_attraction_rankings(cursor, **filters)
        page_count = max(1, (total + 9) // 10)
        page = min(requested_page, page_count)
        rankings = fetch_attraction_rankings(cursor, **filters, limit=10, offset=(page - 1) * 10)
    finally:
        cursor.close()
        connection.close()
    return jsonify({
        "page": page,
        "page_count": page_count,
        "total": total,
        "rankings": [
            {
                "rank": (page - 1) * 10 + index,
                "name": row["name"],
                "country": row["country"],
                "city": row["city"],
                "itinerary_count": row["itinerary_count"],
                "favorite_count": row["favorite_count"],
                "detail_url": url_for("member.attraction_detail", attraction_id=row["attraction_id"]),
            }
            for index, row in enumerate(rankings, start=1)
        ],
    })


@member_bp.route("/attractions/<int:attraction_id>")  # 訪客不用登入也能瀏覽；收藏、留言、加入行程等個人化動作各自的路由還是要求登入
def attraction_detail(attraction_id):
    user_id = session.get("user_id")
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.browse_attractions"))
    cursor = connection.cursor(dictionary=True)
    nearby_trip = None
    nearby_trip_addable = False
    nearby_recommendations = []
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
        """, (user_id, attraction_id))
        attraction = cursor.fetchone()
        addable_trips = _addable_trips(cursor, user_id) if attraction and user_id else []
        posts = []
        if attraction:
            added_to = request.args.get("added_to", "")
            if user_id and added_to.isdigit() and len(added_to) <= 20:  # 剛加入行程後導回來的「附近景點推薦」區塊，匿名訪客不會有這個情境
                cursor.execute("""
                    SELECT i.trip_id, i.itinerary_date, t.trip_name
                    FROM itineraries i
                    JOIN trips t ON t.trip_id = i.trip_id AND t.deleted_at IS NULL
                    JOIN trip_members tm ON tm.trip_id = i.trip_id
                        AND tm.user_id = %s AND tm.join_status = 'accepted'
                        AND tm.member_role IN ('owner', 'editor')
                    WHERE i.itinerary_id = %s AND i.created_by = %s
                      AND i.item_type = 'attraction'
                """, (user_id, int(added_to), user_id))
                nearby_trip = cursor.fetchone()
                if nearby_trip:
                    nearby_trip_addable = any(
                        trip["trip_id"] == nearby_trip["trip_id"] for trip in addable_trips
                    )
                    nearby_recommendations = find_nearby_attractions(
                        cursor, attraction, nearby_trip["trip_id"], nearby_trip["itinerary_date"]
                    )
            cursor.execute("""
                SELECT p.*, u.nickname, u.full_name
                FROM attraction_posts p JOIN users u ON u.user_id = p.user_id
                WHERE p.attraction_id=%s AND (p.review_status='approved' OR p.user_id=%s)
                ORDER BY p.created_at DESC
            """, (attraction_id, user_id))
            posts = cursor.fetchall()
            if posts:
                post_ids = [post["post_id"] for post in posts]
                placeholders = ",".join(["%s"] * len(post_ids))
                cursor.execute(
                    f"SELECT post_id,image_id,image_path,sort_order FROM attraction_post_images "
                    f"WHERE post_id IN ({placeholders}) ORDER BY post_id,sort_order,image_id",
                    tuple(post_ids),
                )
                images_by_post = {}
                for row in cursor.fetchall():
                    images_by_post.setdefault(row["post_id"], []).append(row)
                for post in posts:
                    post["images"] = images_by_post.get(post["post_id"], [])
    finally:
        cursor.close(); connection.close()

    if not attraction:
        flash("找不到這個景點，或已被下架。", "error")
        return redirect(url_for("member.browse_attractions"))

    return render_template(
        "member/attraction_detail.html", a=attraction, addable_trips=addable_trips,
        posts=posts, nearby_trip=nearby_trip, nearby_trip_addable=nearby_trip_addable,
        nearby_recommendations=nearby_recommendations,
    )


@member_bp.route("/attractions/<int:attraction_id>/posts", methods=["POST"])
@login_required("member")
def add_attraction_post(attraction_id):
    caption = request.form.get("caption", "").strip()
    image_files = [file for file in request.files.getlist("images") if file and file.filename]
    target = url_for("member.attraction_detail", attraction_id=attraction_id) + "#album"
    if not caption and not image_files:
        flash("請至少上傳一張照片，或寫點什麼。", "error")
        return redirect(target)
    if len(image_files) > MAX_POST_IMAGES:
        flash(f"一篇貼文最多上傳 {MAX_POST_IMAGES} 張照片。", "error")
        return redirect(target)
    connection = _connection_or_home()
    if connection is None:
        return redirect(target)
    cursor = connection.cursor()
    image_paths = []
    try:
        cursor.execute("SELECT attraction_id FROM attractions WHERE attraction_id=%s AND status='active' AND deleted_at IS NULL", (attraction_id,))
        if not cursor.fetchone():
            flash("找不到這個景點，或已被下架。", "error")
            return redirect(url_for("member.browse_attractions"))
        image_paths = [save_uploaded_image(file, "attraction_posts") for file in image_files]
        is_explicit = any(is_image_explicit(os.path.join(current_app.static_folder, path)) for path in image_paths)
        review_note = ("系統自動偵測到疑似不適當的照片內容，已自動退回。"
                       if is_explicit else None)
        cursor.execute(
            "INSERT INTO attraction_posts "
            "(attraction_id,user_id,caption,review_status,reviewed_at,review_note) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (attraction_id, session["user_id"], caption or None,
             "rejected" if is_explicit else "pending", datetime.now() if is_explicit else None, review_note),
        )
        post_id = cursor.lastrowid
        if is_explicit:
            for path in image_paths:
                delete_uploaded_image(path)
            image_paths = []
        else:
            cursor.executemany(
                "INSERT INTO attraction_post_images (post_id,image_path,sort_order) VALUES (%s,%s,%s)",
                [(post_id, path, order) for order, path in enumerate(image_paths)],
            )
        connection.commit()
        flash("照片疑似含有不適當內容，已自動退回。" if is_explicit else "已送出，審核通過後會公開顯示。",
              "error" if is_explicit else "success")
    except ValueError as error:
        for path in image_paths:
            delete_uploaded_image(path)
        connection.rollback()
        flash(str(error), "error")
    except Exception as error:
        for path in image_paths:
            delete_uploaded_image(path)
        connection.rollback()
        print("新增景點相簿貼文失敗：", error)
        flash("分享失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(target)


@member_bp.route("/attractions/<int:attraction_id>/posts/<int:post_id>/edit", methods=["POST"])
@login_required("member")
def edit_attraction_post(attraction_id, post_id):
    caption = request.form.get("caption", "").strip()
    new_files = [file for file in request.files.getlist("images") if file and file.filename]
    remove_ids = {int(value) for value in request.form.getlist("remove_image_ids") if value.isdigit()}
    target = url_for("member.attraction_detail", attraction_id=attraction_id) + "#album"
    connection = _connection_or_home()
    if connection is None:
        return redirect(target)
    cursor = connection.cursor(dictionary=True)
    new_paths = []
    try:
        cursor.execute("SELECT user_id FROM attraction_posts WHERE post_id=%s AND attraction_id=%s FOR UPDATE", (post_id, attraction_id))
        post = cursor.fetchone()
        if not post or post["user_id"] != session["user_id"]:
            flash("找不到這則貼文，或你沒有編輯權限。", "error")
            return redirect(target)
        cursor.execute("SELECT image_id,image_path,sort_order FROM attraction_post_images WHERE post_id=%s ORDER BY sort_order,image_id", (post_id,))
        existing = cursor.fetchall()
        kept = [image for image in existing if image["image_id"] not in remove_ids]
        removed = [image for image in existing if image["image_id"] in remove_ids]
        if len(kept) + len(new_files) > MAX_POST_IMAGES:
            flash(f"一篇貼文最多 {MAX_POST_IMAGES} 張照片。", "error")
            return redirect(target)
        if not caption and not kept and not new_files:
            flash("請至少保留一張照片，或寫點什麼。", "error")
            return redirect(target)
        new_paths = [save_uploaded_image(file, "attraction_posts") for file in new_files]
        if any(is_image_explicit(os.path.join(current_app.static_folder, path)) for path in new_paths):
            for path in new_paths:
                delete_uploaded_image(path)
            new_paths = []
            flash("新照片疑似含有不適當內容，本次編輯未儲存。", "error")
            return redirect(target)
        cursor.execute("UPDATE attraction_posts SET caption=%s,review_status='pending',reviewed_by=NULL,reviewed_at=NULL,review_note=NULL WHERE post_id=%s", (caption or None, post_id))
        if removed:
            placeholders = ",".join(["%s"] * len(removed))
            cursor.execute(f"DELETE FROM attraction_post_images WHERE image_id IN ({placeholders})", tuple(image["image_id"] for image in removed))
        next_order = max((image["sort_order"] for image in kept), default=-1) + 1
        cursor.executemany(
            "INSERT INTO attraction_post_images (post_id,image_path,sort_order) VALUES (%s,%s,%s)",
            [(post_id, path, next_order + offset) for offset, path in enumerate(new_paths)],
        )
        connection.commit()
        for image in removed:
            delete_uploaded_image(image["image_path"])
        flash("貼文已更新並重新送審。", "success")
    except ValueError as error:
        for path in new_paths:
            delete_uploaded_image(path)
        connection.rollback()
        flash(str(error), "error")
    except Exception as error:
        for path in new_paths:
            delete_uploaded_image(path)
        connection.rollback()
        print("更新景點相簿貼文失敗：", error)
        flash("更新失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(target)


@member_bp.route("/attractions/<int:attraction_id>/posts/<int:post_id>/delete", methods=["POST"])
@login_required("member")
def delete_attraction_post(attraction_id, post_id):
    target = url_for("member.attraction_detail", attraction_id=attraction_id) + "#album"
    connection = _connection_or_home()
    if connection is None:
        return redirect(target)
    cursor = connection.cursor(dictionary=True)
    image_paths = []
    try:
        cursor.execute("SELECT user_id FROM attraction_posts WHERE post_id=%s AND attraction_id=%s FOR UPDATE", (post_id, attraction_id))
        post = cursor.fetchone()
        if not post or post["user_id"] != session["user_id"]:
            flash("找不到這則貼文，或你沒有刪除權限。", "error")
            return redirect(target)
        cursor.execute("SELECT image_path FROM attraction_post_images WHERE post_id=%s", (post_id,))
        image_paths = [row["image_path"] for row in cursor.fetchall()]
        cursor.execute("DELETE FROM attraction_posts WHERE post_id=%s", (post_id,))
        connection.commit()
        for path in image_paths:
            delete_uploaded_image(path)
        flash("已刪除這則貼文。", "success")
    except Exception as error:
        connection.rollback()
        print("刪除景點相簿貼文失敗：", error)
        flash("刪除失敗，請再試一次。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(target)


@member_bp.route("/attractions/<int:attraction_id>/add-to-trip", methods=["POST"])
@login_required("member")
def add_attraction_to_trip(attraction_id):
    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.browse_attractions")

    trip_id = request.form.get("trip_id", "").strip()
    day = request.form.get("itinerary_date", "").strip()
    start, end, is_all_day, transport_minutes, time_errors = _parse_itinerary_time(request.form)
    if not trip_id.isdigit() or not day:
        flash("請選擇要加入的行程與日期。", "error"); return redirect(next_url)
    if time_errors:
        for error in time_errors: flash(error, "error")
        return redirect(next_url)
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
        cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,address,transport_method,transport_minutes,estimated_cost,notes,attraction_id,sort_order)
                          VALUES (%s,%s,%s,'attraction',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                       (trip["trip_id"], session["user_id"], day_value, attraction["name"][:150], start, end, is_all_day, attraction["address"],
                        request.form.get("transport_method", "").strip() or None, transport_minutes,
                        attraction["ticket_price"] or 0, request.form.get("notes", "").strip() or None, attraction_id, order))
        added_itinerary_id = cursor.lastrowid
        connection.commit()
        flash(f"已將「{attraction['name']}」加入「{trip['trip_name']}」的 {day_value} 行程。", "success")
        if re.fullmatch(r"/member/attractions/\d+", next_url.split("?", 1)[0].split("#", 1)[0]):
            next_url = f"{next_url.split('?', 1)[0].split('#', 1)[0]}?added_to={added_itinerary_id}#nearby"
    except Exception:
        current_app.logger.exception("加入景點到行程失敗 user_id=%s", session.get("user_id"))
        connection.rollback(); flash("加入行程失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(next_url)


def _parse_iso_date(value):
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


@member_bp.route("/api/flight-trips")
def api_flight_trips():
    # 機票頁「我已訂票，加入旅程」用：列出這位會員能編輯的旅程，並標示每段航班日期是否落在旅程期間內
    user_id = session.get("user_id") if session.get("role") == "member" else None
    if not user_id:
        return jsonify(error="login_required"), 401
    flight_dates = [d for d in (_parse_iso_date(x) for x in request.args.get("dates", "").split(",")) if d]
    connection = get_db_connection()
    if connection is None:
        return jsonify(error="db_unavailable"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.start_date, t.end_date
            FROM trips t JOIN trip_members tm ON tm.trip_id = t.trip_id
            WHERE tm.user_id = %s AND tm.join_status = 'accepted' AND tm.member_role IN ('owner', 'editor')
              AND t.deleted_at IS NULL
            ORDER BY t.start_date DESC
        """, (user_id,))
        trips = [{
            "trip_id": row["trip_id"], "trip_name": row["trip_name"],
            "start_date": row["start_date"].isoformat(), "end_date": row["end_date"].isoformat(),
            "fits": all(row["start_date"] <= d <= row["end_date"] for d in flight_dates),
        } for row in cursor.fetchall()]
    finally:
        cursor.close(); connection.close()
    return jsonify(trips=trips)


@member_bp.route("/api/flights/add-to-trip", methods=["POST"])
def api_add_flights_to_trip():
    user_id = session.get("user_id") if session.get("role") == "member" else None
    if not user_id:
        return jsonify(error="login_required"), 401
    payload = request.get_json(silent=True) or {}
    flights = payload.get("flights")
    trip_id = payload.get("trip_id")
    if not isinstance(trip_id, int) or not isinstance(flights, list) or not 1 <= len(flights) <= 4:
        return jsonify(error="資料格式不正確，請重新操作。"), 400

    items = []
    for flight in flights:
        if not isinstance(flight, dict):
            return jsonify(error="資料格式不正確，請重新操作。"), 400
        day = _parse_iso_date(flight.get("date"))
        title = str(flight.get("title") or "").strip()[:150]
        if not day or not title:
            return jsonify(error="航班缺少日期或名稱，無法加入旅程。"), 400
        times = []
        for key in ("start_time", "end_time"):
            value = str(flight.get(key) or "").strip()
            if value and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
                return jsonify(error="航班時間格式不正確。"), 400
            times.append(value + ":00" if value else None)
        try:
            cost = Decimal(str(flight.get("cost") or 0))
        except InvalidOperation:
            return jsonify(error="航班價格格式不正確。"), 400
        if not Decimal(0) <= cost <= Decimal(10_000_000):
            return jsonify(error="航班價格格式不正確。"), 400
        items.append((day, title, times[0], times[1], cost, str(flight.get("notes") or "").strip()[:500] or None))

    connection = get_db_connection()
    if connection is None:
        return jsonify(error="目前無法連線資料庫，請稍後再試。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, user_id)
        if not trip or not _can_edit(trip):
            return jsonify(error="你沒有編輯這個行程的權限。"), 403
        for day, *_ in items:
            if not trip["start_date"] <= day <= trip["end_date"]:
                return jsonify(error=f"航班日期 {day} 不在旅程期間（{trip['start_date']} ～ {trip['end_date']}）內。"), 400
        added = skipped = 0
        for day, title, start, end, cost, notes in items:
            cursor.execute("""SELECT itinerary_id FROM itineraries
                              WHERE trip_id=%s AND itinerary_date=%s AND item_type='transport' AND title=%s""",
                           (trip_id, day, title))
            if cursor.fetchone():
                skipped += 1
                continue
            if day == trip["start_date"]:  # 去程當天排在最前面，其他天排在最後面
                cursor.execute("UPDATE itineraries SET sort_order = sort_order + 1 WHERE trip_id=%s AND itinerary_date=%s",
                               (trip_id, day))
                order = 1
            else:
                cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s",
                               (trip_id, day))
                order = cursor.fetchone()["next_order"]
            cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,
                                                       transport_method,transport_minutes,estimated_cost,notes,sort_order)
                              VALUES (%s,%s,%s,'transport',%s,%s,%s,0,'飛機',0,%s,%s,%s)""",
                           (trip_id, user_id, day, title, start, end, cost, notes, order))
            added += 1
        connection.commit()
    except Exception:
        current_app.logger.exception("機票加入旅程失敗 user_id=%s", user_id)
        connection.rollback()
        return jsonify(error="加入旅程失敗，請再試一次。"), 500
    finally:
        cursor.close(); connection.close()
    return jsonify(added=added, skipped=skipped, trip_id=trip_id, trip_name=trip["trip_name"],
                   trip_url=url_for("member.trip_detail", trip_id=trip_id))


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


@member_bp.route("/restaurants")  # 訪客不用登入也能瀏覽；收藏、加入行程等個人化動作各自的路由還是要求登入
def browse_restaurants():
    user_id = session.get("user_id")
    keyword = request.args.get("keyword", "").strip()
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    favorites_only = request.args.get("favorites_only") == "1" and bool(user_id)

    connection = _connection_or_home()
    if connection is None:
        return render_template("member/restaurants.html", restaurants=[], countries=[], cities=[],
                                keyword=keyword, country_id=country_id, city_id=city_id,
                                favorites_only=favorites_only, ranking_preview=[], addable_trips=[],
                                taiwan_counties=TAIWAN_COUNTIES)
    cursor = connection.cursor(dictionary=True)
    try:
        conditions = ["r.status = 'active'", "r.deleted_at IS NULL"]
        params = [user_id]

        if keyword:
            conditions.append("(r.name LIKE %s OR r.address LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if country_id:
            conditions.append("r.country_id = %s")
            params.append(country_id)
        if city_id:
            conditions.append("r.city_id = %s")
            params.append(city_id)
        if favorites_only:
            conditions.append("f.favorite_id IS NOT NULL")

        where_clause = " AND ".join(conditions)
        cursor.execute(f"""
            SELECT r.restaurant_id, r.city_id, r.name, r.address, r.latitude, r.longitude,
                   r.cuisine_type, r.price_level, r.image_path,
                   cat.category_name, co.name AS country, ci.name AS city,
                   (f.favorite_id IS NOT NULL) AS is_favorited
            FROM restaurants r
            LEFT JOIN categories cat ON cat.category_id = r.category_id
            JOIN countries co ON co.country_id = r.country_id
            JOIN cities ci ON ci.city_id = r.city_id
            LEFT JOIN favorites f ON f.restaurant_id = r.restaurant_id AND f.user_id = %s
            WHERE {where_clause}
            ORDER BY r.restaurant_id DESC
        """, params)
        restaurants = cursor.fetchall()
        ranking_preview = fetch_restaurant_rankings(
            cursor, country_id=country_id, city_id=city_id, keyword=keyword,
            limit=3,
        )
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        addable_trips = _addable_trips(cursor, user_id) if user_id else []
    finally:
        cursor.close(); connection.close()

    return render_template("member/restaurants.html", restaurants=restaurants, countries=countries, cities=cities,
                            keyword=keyword, country_id=country_id, city_id=city_id, favorites_only=favorites_only,
                            ranking_preview=ranking_preview, addable_trips=addable_trips,
                            taiwan_counties=TAIWAN_COUNTIES)


@member_bp.route("/restaurants/rankings/data")  # 排行榜彈窗用的 AJAX，純公開統計資料，訪客不用登入也能看
def restaurant_rankings_data():
    """Return the top-5 ranking data for the Explore page's in-place dialog."""
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    country_id = country_id if country_id.isdecimal() and int(country_id) > 0 else ""
    city_id = city_id if city_id.isdecimal() and int(city_id) > 0 else ""
    metric = request.args.get("metric", "itineraries").strip()
    county = request.args.get("county", "").strip().replace("臺", "台")
    if metric not in ("itineraries", "favorites") or (county and county not in TAIWAN_COUNTIES):
        return jsonify({"error": "無效的排行榜篩選"}), 400

    connection = get_db_connection()
    if connection is None:
        return jsonify({"error": "排行榜暫時無法載入，請稍後再試。"}), 503
    cursor = connection.cursor(dictionary=True)
    try:
        rankings = fetch_restaurant_rankings(
            cursor, country_id=None if county else country_id or None,
            county_name=county or None,
            favorites_only=metric == "favorites",
            positive_only=metric == "itineraries", sort_by=metric, limit=5)
    finally:
        cursor.close(); connection.close()
    return jsonify({"rankings": [{
        "rank": index, "name": row["name"], "country": row["country"],
        "city": row["city"], "itinerary_count": row["itinerary_count"],
        "favorite_count": row["favorite_count"],
        "detail_url": url_for("member.restaurant_detail", restaurant_id=row["restaurant_id"]),
    } for index, row in enumerate(rankings, start=1)]})


@member_bp.route("/restaurants/<int:restaurant_id>")  # 訪客不用登入也能瀏覽；收藏、加入行程等個人化動作各自的路由還是要求登入
def restaurant_detail(restaurant_id):
    user_id = session.get("user_id")
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.browse_restaurants"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT r.*, cat.category_name, co.name AS country, ci.name AS city,
                   (f.favorite_id IS NOT NULL) AS is_favorited
            FROM restaurants r
            LEFT JOIN categories cat ON cat.category_id = r.category_id
            JOIN countries co ON co.country_id = r.country_id
            JOIN cities ci ON ci.city_id = r.city_id
            LEFT JOIN favorites f ON f.restaurant_id = r.restaurant_id AND f.user_id = %s
            WHERE r.restaurant_id = %s AND r.status = 'active' AND r.deleted_at IS NULL
        """, (user_id, restaurant_id))
        restaurant = cursor.fetchone()
        addable_trips = _addable_trips(cursor, user_id) if restaurant and user_id else []
    finally:
        cursor.close(); connection.close()

    if not restaurant:
        flash("找不到這間餐廳，或已被下架。", "error")
        return redirect(url_for("member.browse_restaurants"))

    return render_template("member/restaurant_detail.html", r=restaurant, addable_trips=addable_trips)


@member_bp.route("/restaurants/<int:restaurant_id>/add-to-trip", methods=["POST"])
@login_required("member")
def add_restaurant_to_trip(restaurant_id):
    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.browse_restaurants")

    trip_id = request.form.get("trip_id", "").strip()
    day = request.form.get("itinerary_date", "").strip()
    start, end, is_all_day, transport_minutes, time_errors = _parse_itinerary_time(request.form)
    if not trip_id.isdigit() or not day:
        flash("請選擇要加入的行程與日期。", "error"); return redirect(next_url)
    if time_errors:
        for error in time_errors: flash(error, "error")
        return redirect(next_url)
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
        cursor.execute("""SELECT name, address FROM restaurants
                          WHERE restaurant_id=%s AND status='active' AND deleted_at IS NULL""", (restaurant_id,))
        restaurant = cursor.fetchone()
        if not restaurant:
            flash("找不到這間餐廳，或已被下架。", "error"); return redirect(next_url)
        cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s", (trip["trip_id"], day_value))
        order = cursor.fetchone()["next_order"]
        cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,address,transport_method,transport_minutes,estimated_cost,notes,restaurant_id,sort_order)
                          VALUES (%s,%s,%s,'restaurant',%s,%s,%s,%s,%s,%s,%s,0,%s,%s,%s)""",
                       (trip["trip_id"], session["user_id"], day_value, restaurant["name"][:150], start, end, is_all_day, restaurant["address"],
                        request.form.get("transport_method", "").strip() or None, transport_minutes,
                        request.form.get("notes", "").strip() or None, restaurant_id, order))
        connection.commit()
        flash(f"已將「{restaurant['name']}」加入「{trip['trip_name']}」的 {day_value} 行程。", "success")
    except Exception:
        current_app.logger.exception("加入餐廳到行程失敗 user_id=%s", session.get("user_id"))
        connection.rollback(); flash("加入行程失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(next_url)


@member_bp.route("/restaurants/<int:restaurant_id>/favorite", methods=["POST"])
@login_required("member")
def toggle_restaurant_favorite(restaurant_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.browse_restaurants"))
    cursor = connection.cursor()
    try:
        user_id = session["user_id"]
        cursor.execute("SELECT favorite_id FROM favorites WHERE user_id=%s AND restaurant_id=%s", (user_id, restaurant_id))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("DELETE FROM favorites WHERE favorite_id=%s", (existing[0],))
            connection.commit()
            flash("已取消收藏。", "success")
        else:
            cursor.execute("INSERT INTO favorites (user_id, target_type, restaurant_id) VALUES (%s,'restaurant',%s)", (user_id, restaurant_id))
            connection.commit()
            flash("已加入收藏。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()

    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.browse_restaurants")
    return redirect(next_url)


@member_bp.route("/accommodations")  # 訪客不用登入也能瀏覽；收藏、加入行程等個人化動作各自的路由還是要求登入
def browse_accommodations():
    user_id = session.get("user_id")
    keyword = request.args.get("keyword", "").strip()
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    favorites_only = request.args.get("favorites_only") == "1" and bool(user_id)

    connection = _connection_or_home()
    if connection is None:
        return render_template("member/accommodations.html", accommodations=[], countries=[], cities=[],
                                keyword=keyword, country_id=country_id, city_id=city_id,
                                favorites_only=favorites_only, ranking_preview=[], addable_trips=[],
                                taiwan_counties=TAIWAN_COUNTIES)
    cursor = connection.cursor(dictionary=True)
    try:
        conditions = ["ac.status = 'active'", "ac.deleted_at IS NULL"]
        params = [user_id]

        if keyword:
            conditions.append("(ac.name LIKE %s OR ac.address LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if country_id:
            conditions.append("ac.country_id = %s")
            params.append(country_id)
        if city_id:
            conditions.append("ac.city_id = %s")
            params.append(city_id)
        if favorites_only:
            conditions.append("f.favorite_id IS NOT NULL")

        where_clause = " AND ".join(conditions)
        cursor.execute(f"""
            SELECT ac.accommodation_id, ac.city_id, ac.name, ac.address, ac.latitude, ac.longitude,
                   ac.accommodation_type, ac.price_per_night, ac.image_path,
                   cat.category_name, co.name AS country, ci.name AS city,
                   (f.favorite_id IS NOT NULL) AS is_favorited
            FROM accommodations ac
            LEFT JOIN categories cat ON cat.category_id = ac.category_id
            JOIN countries co ON co.country_id = ac.country_id
            JOIN cities ci ON ci.city_id = ac.city_id
            LEFT JOIN favorites f ON f.accommodation_id = ac.accommodation_id AND f.user_id = %s
            WHERE {where_clause}
            ORDER BY ac.accommodation_id DESC
        """, params)
        accommodations = cursor.fetchall()
        ranking_preview = fetch_accommodation_rankings(
            cursor, country_id=country_id, city_id=city_id, keyword=keyword,
            limit=3,
        )
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        addable_trips = _addable_trips(cursor, user_id) if user_id else []
    finally:
        cursor.close(); connection.close()

    return render_template("member/accommodations.html", accommodations=accommodations, countries=countries, cities=cities,
                            keyword=keyword, country_id=country_id, city_id=city_id, favorites_only=favorites_only,
                            ranking_preview=ranking_preview, addable_trips=addable_trips,
                            taiwan_counties=TAIWAN_COUNTIES)


@member_bp.route("/accommodations/rankings/data")  # 排行榜彈窗用的 AJAX，純公開統計資料，訪客不用登入也能看
def accommodation_rankings_data():
    """Return the top-5 ranking data for the Explore page's in-place dialog."""
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    country_id = country_id if country_id.isdecimal() and int(country_id) > 0 else ""
    city_id = city_id if city_id.isdecimal() and int(city_id) > 0 else ""
    metric = request.args.get("metric", "itineraries").strip()
    county = request.args.get("county", "").strip().replace("臺", "台")
    if metric not in ("itineraries", "favorites") or (county and county not in TAIWAN_COUNTIES):
        return jsonify({"error": "無效的排行榜篩選"}), 400

    connection = get_db_connection()
    if connection is None:
        return jsonify({"error": "排行榜暫時無法載入，請稍後再試。"}), 503
    cursor = connection.cursor(dictionary=True)
    try:
        rankings = fetch_accommodation_rankings(
            cursor, country_id=None if county else country_id or None,
            county_name=county or None,
            favorites_only=metric == "favorites",
            positive_only=metric == "itineraries", sort_by=metric, limit=5)
    finally:
        cursor.close(); connection.close()
    return jsonify({"rankings": [{
        "rank": index, "name": row["name"], "country": row["country"],
        "city": row["city"], "itinerary_count": row["itinerary_count"],
        "favorite_count": row["favorite_count"],
        "detail_url": url_for("member.accommodation_detail", accommodation_id=row["accommodation_id"]),
    } for index, row in enumerate(rankings, start=1)]})


@member_bp.route("/accommodations/<int:accommodation_id>")  # 訪客不用登入也能瀏覽；收藏、加入行程等個人化動作各自的路由還是要求登入
def accommodation_detail(accommodation_id):
    user_id = session.get("user_id")
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.browse_accommodations"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT ac.*, cat.category_name, co.name AS country, ci.name AS city,
                   (f.favorite_id IS NOT NULL) AS is_favorited
            FROM accommodations ac
            LEFT JOIN categories cat ON cat.category_id = ac.category_id
            JOIN countries co ON co.country_id = ac.country_id
            JOIN cities ci ON ci.city_id = ac.city_id
            LEFT JOIN favorites f ON f.accommodation_id = ac.accommodation_id AND f.user_id = %s
            WHERE ac.accommodation_id = %s AND ac.status = 'active' AND ac.deleted_at IS NULL
        """, (user_id, accommodation_id))
        accommodation = cursor.fetchone()
        addable_trips = _addable_trips(cursor, user_id) if accommodation and user_id else []
    finally:
        cursor.close(); connection.close()

    if not accommodation:
        flash("找不到這間住宿，或已被下架。", "error")
        return redirect(url_for("member.browse_accommodations"))

    return render_template("member/accommodation_detail.html", ac=accommodation, addable_trips=addable_trips)


@member_bp.route("/accommodations/<int:accommodation_id>/add-to-trip", methods=["POST"])
@login_required("member")
def add_accommodation_to_trip(accommodation_id):
    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.browse_accommodations")

    trip_id = request.form.get("trip_id", "").strip()
    day = request.form.get("itinerary_date", "").strip()
    start, end, is_all_day, transport_minutes, time_errors = _parse_itinerary_time(request.form)
    if not trip_id.isdigit() or not day:
        flash("請選擇要加入的行程與日期。", "error"); return redirect(next_url)
    if time_errors:
        for error in time_errors: flash(error, "error")
        return redirect(next_url)
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
        cursor.execute("""SELECT name, address, price_per_night FROM accommodations
                          WHERE accommodation_id=%s AND status='active' AND deleted_at IS NULL""", (accommodation_id,))
        accommodation = cursor.fetchone()
        if not accommodation:
            flash("找不到這間住宿，或已被下架。", "error"); return redirect(next_url)
        cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s", (trip["trip_id"], day_value))
        order = cursor.fetchone()["next_order"]
        cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,address,transport_method,transport_minutes,estimated_cost,notes,accommodation_id,sort_order)
                          VALUES (%s,%s,%s,'accommodation',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                       (trip["trip_id"], session["user_id"], day_value, accommodation["name"][:150], start, end, is_all_day, accommodation["address"],
                        request.form.get("transport_method", "").strip() or None, transport_minutes,
                        accommodation["price_per_night"] or 0, request.form.get("notes", "").strip() or None, accommodation_id, order))
        connection.commit()
        flash(f"已將「{accommodation['name']}」加入「{trip['trip_name']}」的 {day_value} 行程。", "success")
    except Exception:
        current_app.logger.exception("加入住宿到行程失敗 user_id=%s", session.get("user_id"))
        connection.rollback(); flash("加入行程失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(next_url)


@member_bp.route("/accommodations/<int:accommodation_id>/favorite", methods=["POST"])
@login_required("member")
def toggle_accommodation_favorite(accommodation_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.browse_accommodations"))
    cursor = connection.cursor()
    try:
        user_id = session["user_id"]
        cursor.execute("SELECT favorite_id FROM favorites WHERE user_id=%s AND accommodation_id=%s", (user_id, accommodation_id))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("DELETE FROM favorites WHERE favorite_id=%s", (existing[0],))
            connection.commit()
            flash("已取消收藏。", "success")
        else:
            cursor.execute("INSERT INTO favorites (user_id, target_type, accommodation_id) VALUES (%s,'accommodation',%s)", (user_id, accommodation_id))
            connection.commit()
            flash("已加入收藏。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()

    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.browse_accommodations")
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
                return render_template("member/trip_form.html", trip=form, mode="create", countries=countries, cities=cities, popular_cities=_popular_cities(cursor))
            try:
                cursor.execute("""INSERT INTO trips (owner_id,trip_name,cover_image_path,country_id,city_id,start_date,end_date,people_count,total_budget,currency,introduction,visibility,allow_copy,status,share_token)
                                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'planning',%s)""",
                               (session["user_id"], form["trip_name"], cover_image_path, form["country_id"], form["city_id"], form["start_date"], form["end_date"], form["people_count"], form["total_budget"], form["currency"], form["introduction"] or None, form["visibility"], form["allow_copy"], secrets.token_urlsafe(16)))
                trip_id = cursor.lastrowid
                cursor.execute("INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())", (trip_id, session["user_id"]))
                connection.commit()
                flash("已建立新行程，現在可以邀請旅伴並安排每日活動。", "success")
                return redirect(url_for("member.trip_detail", trip_id=trip_id))
            except Exception:
                current_app.logger.exception("建立行程失敗 user_id=%s", session.get("user_id"))
                connection.rollback(); flash("建立行程失敗，請再試一次。", "error")
        # 首頁「快速建立行程」帶過來的目的地、日期、人數，先填進表單
        prefill = {}
        city_raw = request.args.get("city_id", "")
        if city_raw.isdigit():
            city = next((c for c in cities if str(c["city_id"]) == city_raw), None)
            if city:
                prefill.update(city_id=city["city_id"], country_id=city["country_id"])
        for key in ("start_date", "end_date"):
            try:
                prefill[key] = date.fromisoformat(request.args.get(key, "")).isoformat()
            except ValueError:
                pass
        people_raw = request.args.get("people_count", "")
        if people_raw.isdigit() and 1 <= int(people_raw) <= 99:
            prefill["people_count"] = int(people_raw)
        return render_template("member/trip_form.html", trip=prefill or None, mode="create", countries=countries,
                               cities=cities, popular_cities=_popular_cities(cursor))
    finally:
        cursor.close(); connection.close()



@member_bp.route("/trips/ai-create", methods=["POST"])
@login_required("member")
def ai_create_trip():
    """首頁「讓 AI 幫你排行程」：從一句需求推測目的地與日期，請 AI 排好每日行程，直接建立成「我的旅程」。"""
    from group_ai_planner import generate_plan  # 延後載入，避免啟動時的循環匯入

    text = request.form.get("q", "").strip()[:1000]
    back = redirect(url_for("member.dashboard", q=text or None))
    if not text:
        flash("請先寫下你的旅行需求，例如「12 月想去東京 5 天」。", "error")
        return back
    if not ai_ready():
        flash("伺服器尚未設定 AI 服務金鑰，暫時無法自動排行程，請改用「自己快速建立」。", "error")
        return back
    connection = get_db_connection()
    if connection is None:
        flash("目前無法連線資料庫，請稍後再試。", "error")
        return back
    cursor = connection.cursor(dictionary=True)
    try:
        countries, cities = get_countries(cursor), get_cities(cursor)
        cursor.execute("SELECT city_id FROM attractions WHERE city_id IS NOT NULL GROUP BY city_id ORDER BY COUNT(*) DESC LIMIT 60")
        popular_city_ids = [row["city_id"] for row in cursor.fetchall()]
        guess = trip_request.complete(text, countries, cities, popular_city_ids)
        if not guess.get("city_id"):
            raise ValueError("看不出你想去哪裡，請在需求裡寫上城市或國家，例如「東京」「韓國首爾」。")
        city = next(c for c in cities if c["city_id"] == guess["city_id"])
        start_date, end_date = guess["start_date"], guess["end_date"]
        days = (end_date - start_date).days + 1
        plan = generate_plan(text, guess["country_name"], city["name"], start_date, end_date,
                             guess["people_count"], guess["budget"])
        trip_name = f"{city['name']} {days} 天行程"
        cursor.execute("""
            INSERT INTO trips (owner_id,trip_name,country_id,city_id,start_date,end_date,
                               people_count,total_budget,currency,introduction,visibility,status,share_token)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'TWD',%s,'private','planning',%s)
        """, (session["user_id"], trip_name, guess["country_id"], guess["city_id"], start_date, end_date,
              guess["people_count"], guess["budget"], plan["summary"] or text, secrets.token_urlsafe(16)))
        trip_id = cursor.lastrowid
        cursor.execute("INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())",
                       (trip_id, session["user_id"]))
        for sort_order, item in enumerate(plan["items"], 1):
            cursor.execute("""
                INSERT INTO itineraries
                  (trip_id,created_by,itinerary_date,item_type,title,start_time,address,estimated_cost,notes,sort_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (trip_id, session["user_id"], item["date"], item["type"], item["title"],
                  item["start_time"], item["address"], item["estimated_cost"], item["notes"], sort_order))
        connection.commit()
        cap_note = (
            f"你的需求提到 {guess['requested_days']} 天，AI 一次最多只能排 {trip_request.MAX_DAYS} 天（天數太多估算容易失真），"
            f"已經先用 {days} 天幫你規劃，想排更長可以之後自己在「編輯行程」調整天數、再手動加項目。"
        ) if guess.get("requested_days") else ""
        flash(f"AI 已建立「{trip_name}」（{start_date:%m/%d}–{end_date:%m/%d}，{guess['people_count']} 人）。"
              f"日期、人數是從你的需求推測的，可按「編輯行程」修改；每日項目也請確認營業時間與價格。{cap_note}", "success")
        return redirect(url_for("member.trip_detail", trip_id=trip_id))
    except (ValueError, RuntimeError) as error:
        connection.rollback()
        flash(str(error), "error")
    except Exception as error:
        connection.rollback()
        print("AI 建立行程失敗：", error)
        flash("AI 排行程暫時失敗，請稍後再試，或改用「自己快速建立」。", "error")
    finally:
        cursor.close(); connection.close()
    return back


def _popular_cities(cursor, limit=10):
    """熱門目的地：依景點數與行程數排序的城市，給建立行程時一鍵點選。"""
    try:
        cursor.execute("""
            SELECT city_id, name, country_id, country FROM (
                SELECT ci.city_id, ci.name, ci.country_id, co.name AS country,
                       (SELECT COUNT(*) FROM attractions a WHERE a.city_id = ci.city_id AND a.status = 'active' AND a.deleted_at IS NULL) AS attraction_count,
                       (SELECT COUNT(*) FROM trips t WHERE t.city_id = ci.city_id AND t.deleted_at IS NULL) AS trip_count
                FROM cities ci JOIN countries co ON co.country_id = ci.country_id
            ) ranked
            WHERE attraction_count > 0 OR trip_count >= 2
            ORDER BY attraction_count + trip_count * 2 DESC, city_id
            LIMIT %s
        """, (limit,))
        return cursor.fetchall()
    except Exception as error:
        print("熱門目的地查詢失敗：", error)
        return []


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


# 新增行程項目的「名稱搜尋」：景點／餐廳／住宿只能從網站資料裡選(避免亂打名稱)，找不到再送交管理員審核
PLACE_SEARCH_TABLES = {
    "attraction": ("attractions", "attraction_id", "ticket_price"),
    "restaurant": ("restaurants", "restaurant_id", "0"),
    "accommodation": ("accommodations", "accommodation_id", "price_per_night"),
}


@member_bp.route("/trips/<int:trip_id>/place-search")
@login_required("member")
def search_trip_places(trip_id):
    """輸入名稱時跳出的選項：同城市的排前面，再來是同國家的；沒輸入時列出同城市的熱門選項。"""
    item_type = request.args.get("type", "")
    keyword = request.args.get("q", "").strip()[:50]
    if item_type not in PLACE_SEARCH_TABLES:
        return jsonify(places=[])
    connection = get_db_connection()
    if connection is None:
        return jsonify(places=[]), 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            return jsonify(places=[]), 403
        rows = search_site_places(cursor, item_type, keyword, trip["city_id"], trip["country_id"])
        places = [{
            "id": row["id"], "name": row["name"], "address": row["address"] or "", "city": row["city"] or "",
            "cost": float(row["cost"] or 0), "same_city": bool(row["same_city"]),
            "image": url_for("static", filename=row["image_path"]) if row["image_path"] else "",
        } for row in rows]
        return jsonify(places=places, city=trip["city"])
    finally:
        cursor.close(); connection.close()


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
        return_group_id = None
        source_group = request.args.get("from_group", "")
        if trip["member_role"] == "owner" and re.fullmatch(r"[1-9][0-9]{0,17}", source_group):
            cursor.execute(
                "SELECT group_id FROM friend_groups WHERE group_id=%s AND trip_id=%s AND host_user_id=%s",
                (int(source_group), trip_id, session["user_id"]),
            )
            if cursor.fetchone():
                return_group_id = int(source_group)
        cursor.execute("""SELECT i.*, u.nickname, u.full_name,
                                 a.attraction_id AS detail_attraction_id, a.image_path AS attraction_image,
                                 a.description AS attraction_description, a.opening_hours AS attraction_hours,
                                 a.suggested_duration_minutes AS attraction_duration,
                                 a.latitude AS attraction_lat, a.longitude AS attraction_lng
                          FROM itineraries i JOIN users u ON u.user_id=i.created_by
                          LEFT JOIN attractions a ON a.attraction_id=i.attraction_id
                              AND i.item_type='attraction' AND a.status='active' AND a.deleted_at IS NULL
                          WHERE i.trip_id=%s ORDER BY i.itinerary_date,i.sort_order""", (trip_id,)); itinerary = cursor.fetchall()

        # 依日期逐筆記錄「這一天前一筆有座標的景點」，提供給前端估算交通時間用
        day_last_coords = {}
        for it in itinerary:
            day_key = it["itinerary_date"].isoformat()
            prev = day_last_coords.get(day_key)
            it["prev_lat"] = prev[0] if prev else None
            it["prev_lng"] = prev[1] if prev else None
            if it.get("attraction_lat") is not None and it.get("attraction_lng") is not None:
                day_last_coords[day_key] = (float(it["attraction_lat"]), float(it["attraction_lng"]))
        city_weather_days = {}
        city_weather = weather.get_weather_by_cities([trip["city"]]) if trip.get("city") else {}
        if trip.get("city") in city_weather:
            city_weather_days = {day["date"]: day for day in city_weather[trip["city"]]["days"]}
        precheck_issues = None  # 出發前檢查(行程頁「每日行程」最上面)；旅程已經結束就不檢查
        if trip["end_date"] >= date.today():
            try:
                precheck_issues = pre_trip_check.run_checks(cursor, trip)
            except Exception as error:  # 檢查失敗不影響行程頁
                print("出發前檢查失敗：", error)
        compare_nights = []  # 比價「加進行程」時讓使用者勾選要住哪幾晚：每一晚的日期，以及那晚已經排的住宿
        for offset in range(max(0, (trip["end_date"] - trip["start_date"]).days)):
            night = trip["start_date"] + timedelta(days=offset)
            stays = [it["title"] for it in itinerary if it["item_type"] == "accommodation" and it["itinerary_date"] == night]
            compare_nights.append({"date": night.isoformat(), "label": f"{night.month}/{night.day}（{'一二三四五六日'[night.weekday()]}）",
                                   "booked": "、".join(stays)})
        compares, compare_remaining, compare_ready = [], 0, False  # 機票＋住宿比價(住宿與預算分頁)
        try:
            if booking_compare.table_available(cursor):
                compare_ready = True
                compares = booking_compare.latest(cursor, trip_id)
                compare_remaining = max(0, booking_compare.DAILY_LIMIT - booking_compare.used_today(cursor, session["user_id"]))
        except Exception as error:  # 比價資料讀取失敗不影響行程頁
            print("讀取比價結果失敗：", error)
        cursor.execute("""SELECT tm.*, u.full_name,u.nickname,u.username,u.avatar_path FROM trip_members tm JOIN users u ON u.user_id=tm.user_id
                          WHERE tm.trip_id=%s AND tm.join_status='accepted' ORDER BY FIELD(tm.member_role,'owner','editor','viewer'),u.full_name""", (trip_id,)); members = cursor.fetchall()
        cursor.execute("""SELECT ti.*, u.full_name AS invitee_name, u.nickname AS invitee_nickname, u.avatar_path
                          FROM trip_invitations ti JOIN users u ON u.user_id=ti.invitee_id
                          WHERE ti.trip_id=%s AND ti.status='pending' ORDER BY ti.created_at DESC""", (trip_id,)); pending_invitations = cursor.fetchall()
        cursor.execute("""SELECT tm.*, u.full_name,u.nickname,u.avatar_path FROM trip_members tm JOIN users u ON u.user_id=tm.user_id
                          WHERE tm.trip_id=%s AND tm.join_status='requested' ORDER BY tm.created_at""", (trip_id,)); pending_requests = cursor.fetchall()
        cursor.execute("""SELECT invitation_id, invite_token, assigned_role, expires_at FROM trip_invitations
                          WHERE trip_id=%s AND invitee_id IS NULL AND status='pending'
                            AND (expires_at IS NULL OR expires_at > NOW())
                          ORDER BY created_at DESC LIMIT 1""", (trip_id,)); invite_link = cursor.fetchone()
        cursor.execute("""SELECT p.*,u.full_name AS proposer_name FROM proposals p JOIN users u ON u.user_id=p.proposer_id
                          WHERE p.trip_id=%s AND p.is_catalog_submission=0
                          ORDER BY p.created_at DESC""", (trip_id,)); proposals = cursor.fetchall()
        for p in proposals:
            p["before"] = json.loads(p["before_data"]) if p["before_data"] else None
            p["after"] = json.loads(p["after_data"]) if p["after_data"] else None
        votes = _load_votes(cursor, trip_id, session["user_id"])
        proposal_comments = _load_proposal_comments(cursor, trip_id)
        cursor.execute("SELECT target_id FROM reports WHERE reporter_id=%s AND target_type='comment' AND status IN ('pending','processing')", (session["user_id"],))
        reported_comment_ids = {row["target_id"] for row in cursor.fetchall()}
        expenses = _load_expenses(cursor, trip_id)
        balance_summary = _load_balance_summary(cursor, trip_id)
        attachments = _load_attachments(cursor, trip_id)
        place_options = _load_place_options(cursor, trip["city_id"])
        cursor.execute("""
            SELECT a.attraction_id, a.name, a.address, a.ticket_price, a.image_path, a.city_id,
                   cat.category_name, ci.name AS city, a.description,
                   a.opening_hours, a.suggested_duration_minutes, a.latitude, a.longitude
            FROM attractions a
            LEFT JOIN categories cat ON cat.category_id = a.category_id
            JOIN cities ci ON ci.city_id = a.city_id
            WHERE a.country_id = %s AND a.status = 'active' AND a.deleted_at IS NULL
            ORDER BY (a.city_id = %s) DESC, a.is_popular DESC, a.attraction_id DESC
            LIMIT 20
        """, (trip["country_id"], trip["city_id"])); popular_attractions = cursor.fetchall()
        cursor.execute("SELECT COALESCE(SUM(amount),0) AS actual FROM expenses WHERE trip_id=%s AND expense_type='actual'", (trip_id,)); actual = cursor.fetchone()["actual"]
        transport_summary = _summarize_transport_time(itinerary)
        stay_tier = request.args.get("tier") if request.args.get("tier") in smart_trip.LODGING_TIERS else "mid"
        try:
            stay_plan, budget_estimate = _build_stay_plan(cursor, trip, _load_planning_items(cursor, trip_id), stay_tier)
        except Exception as error:  # 住宿與預算建議失敗不影響行程頁其他區塊
            print("住宿與預算建議失敗：", error)
            stay_plan, budget_estimate = [], None
        preference_rows = trip_preferences.load_trip_preferences(cursor, trip_id)
        my_preference, my_preference_source = trip_preferences.my_form_values(cursor, preference_rows, session["user_id"])
    finally:
        cursor.close(); connection.close()
    return render_template("member/trip_detail.html", trip=trip, itinerary=itinerary, place_options=place_options, popular_attractions=popular_attractions, addable_trips=[trip], day_last_coords=day_last_coords, city_weather_days=city_weather_days, members=members, mention_members=[{"name": m["nickname"] or m["full_name"], "full_name": m["full_name"], "is_me": m["user_id"] == session["user_id"]} for m in members], pending_invitations=pending_invitations, pending_requests=pending_requests, invite_link=invite_link, proposals=proposals, votes=votes, proposal_comments=proposal_comments, reported_comment_ids=reported_comment_ids, comment_report_reasons=COMMENT_REPORT_REASONS, expenses=expenses, balance_summary=balance_summary, attachments=attachments, actual=actual, can_edit=_can_edit(trip), is_owner=trip["member_role"] == "owner", now=datetime.now(), item_type_labels=ITEM_TYPE_LABELS, itinerary_change_field_labels=ITINERARY_CHANGE_FIELD_LABELS, disney_parks=theme_parks.get_disney_parks(), transport_summary=transport_summary, preferences_ready=preference_rows is not None, my_preference=my_preference, my_preference_source=my_preference_source, preference_summary=trip_preferences.summarize(preference_rows), preference_options=trip_preferences, return_group_id=return_group_id, stay_plan=stay_plan, budget_estimate=budget_estimate, stay_tier=stay_tier, lodging_tiers=smart_trip.LODGING_TIERS, ai_ready=ai_ready(), precheck_issues=precheck_issues, compares=compares, compare_remaining=compare_remaining, compare_ready=compare_ready, compare_limit=booking_compare.DAILY_LIMIT, compare_nights=compare_nights)


@member_bp.route("/trips/<int:trip_id>/export/excel")
@login_required("member")
def export_trip_excel(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            flash("你沒有查看這個行程的權限。", "error")
            return redirect(url_for("member.dashboard"))
        cursor.execute("SELECT * FROM itineraries WHERE trip_id=%s ORDER BY itinerary_date, sort_order", (trip_id,))
        itinerary = cursor.fetchall()
        cursor.execute("""SELECT tm.member_role, u.full_name, u.nickname FROM trip_members tm JOIN users u ON u.user_id=tm.user_id
                          WHERE tm.trip_id=%s AND tm.join_status='accepted'
                          ORDER BY FIELD(tm.member_role,'owner','editor','viewer'), u.full_name""", (trip_id,))
        members = cursor.fetchall()
    finally:
        cursor.close(); connection.close()

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        current_app.logger.exception("Excel 匯出需要 openpyxl")
        flash("目前無法匯出 Excel，請通知管理員安裝 openpyxl。", "error")
        return redirect(url_for("member.trip_detail", trip_id=trip_id))

    header_font = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="EEF6F7")
    role_labels = {"owner": "建立者", "editor": "共同編輯者", "viewer": "查看者"}

    workbook = Workbook()
    overview = workbook.active
    overview.title = "行程總覽"
    overview_rows = [
        ("行程名稱", trip["trip_name"]),
        ("目的地", f"{trip['country']} / {trip['city']}"),
        ("旅遊期間", f"{trip['start_date']} ~ {trip['end_date']}"),
        ("人數", trip["people_count"]),
        ("團體預算", f"{trip['total_budget']} {trip['currency']}"),
        ("簡介", trip["introduction"] or ""),
    ]
    for label, value in overview_rows:
        overview.append([label, value])
        overview.cell(row=overview.max_row, column=1).font = header_font
    overview.append([])
    overview.append(["團員", "角色"])
    for cell in overview[overview.max_row]:
        cell.font = header_font
        cell.fill = header_fill
    for member in members:
        overview.append([member["nickname"] or member["full_name"], role_labels.get(member["member_role"], member["member_role"])])
    overview.column_dimensions["A"].width = 16
    overview.column_dimensions["B"].width = 42

    detail = workbook.create_sheet("每日行程")
    detail_headers = ["天數", "日期", "開始時間", "結束時間", "類型", "項目名稱", "地址", "交通方式", "交通時間(分)", "預估花費", "備註", "Google地圖"]
    detail.append(detail_headers)
    for cell in detail[1]:
        cell.font = header_font
        cell.fill = header_fill
    link_font = Font(color="0563C1", underline="single")  # Excel 預設的超連結藍色底線樣式

    day_numbers = {}  # 把日期對應到「第幾天」，例如行程第一天的日期對應 1
    for item in itinerary:
        day_key = item["itinerary_date"]
        if day_key not in day_numbers:
            day_numbers[day_key] = len(day_numbers) + 1
        label = ITEM_TYPE_LABELS.get(item["item_type"], {}).get("label", item["item_type"])
        detail.append([
            f"Day {day_numbers[day_key]}",
            day_key.isoformat(),
            format_hm(item["start_time"]),
            format_hm(item["end_time"]),
            label,
            item["title"],
            item["address"] or "",
            item["transport_method"] or "",
            item["transport_minutes"] or "",
            float(item["estimated_cost"]) if item["estimated_cost"] is not None else "",
            item["notes"] or "",
            "",
        ])
        map_url = google_maps_url(item["address"])  # 沒有地址就組不出連結，回傳 None
        if map_url:
            map_cell = detail.cell(row=detail.max_row, column=len(detail_headers))
            map_cell.value = "查看地圖"
            map_cell.hyperlink = map_url
            map_cell.font = link_font
    for column, width in zip("ABCDEFGHIJKL", [8, 12, 10, 10, 8, 24, 32, 10, 12, 10, 32, 12]):
        detail.column_dimensions[column].width = width

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", trip["trip_name"])  # 去掉檔名不能出現的符號，避免下載失敗
    return send_file(
        buffer, as_attachment=True, download_name=f"{safe_name}_行程表.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


FLIGHT_TITLE_RE = re.compile(r"^(.*?)\s*([A-Za-z]{2}\d{2,4})?｜\s*(.+?)\s*→\s*(.+)$")


def _parse_flight_title(title):
    """把「航空公司 班號｜起點 → 終點」的標題拆開；格式對不上就回傳 None，當成一般交通項目顯示。"""
    match = FLIGHT_TITLE_RE.match(title or "")
    if not match:
        return None
    airline, flight_number, origin, destination = match.groups()
    airline = (airline or "").strip()
    if not airline or not origin.strip() or not destination.strip():
        return None
    return {"airline": airline, "flight_number": flight_number or "", "origin": origin.strip(), "destination": destination.strip()}


def _load_handbook_data(cursor, trip_id):
    """旅遊手冊共用的資料整理：查出每日行程(依日期分組)、航班卡片跟同行旅伴，登入版跟公開分享版都靠這個組出一樣的內容。"""
    cursor.execute("SELECT * FROM itineraries WHERE trip_id=%s ORDER BY itinerary_date, sort_order", (trip_id,))
    items = cursor.fetchall()
    cursor.execute("""SELECT tm.member_role, u.full_name, u.nickname, u.avatar_path FROM trip_members tm JOIN users u ON u.user_id=tm.user_id
                      WHERE tm.trip_id=%s AND tm.join_status='accepted'
                      ORDER BY FIELD(tm.member_role,'owner','editor','viewer'), u.full_name""", (trip_id,))
    members = cursor.fetchall()

    days = []  # 把行程項目依日期分組，模板直接逐天印出來
    days_by_date = {}
    flights = []  # 用「加入航班」功能存進來的交通項目（transport_method='飛機'），整理成航班卡片用
    for item in items:
        day_key = item["itinerary_date"]
        if day_key not in days_by_date:
            days_by_date[day_key] = {"date": day_key, "day_number": len(days) + 1, "items": []}
            days.append(days_by_date[day_key])
        days_by_date[day_key]["items"].append(item)
        if item["item_type"] == "transport" and item.get("transport_method") == "飛機":
            item["flight_info"] = _parse_flight_title(item["title"])
            flights.append(item)
    return days, members, flights


def _handbook_countdown_target(trip, flights):
    """倒數計時的目標時間：有加入航班就用最早那班的出發日期+時間，不然用旅程的出發日期 00:00。"""
    if flights:
        first = flights[0]
        base = datetime.combine(first["itinerary_date"], dt_time())
        start_time = first.get("start_time")
        if isinstance(start_time, timedelta):
            base += start_time
        return base.isoformat()
    return datetime.combine(trip["start_date"], dt_time()).isoformat()


@member_bp.route("/trips/<int:trip_id>/handbook")
@login_required("member")
def trip_handbook(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            flash("你沒有查看這個行程的權限。", "error")
            return redirect(url_for("member.dashboard"))
        days, members, flights = _load_handbook_data(cursor, trip_id)
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/trip_handbook.html", trip=trip, days=days, members=members, flights=flights, is_public_view=False,
        countdown_target=_handbook_countdown_target(trip, flights),
        item_type_labels=ITEM_TYPE_LABELS, role_labels={"owner": "建立者", "editor": "共同編輯者", "viewer": "查看者"},
    )


@member_bp.route("/handbook/<token>")  # 分享給非會員（例如家人）看的旅遊手冊，憑無法猜到的分享連結瀏覽，不用登入、唯讀
def shared_trip_handbook(token):
    connection = get_db_connection()
    if connection is None:
        flash("目前無法連線資料庫，請稍後再試。", "error")
        return redirect(url_for("visitor"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT t.*, co.name AS country, ci.name AS city FROM trips t
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE t.share_token = %s AND t.deleted_at IS NULL
        """, (token,))
        trip = cursor.fetchone()
        if not trip:
            flash("找不到這個旅遊手冊，連結可能已經失效。", "error")
            return redirect(url_for("visitor"))
        days, members, flights = _load_handbook_data(cursor, trip["trip_id"])
    finally:
        cursor.close(); connection.close()

    return render_template(
        "member/trip_handbook.html", trip=trip, days=days, members=members, flights=flights, is_public_view=True,
        countdown_target=_handbook_countdown_target(trip, flights),
        item_type_labels=ITEM_TYPE_LABELS, role_labels={"owner": "建立者", "editor": "共同編輯者", "viewer": "查看者"},
    )


@member_bp.route("/trips/<int:trip_id>/preferences", methods=["POST"])
@login_required("member")
def save_trip_preferences(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            flash("你沒有填寫這個行程偏好的權限。", "error")
            return redirect(url_for("member.dashboard"))

        data, errors = trip_preferences.parse_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
        elif trip_preferences.load_trip_preferences(cursor, trip_id) is None:
            flash("旅伴偏好尚未完成資料庫更新，請先執行 migrate_1028_trip_preferences.sql。", "error")
        else:
            trip_preferences.save_preference(cursor, trip_id, session["user_id"], data)
            connection.commit()
            flash("已儲存你的旅遊偏好。", "success")
    except Exception as error:
        connection.rollback()
        print("儲存旅伴偏好失敗：", error)
        flash("儲存失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#preferences")


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
            cursor.execute("""UPDATE trips SET trip_name=%s,cover_image_path=%s,country_id=%s,city_id=%s,start_date=%s,end_date=%s,people_count=%s,total_budget=%s,currency=%s,introduction=%s,visibility=%s,allow_copy=%s WHERE trip_id=%s""", (form["trip_name"],cover_image_path,form["country_id"],form["city_id"],form["start_date"],form["end_date"],form["people_count"],form["total_budget"],form["currency"],form["introduction"] or None,form["visibility"],form["allow_copy"],trip_id))
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
            "SELECT trip_name FROM trips WHERE trip_id=%s AND owner_id=%s AND moderation_status='visible' AND deleted_at IS NULL",
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
    return redirect(url_for("member.my_trips") + "#trip-trash")


def _owned_deleted_trip(cursor, trip_id):
    cursor.execute(
        "SELECT trip_id, trip_name FROM trips WHERE trip_id=%s AND owner_id=%s AND moderation_status='visible' AND deleted_at IS NOT NULL",
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
            return redirect(url_for("member.my_trips") + "#trip-trash")
        cursor.execute("UPDATE trips SET deleted_at=NULL, deleted_by=NULL WHERE trip_id=%s", (trip_id,))
        connection.commit()
        flash(f"行程「{trip['trip_name']}」已復原。", "success")
    except Exception as error:
        connection.rollback()
        print("復原行程失敗：", error)
        flash("復原行程失敗，請稍後再試。", "error")
        return redirect(url_for("member.my_trips") + "#trip-trash")
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
    return redirect(url_for("member.my_trips") + "#trip-trash")


def _duplicate_trip_for(cursor, trip_id, user_id):
    """把一趟行程(自己的，或開放複製的公開行程)複製成 user_id 的新行程。回傳 (新行程 ID, 錯誤訊息)；呼叫端負責 commit。"""
    cursor.execute("SELECT * FROM trips WHERE trip_id=%s AND deleted_at IS NULL", (trip_id,))
    trip = cursor.fetchone()
    if not trip or trip["moderation_status"] != "visible":
        return None, "找不到這個行程。"
    if trip["owner_id"] != user_id and trip["visibility"] != "public":
        return None, "只能複製自己的行程，或是公開行程。"
    if trip["owner_id"] != user_id and not trip["allow_copy"]:
        return None, "行程建立者沒有開放這個行程被複製。"

    cursor.execute("""
        INSERT INTO trips (owner_id,trip_name,country_id,city_id,start_date,end_date,
                            people_count,total_budget,currency,introduction,visibility,status,share_token)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'private','planning',%s)
    """, (user_id, trip["trip_name"] + "（複製）", trip["country_id"], trip["city_id"],
          trip["start_date"], trip["end_date"], trip["people_count"], trip["total_budget"], trip["currency"],
          trip["introduction"], secrets.token_urlsafe(16)))
    new_trip_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())",
        (new_trip_id, user_id)
    )

    cursor.execute("SELECT * FROM itineraries WHERE trip_id=%s ORDER BY itinerary_date, sort_order", (trip_id,))
    for item in cursor.fetchall():
        cursor.execute("""
            INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,
                                      address,transport_method,transport_minutes,estimated_cost,notes,
                                      attraction_id,restaurant_id,accommodation_id,sort_order)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (new_trip_id, user_id, item["itinerary_date"], item["item_type"], item["title"],
              item["start_time"], item["end_time"], item["is_all_day"], item["address"], item["transport_method"],
              item["transport_minutes"], item["estimated_cost"], item["notes"],
              item["attraction_id"], item["restaurant_id"], item["accommodation_id"], item["sort_order"]))
    return new_trip_id, None


def _duplicate_and_redirect(trip_id, success_message):
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        new_trip_id, error = _duplicate_trip_for(cursor, trip_id, session["user_id"])
        if error:
            flash(error, "error")
            return redirect(url_for("member.dashboard"))
        connection.commit()
        flash(success_message, "success")
        return redirect(url_for("member.trip_detail", trip_id=new_trip_id))
    except Exception as error:
        connection.rollback()
        print("複製行程失敗：", error)
        flash("複製行程失敗，請再試一次。", "error")
        return redirect(url_for("member.dashboard"))
    finally:
        cursor.close()
        connection.close()


@member_bp.route("/trips/<int:trip_id>/duplicate", methods=["POST"])
@login_required("member")
def duplicate_trip(trip_id):
    return _duplicate_and_redirect(trip_id, "行程已複製，你可以開始編輯這份新的行程。")


@member_bp.route("/trips/<int:trip_id>/apply-after-login")
@login_required("member")
def apply_trip_after_login(trip_id):
    """訪客在首頁按「登入後一鍵套用」→ 登入後自動來這裡複製那趟行程。
    只有 session 裡記著同一趟行程時才會複製(是訪客自己按的)，別人傳來的連結不會幫你亂複製。"""
    if session.pop("pending_apply_trip_id", None) != trip_id:
        return redirect(url_for("member.dashboard"))
    return _duplicate_and_redirect(trip_id, "已經幫你套用這個行程！這是你自己的一份，可以開始微調路線和時間。")


@member_bp.route("/trips/<int:trip_id>/itinerary", methods=["POST"])
@login_required("member")
def add_itinerary(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    catalog_proposal_id = None  # 勾選「送交管理員審核收錄」時，commit 後請 AI 小幫手在背景先檢查
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            flash("你沒有編輯行程項目的權限。", "error"); return redirect(url_for("member.dashboard"))
        title = request.form.get("title", "").strip(); item_type=request.form.get("item_type", "other")
        day = request.form.get("itinerary_date", "")
        start, end, is_all_day, transport_minutes, time_errors = _parse_itinerary_time(request.form)
        wants_catalog = request.form.get("submit_for_catalog") == "on" and item_type in ("attraction", "restaurant", "accommodation")
        if not title or not day: flash("請填寫項目名稱與日期。", "error")
        elif time_errors:
            for error in time_errors: flash(error, "error")
        elif wants_catalog and not request.form.get("address", "").strip():
            flash("勾選「送交管理員審核收錄」時，請填寫地點，管理員才能確認這個地方。", "error")
        elif (item_type in PLACE_SEARCH_TABLES and not wants_catalog
              and request.form.get("custom_place") != "1"  # 使用者刻意選了「只加進我的行程」(不送審)
              and not find_site_place(cursor, item_type, title, trip["country_id"])):
            label = {"attraction": "景點", "restaurant": "餐廳", "accommodation": "住宿"}[item_type]
            flash(f"網站裡找不到「{title}」這個{label}。請從清單選一個；找不到的話，可以選「只加進我的行程」或「送交管理員審核收錄」。", "error")
        else:
            # 從清單選的網站資料：連結到那筆景點／餐廳／住宿，行程地圖、智慧排程、行程助理才拿得到座標
            site_place = None
            if item_type in PLACE_SEARCH_TABLES and not wants_catalog and request.form.get("custom_place") != "1":
                site_place = find_site_place(cursor, item_type, title, trip["country_id"])
            link_column = SITE_PLACE_COLUMNS[item_type][3] if site_place else "attraction_id"
            link_id = site_place["id"] if site_place else None
            cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s", (trip_id,day)); order=cursor.fetchone()["next_order"]
            address = request.form.get("address","").strip() or None
            cursor.execute(f"""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,address,transport_method,transport_minutes,estimated_cost,notes,{link_column},sort_order)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (trip_id,session["user_id"],day,item_type,title,start,end,is_all_day,address,request.form.get("transport_method","").strip() or None,transport_minutes,request.form.get("estimated_cost") or 0,request.form.get("notes","").strip() or None,link_id,order))

            # 使用者勾選「這個地點不在清單中，送交管理員審核收錄」：這筆送審資料跟上面的旅伴提案投票
            # 是分開的兩件事，用 is_catalog_submission 標記，不會出現在這趟行程的提案投票清單給旅伴看，
            # 只會進到管理員的審核佇列，核准後才會正式收錄進對應的資料表供所有人使用
            catalog_note = ""
            if wants_catalog:
                cursor.execute("""INSERT INTO proposals (trip_id,proposer_id,proposal_type,title,location,description,estimated_cost,content_review_status,is_catalog_submission)
                                  VALUES (%s,%s,%s,%s,%s,%s,%s,'pending',1)""",
                               (trip_id, session["user_id"], item_type, title, address,
                                request.form.get("notes","").strip() or None, request.form.get("estimated_cost") or 0))
                catalog_proposal_id = cursor.lastrowid
                catalog_note = "，已送交管理員審核，通過後會正式收錄進資料庫"

            connection.commit(); flash(f"已加入每日行程{catalog_note}。", "success")
    except Exception:
        connection.rollback(); flash("儲存行程項目失敗。", "error")
        catalog_proposal_id = None
    finally:
        cursor.close(); connection.close()
    if catalog_proposal_id:
        proposal_review.schedule_new_proposal(catalog_proposal_id)
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


@member_bp.route("/trips/<int:trip_id>/itinerary/reorder", methods=["POST"])
@login_required("member")
def reorder_itinerary(trip_id):
    """拖曳排序：同一天的行程項目重新排列後，把新的順序存進 sort_order。"""
    data = request.get_json(silent=True) or {}
    itinerary_date = data.get("itinerary_date")
    ordered_ids = data.get("ordered_ids")
    if not itinerary_date or not isinstance(ordered_ids, list) or not ordered_ids:
        return jsonify(error="缺少必要參數。"), 400

    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            return jsonify(error="你沒有編輯這個行程的權限。"), 403

        cursor.execute(
            "SELECT itinerary_id FROM itineraries WHERE trip_id=%s AND itinerary_date=%s",
            (trip_id, itinerary_date)
        )
        valid_ids = {row["itinerary_id"] for row in cursor.fetchall()}
        try:
            ordered_ids = [int(x) for x in ordered_ids]
        except (TypeError, ValueError):
            return jsonify(error="行程項目格式錯誤。"), 400
        if set(ordered_ids) != valid_ids:
            return jsonify(error="行程項目跟資料庫不一致，請重新整理頁面再試一次。"), 409

        for index, itinerary_id in enumerate(ordered_ids, start=1):
            cursor.execute(
                "UPDATE itineraries SET sort_order=%s WHERE itinerary_id=%s AND trip_id=%s",
                (index, itinerary_id, trip_id)
            )
        connection.commit()
    except Exception:
        connection.rollback(); return jsonify(error="排序更新失敗，請再試一次。"), 500
    finally:
        cursor.close(); connection.close()
    return jsonify(ok=True)

def _time_value(value):
    """MySQL 的 TIME 欄位會讀成 timedelta，轉成 time 方便計算。"""
    if value is None or isinstance(value, dt_time):
        return value
    seconds = int(value.total_seconds()) % 86400
    return dt_time(seconds // 3600, seconds % 3600 // 60)


def _load_planning_items(cursor, trip_id, itinerary_date=None):
    """讀取行程項目，附上景點／餐廳／住宿的座標、營業時間、建議停留時間與價格，給智慧排程與預算估算用。"""
    sql = """
        SELECT i.itinerary_id, i.itinerary_date, i.item_type, i.title, i.start_time, i.end_time, i.is_all_day,
               i.address, i.estimated_cost, i.accommodation_id, i.sort_order, i.transport_method, i.transport_minutes,
               COALESCE(a.latitude, r.latitude, ac.latitude) AS lat,
               COALESCE(a.longitude, r.longitude, ac.longitude) AS lng,
               COALESCE(a.opening_hours, r.opening_hours) AS opening_hours,
               a.suggested_duration_minutes AS duration, a.ticket_price, r.price_level,
               ac.price_per_night, ac.name AS accommodation_name
        FROM itineraries i
        LEFT JOIN attractions a ON a.attraction_id = i.attraction_id AND a.deleted_at IS NULL
        LEFT JOIN restaurants r ON r.restaurant_id = i.restaurant_id AND r.deleted_at IS NULL
        LEFT JOIN accommodations ac ON ac.accommodation_id = i.accommodation_id AND ac.deleted_at IS NULL
        WHERE i.trip_id = %s"""
    params = [trip_id]
    if itinerary_date is not None:
        sql += " AND i.itinerary_date = %s"
        params.append(itinerary_date)
    cursor.execute(sql + " ORDER BY i.itinerary_date, i.sort_order, i.itinerary_id", tuple(params))
    rows = cursor.fetchall()
    for row in rows:
        row["start_time"] = _time_value(row["start_time"])
        row["end_time"] = _time_value(row["end_time"])
    return rows


@member_bp.route("/trips/<int:trip_id>/estimate-costs", methods=["POST"])
@login_required("member")
def estimate_item_costs(trip_id):
    """「💰 AI 估算費用」：替還沒填費用（0 元）的行程項目估一個參考價，寫入預估費用並在備註註明估算依據。"""
    back = redirect(url_for("member.trip_detail", trip_id=trip_id) + "#itinerary")
    connection = get_db_connection()
    if connection is None:
        flash("目前無法連線資料庫。", "error"); return back
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            flash("你沒有編輯這個行程的權限。", "error"); return back
        cursor.execute("""
            SELECT i.itinerary_id, i.itinerary_date, i.item_type, i.title, i.address, i.notes,
                   a.ticket_price, r.price_level
            FROM itineraries i
            LEFT JOIN attractions a ON a.attraction_id = i.attraction_id
            LEFT JOIN restaurants r ON r.restaurant_id = i.restaurant_id
            WHERE i.trip_id=%s AND COALESCE(i.estimated_cost, 0) = 0
            ORDER BY i.itinerary_date, i.sort_order LIMIT 40
        """, (trip_id,))
        items = cursor.fetchall()
        if not items:
            flash("每個項目都已經有費用了。", "success"); return back
        people = trip.get("people_count") or 1
        currency = trip.get("currency") or "TWD"
        lines = [{"id": it["itinerary_id"], "date": str(it["itinerary_date"]), "type": it["item_type"], "title": it["title"],
                  "address": it["address"] or "", "ticket_price_TWD_per_person": it["ticket_price"],
                  "price_level": it["price_level"]} for it in items]
        prompt = (
            f"你是旅遊預算助手。目的地：{trip['country']} {trip['city']}，{people} 人同行。"
            f"請替下列每個行程項目估算「{people} 人合計」的參考花費，用當地幣別的數字（不要自己換算匯率），依當地一般行情"
            "（門票、一餐平均消費、住宿一晚房價、交通票價等）。真的免費（免門票寺廟、公園、散步）才給 0。"
            "若有 ticket_price_TWD_per_person 請以它為準（那時 currency 填 TWD）。"
            '只回傳 JSON：{"costs":[{"id":項目id,"cost":數字,"currency":"ISO 幣別代碼，例如 JPY",'
            '"basis":"20 字內的估算依據，例如 門票約 ¥2,000／人"}]}。'
            "項目：" + json.dumps(lines, ensure_ascii=False, default=str)
        )
        result = ask_json(prompt, timeout=60)
        by_id = {it["itinerary_id"]: it for it in items}
        updated = 0
        for entry in result.get("costs", []) if isinstance(result.get("costs"), list) else []:
            try:
                item_id, cost = int(entry.get("id")), float(entry.get("cost"))
            except (TypeError, ValueError):
                continue
            # AI 給當地幣別金額，由程式用匯率換成行程的幣別
            cost = currency_rates.convert(cost, str(entry.get("currency") or currency), currency)
            if cost is None:
                continue
            cost = round(cost)
            if item_id not in by_id or not 0 <= cost <= 10_000_000:
                continue
            basis = str(entry.get("basis") or "").strip()[:60]
            note = by_id[item_id]["notes"] or ""
            if basis:
                note = (note + "\n" if note else "") + f"💰 AI 估價：{basis}（參考價，請自行查證）"
            cursor.execute("UPDATE itineraries SET estimated_cost=%s, notes=%s WHERE itinerary_id=%s AND trip_id=%s",
                           (cost, note[:1000] or None, item_id, trip_id))
            updated += 1
        connection.commit()
        flash(f"已替 {updated} 個項目估算參考費用（{currency}，{people} 人合計），請依實際價格修改。" if updated
              else "AI 這次沒有給出可用的估價，請稍後再試。", "success" if updated else "error")
    except AIUnavailable as error:
        connection.rollback(); flash(f"AI 估價暫時失敗：{error}", "error")
    except Exception as error:
        connection.rollback(); print("AI 估價失敗：", error); flash("AI 估價暫時失敗，請稍後再試。", "error")
    finally:
        cursor.close(); connection.close()
    return back


@member_bp.route("/trips/<int:trip_id>/smart-schedule", methods=["POST"])
@login_required("member")
def smart_schedule_preview(trip_id):
    """智慧排程預覽：依距離（與 AI）重新排列某一天的行程，回傳建議順序、時間與交通，不會直接改資料。"""
    data = request.get_json(silent=True) or {}
    try:
        day = date.fromisoformat(str(data.get("itinerary_date", "")))
    except ValueError:
        return jsonify(error="日期格式錯誤。"), 400
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            return jsonify(error="你沒有編輯這個行程的權限。"), 403
        items = _load_planning_items(cursor, trip_id, day)
    finally:
        cursor.close(); connection.close()
    if len(items) < 2:
        return jsonify(error="這一天至少要有兩個行程項目才能排順序。"), 400
    city = f"{trip.get('country') or ''} {trip.get('city') or ''}".strip()
    result = smart_trip.smart_schedule_day(items, day, city, use_ai=data.get("use_ai", True) is not False)
    result["itinerary_date"] = day.isoformat()
    return jsonify(result)


@member_bp.route("/trips/<int:trip_id>/smart-schedule/apply", methods=["POST"])
@login_required("member")
def smart_schedule_apply(trip_id):
    """套用智慧排程：更新排序、建議開始時間（保留原本的停留長度）與交通方式／時間。"""
    data = request.get_json(silent=True) or {}
    try:
        day = date.fromisoformat(str(data.get("itinerary_date", "")))
    except ValueError:
        return jsonify(error="日期格式錯誤。"), 400
    rows = data.get("items")
    if not isinstance(rows, list) or not rows:
        return jsonify(error="缺少排程內容。"), 400
    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            return jsonify(error="排程格式錯誤。"), 400
        try:
            itinerary_id = int(row.get("itinerary_id"))
        except (TypeError, ValueError):
            return jsonify(error="排程格式錯誤。"), 400
        start = None
        match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", str(row.get("start_time") or ""))
        if match:
            start = dt_time(int(match.group(1)), int(match.group(2)))
        method = str(row.get("transport_method") or "").strip()[:100] or None
        try:
            minutes = int(row.get("transport_minutes")) if row.get("transport_minutes") not in (None, "") else None
        except (TypeError, ValueError):
            minutes = None
        if minutes is not None and not 0 <= minutes <= 1440:
            minutes = None
        parsed.append((itinerary_id, start, method, minutes))
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            return jsonify(error="你沒有編輯這個行程的權限。"), 403
        current = {item["itinerary_id"]: item for item in _load_planning_items(cursor, trip_id, day)}
        if sorted(current) != sorted(row[0] for row in parsed):
            return jsonify(error="行程項目已經變動，請重新整理頁面後再排一次。"), 409
        for index, (itinerary_id, start, method, minutes) in enumerate(parsed, start=1):
            item = current[itinerary_id]
            new_start, new_end = item["start_time"], item["end_time"]
            if start and not item["is_all_day"]:
                if item["start_time"] and item["end_time"]:
                    length = ((item["end_time"].hour * 60 + item["end_time"].minute)
                              - (item["start_time"].hour * 60 + item["start_time"].minute))
                    end_minutes = min(start.hour * 60 + start.minute + max(length, 0), 23 * 60 + 59)
                    new_end = dt_time(end_minutes // 60, end_minutes % 60)
                elif item["end_time"] and item["end_time"] <= start:
                    new_end = None
                new_start = start
            if index > 1 and method:
                cursor.execute("""UPDATE itineraries SET sort_order=%s, start_time=%s, end_time=%s,
                                         transport_method=%s, transport_minutes=%s
                                  WHERE itinerary_id=%s AND trip_id=%s""",
                               (index, new_start, new_end, method, minutes or 0, itinerary_id, trip_id))
            else:
                cursor.execute("UPDATE itineraries SET sort_order=%s, start_time=%s, end_time=%s WHERE itinerary_id=%s AND trip_id=%s",
                               (index, new_start, new_end, itinerary_id, trip_id))
        connection.commit()
    except Exception as error:
        connection.rollback(); print("套用智慧排程失敗：", error)
        return jsonify(error="套用排程失敗，請再試一次。"), 500
    finally:
        cursor.close(); connection.close()
    return jsonify(ok=True)


def _build_stay_plan(cursor, trip, items, tier):
    """住宿與預算建議：每一晚依當天最後一站推薦附近住宿，並依已排入的行程估算整趟預算。"""
    nights = max(0, (trip["end_date"] - trip["start_date"]).days)
    by_day = {}
    for item in items:
        by_day.setdefault(item["itinerary_date"], []).append(item)
    all_coords = [c for c in (smart_trip.coordinates(i["lat"], i["lng"]) for i in items) if c]
    center = ((sum(c[0] for c in all_coords) / len(all_coords), sum(c[1] for c in all_coords) / len(all_coords))
              if all_coords else None)
    plan, lodging_prices = [], []
    for night in range(nights):
        day = trip["start_date"] + timedelta(days=night)
        day_items = by_day.get(day, [])
        booked = next((i for i in day_items if i["item_type"] == "accommodation"), None)
        anchor = next((i for i in reversed(day_items)
                       if i["item_type"] != "accommodation" and smart_trip.coordinates(i["lat"], i["lng"])), None)
        origin = smart_trip.coordinates(anchor["lat"], anchor["lng"]) if anchor else center
        hotels = smart_trip.find_nearby_accommodations(cursor, origin, trip["country_id"]) if origin else []
        if booked:
            lodging_prices.append(booked.get("price_per_night") or booked.get("estimated_cost") or None)
        else:
            priced = sorted(float(h["price_per_night"]) for h in hotels if h.get("price_per_night"))
            lodging_prices.append(priced[len(priced) // 2] if priced else None)
        plan.append({"date": day, "anchor": anchor["title"] if anchor else ("行程中心點" if center else None),
                     "booked": booked, "hotels": hotels})
    budget = smart_trip.estimate_budget(items, trip.get("people_count"), nights, lodging_prices, tier)
    return plan, budget


ALLOWED_SCAN_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
SCAN_KINDS = {"flight": "機票", "hotel": "訂房", "train": "車票", "ticket": "門票／票券", "receipt": "收據／消費", "other": "其他"}
SCAN_MAX_BYTES = 8 * 1024 * 1024


def _iso_date_or_none(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None


@member_bp.route("/trips/<int:trip_id>/expenses/scan", methods=["POST"])
@login_required("member")
def scan_expense_image(trip_id):
    """上傳機票、訂房或消費截圖，由 AI 辨識金額、日期與類型，回傳給前端填入新增費用表單（不會直接儲存）。"""
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return jsonify(error="請選擇一張截圖。"), 400
    mime = (upload.mimetype or "").lower()
    if mime not in ALLOWED_SCAN_TYPES:
        return jsonify(error="只支援 JPG、PNG、WEBP 或 HEIC 圖片。"), 400
    image = upload.read(SCAN_MAX_BYTES + 1)
    if len(image) > SCAN_MAX_BYTES:
        return jsonify(error="圖片超過 8MB，請裁切或壓縮後再上傳。"), 400
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
    finally:
        cursor.close(); connection.close()
    if not trip:
        return jsonify(error="你沒有這個行程的權限。"), 403
    if not ai_ready():
        return jsonify(error="伺服器尚未設定 AI 服務金鑰，暫時無法辨識截圖，請手動填寫。"), 503
    prompt = (
        "你是旅遊記帳助手。請辨識這張截圖（機票、訂房確認、車票、門票或消費收據），只回傳 JSON 物件，文字用繁體中文。"
        f"這趟旅行：{trip.get('country') or ''} {trip.get('city') or ''}，{trip['start_date']} 到 {trip['end_date']}，"
        f"記帳幣別 {trip['currency']}。"
        '格式：{"kind":"flight|hotel|train|ticket|receipt|other","expense_name":"簡短名稱，例如「長榮 BR198 台北→東京」",'
        '"amount":數字或null,"currency":"三碼幣別或null","date":"YYYY-MM-DD 或 null（付款或消費日）",'
        '"merchant":"商家或航空公司","details":"一句話重點，例如航班時間、入住退房日期、房型",'
        '"itinerary":{"date":"YYYY-MM-DD 或 null","start_time":"HH:MM 或 null","title":"要放進每日行程的名稱或 null",'
        '"item_type":"transport|accommodation|attraction|restaurant|other"},"confidence":"high|medium|low"}。'
        "amount 請填總金額（含稅）；看不清楚的欄位填 null，不要猜。itinerary 只有機票、車票、訂房、門票需要填。"
    )
    try:
        payload = ask_json(prompt, image_bytes=image, image_mime=mime)
    except AIUnavailable as error:
        return jsonify(error=str(error)), 502
    kind = payload.get("kind") if payload.get("kind") in SCAN_KINDS else "other"
    try:
        amount = round(float(payload.get("amount")), 2) if payload.get("amount") is not None else None
        if amount is not None and not 0 <= amount <= 100_000_000:
            amount = None
    except (TypeError, ValueError):
        amount = None
    currency = str(payload.get("currency") or "").strip().upper()
    currency = currency if re.fullmatch(r"[A-Z]{3}", currency) else None
    itinerary = payload.get("itinerary") if isinstance(payload.get("itinerary"), dict) else {}
    suggestion = None
    item_date = _iso_date_or_none(itinerary.get("date"))
    title = str(itinerary.get("title") or "").strip()[:150]
    if item_date and title and trip["start_date"].isoformat() <= item_date <= trip["end_date"].isoformat():
        start = str(itinerary.get("start_time") or "")
        suggestion = {
            "date": item_date, "title": title,
            "start_time": start if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", start) else "",
            "item_type": itinerary.get("item_type") if itinerary.get("item_type") in ITEM_TYPE_LABELS else "other",
        }
    warnings = ["AI 辨識結果僅供參考，請核對截圖上的金額、日期，與實際付款或訂房網站顯示的價格是否一致。"]
    if currency and currency != trip["currency"]:
        warnings.append(f"截圖幣別是 {currency}，這趟行程記帳幣別是 {trip['currency']}，請自行換算後再儲存。")
    if payload.get("confidence") == "low":
        warnings.append("截圖不太清楚，部分欄位可能不正確。")
    return jsonify(
        kind=kind, kind_label=SCAN_KINDS[kind],
        expense_name=str(payload.get("expense_name") or "").strip()[:150],
        amount=amount, currency=currency, date=_iso_date_or_none(payload.get("date")),
        merchant=str(payload.get("merchant") or "").strip()[:100],
        details=str(payload.get("details") or "").strip()[:300],
        itinerary=suggestion, warnings=warnings,
    )


PROPOSAL_TYPES = ("attraction", "restaurant", "accommodation", "activity", "transport", "date", "other")


@member_bp.route("/trips/<int:trip_id>/proposals", methods=["POST"])
@login_required("member")
def add_proposal(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    review_proposal_id = None  # 需要審核的提案送出後，請 AI 小幫手在背景先幫管理員檢查
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        title = request.form.get("title", "").strip()
        proposal_type = request.form.get("proposal_type", "other")
        website_url = request.form.get("website_url", "").strip() or None
        image_path = None
        image_file = request.files.get("image")
        if not trip: flash("你沒有新增提案的權限。", "error")
        elif not title: flash("請填寫提案名稱。", "error")
        elif proposal_type not in PROPOSAL_TYPES: flash("提案類型無效。", "error")
        else:
            if image_file and image_file.filename:
                try:
                    image_path = save_uploaded_image(image_file, "proposals")
                except ValueError as error:
                    flash(str(error), "error")
                    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")
            needs_review = proposal_type in ("attraction", "restaurant", "accommodation")
            review_status = "pending" if needs_review else "not_required"
            cursor.execute("""INSERT INTO proposals (trip_id,proposer_id,proposal_type,title,location,description,estimated_cost,proposed_date,website_url,image_path,content_review_status)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (trip_id, session["user_id"], proposal_type, title, request.form.get("location", "").strip() or None, request.form.get("description", "").strip() or None, request.form.get("estimated_cost") or 0, request.form.get("proposed_date") or None, website_url, image_path, review_status))
            new_proposal_id = cursor.lastrowid
            connection.commit()
            if needs_review:
                review_proposal_id = new_proposal_id
                flash("提案已送出，旅伴可以先討論；新增景點、餐廳或住宿須經內容管理員審核後才會正式收錄。", "success")
            else:
                flash("提案已送出，旅伴現在可以一起討論。", "success")
    except Exception:
        connection.rollback(); flash("送出提案失敗。", "error")
        review_proposal_id = None
    finally:
        cursor.close(); connection.close()
    if review_proposal_id:
        proposal_review.schedule_new_proposal(review_proposal_id)
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/proposals/<int:proposal_id>/edit", methods=["POST"])
@login_required("member")
def edit_proposal(trip_id, proposal_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM proposals WHERE proposal_id=%s AND trip_id=%s", (proposal_id, trip_id))
        proposal = cursor.fetchone()
        title = request.form.get("title", "").strip()
        proposal_type = request.form.get("proposal_type", "other")

        if not trip or not proposal: flash("找不到這個提案。", "error")
        elif proposal["proposer_id"] != session["user_id"]: flash("只有提案人可以修改這個提案。", "error")
        elif proposal["status"] != "discussing": flash("提案已進入投票或已有結果，無法再修改。", "error")
        elif not title: flash("請填寫提案名稱。", "error")
        elif proposal_type not in PROPOSAL_TYPES: flash("提案類型無效。", "error")
        else:
            image_path = proposal["image_path"]
            image_file = request.files.get("image")
            if image_file and image_file.filename:
                try:
                    new_path = save_uploaded_image(image_file, "proposals")
                except ValueError as error:
                    flash(str(error), "error")
                    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")
                if image_path: delete_uploaded_image(image_path)
                image_path = new_path
            cursor.execute("""UPDATE proposals SET proposal_type=%s,title=%s,location=%s,description=%s,estimated_cost=%s,proposed_date=%s,website_url=%s,image_path=%s
                              WHERE proposal_id=%s""", (proposal_type, title, request.form.get("location", "").strip() or None, request.form.get("description", "").strip() or None, request.form.get("estimated_cost") or 0, request.form.get("proposed_date") or None, request.form.get("website_url", "").strip() or None, image_path, proposal_id))
            connection.commit(); flash("提案已更新。", "success")
    except Exception:
        connection.rollback(); flash("修改提案失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/proposals/<int:proposal_id>/cancel", methods=["POST"])
@login_required("member")
def cancel_proposal(trip_id, proposal_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM proposals WHERE proposal_id=%s AND trip_id=%s", (proposal_id, trip_id))
        proposal = cursor.fetchone()

        if not trip or not proposal: flash("找不到這個提案。", "error")
        elif proposal["proposer_id"] != session["user_id"]: flash("只有提案人可以取消這個提案。", "error")
        elif proposal["status"] != "discussing": flash("提案已進入投票或已有結果，無法取消。", "error")
        else:
            cursor.execute("UPDATE proposals SET status='cancelled' WHERE proposal_id=%s", (proposal_id,))
            connection.commit(); flash("提案已取消。", "success")
    except Exception:
        connection.rollback(); flash("取消提案失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/proposals/<int:proposal_id>/delete", methods=["POST"])
@login_required("member")
def delete_proposal(trip_id, proposal_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM proposals WHERE proposal_id=%s AND trip_id=%s", (proposal_id, trip_id))
        proposal = cursor.fetchone()

        if not trip or not proposal: flash("找不到這個提案。", "error")
        elif proposal["proposer_id"] != session["user_id"]: flash("只有提案人可以刪除這個提案。", "error")
        elif proposal["status"] in ("voting", "approved", "added"): flash("提案正在投票或已有結果，無法刪除。", "error")
        else:
            cursor.execute("DELETE FROM proposals WHERE proposal_id=%s", (proposal_id,))
            connection.commit()
            if proposal["image_path"]: delete_uploaded_image(proposal["image_path"])
            flash("提案已刪除。", "success")
    except Exception:
        connection.rollback(); flash("刪除提案失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


PROPOSAL_TO_ITEM_TYPE = {"attraction": "attraction", "restaurant": "restaurant", "accommodation": "accommodation", "transport": "transport", "activity": "other", "other": "other"}


@member_bp.route("/trips/<int:trip_id>/proposals/<int:proposal_id>/add-to-itinerary", methods=["POST"])
@login_required("member")
def add_proposal_to_itinerary(trip_id, proposal_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM proposals WHERE proposal_id=%s AND trip_id=%s", (proposal_id, trip_id))
        proposal = cursor.fetchone()

        if not trip or not proposal: flash("找不到這個提案。", "error")
        elif trip["member_role"] != "owner": flash("只有行程建立者可以把提案加入正式行程。", "error")
        elif proposal["status"] != "approved": flash("只有已通過的提案可以加入正式行程。", "error")
        elif proposal["proposal_type"] == "date": flash("日期調整方案請直接修改行程日期，無法加入每日行程。", "error")
        else:
            item_type = PROPOSAL_TO_ITEM_TYPE.get(proposal["proposal_type"], "other")
            day = proposal["proposed_date"] or trip["start_date"]
            cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s", (trip_id, day)); order = cursor.fetchone()["next_order"]
            cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,is_all_day,address,estimated_cost,notes,sort_order)
                              VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)""", (trip_id, session["user_id"], day, item_type, proposal["title"], proposal["location"], proposal["estimated_cost"], proposal["description"], order))
            cursor.execute("UPDATE proposals SET status='added' WHERE proposal_id=%s", (proposal_id,))
            connection.commit(); flash("提案已加入每日行程。", "success")
    except Exception:
        connection.rollback(); flash("加入正式行程失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


ITINERARY_CHANGE_FIELDS = ("title", "item_type", "itinerary_date", "start_time", "end_time", "is_all_day", "address", "transport_method", "transport_minutes", "estimated_cost", "notes")
ITINERARY_CHANGE_FIELD_LABELS = {
    "title": "項目名稱", "item_type": "類型", "itinerary_date": "日期", "start_time": "開始時間",
    "end_time": "結束時間", "is_all_day": "整天", "address": "地點", "transport_method": "交通方式",
    "transport_minutes": "交通時間（分鐘）", "estimated_cost": "預估費用", "notes": "備註",
}


def _itinerary_snapshot(item):
    return {
        "title": item["title"],
        "item_type": item["item_type"],
        "itinerary_date": item["itinerary_date"].isoformat() if item["itinerary_date"] else None,
        "start_time": format_hm(item["start_time"]) if item["start_time"] else None,
        "end_time": format_hm(item["end_time"]) if item["end_time"] else None,
        "is_all_day": bool(item["is_all_day"]),
        "address": item["address"],
        "transport_method": item["transport_method"],
        "transport_minutes": item["transport_minutes"],
        "estimated_cost": float(item["estimated_cost"]) if item["estimated_cost"] is not None else 0,
        "notes": item["notes"],
    }


def _itinerary_change_from_form(form, base=None):
    """依表單值組出提議的新內容；update 時以目前內容(base)當底，只覆寫使用者有填的欄位。"""
    data = dict(base) if base else {key: None for key in ITINERARY_CHANGE_FIELDS}
    if form.get("title", "").strip():
        data["title"] = form["title"].strip()
    if form.get("item_type") in ITEM_TYPE_LABELS:
        data["item_type"] = form["item_type"]
    if form.get("itinerary_date", "").strip():
        data["itinerary_date"] = form["itinerary_date"].strip()
    time_mode = form.get("time_mode", "").strip()
    if time_mode:
        if time_mode not in TIME_MODES: time_mode = "range"
        start = form.get("start_time", "").strip() or None
        end = form.get("end_time", "").strip() or None
        is_all_day = False
        if time_mode == "all_day": start, end, is_all_day = None, None, True
        elif time_mode == "start_only": end = None
        elif time_mode == "end_only": start = None
        data["start_time"], data["end_time"], data["is_all_day"] = start, end, is_all_day
    if form.get("address", "").strip():
        data["address"] = form["address"].strip()
    if form.get("transport_method", "").strip():
        data["transport_method"] = form["transport_method"].strip()
    if form.get("transport_minutes", "").strip():
        try: data["transport_minutes"] = int(form["transport_minutes"])
        except ValueError: pass
    if form.get("estimated_cost", "").strip():
        try: data["estimated_cost"] = float(form["estimated_cost"])
        except ValueError: pass
    if form.get("notes", "").strip():
        data["notes"] = form["notes"].strip()
    return data


@member_bp.route("/trips/<int:trip_id>/itinerary-changes", methods=["POST"])
@login_required("member")
def propose_itinerary_change(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        change_type = request.form.get("change_type", "")
        reason = request.form.get("reason", "").strip()
        target_id = request.form.get("target_itinerary_id", "").strip() or None

        if not trip or not _can_edit(trip): flash("只有建立者或共同編輯者可以提出行程變更提案。", "error")
        elif change_type not in ("update", "delete", "create"): flash("請選擇變更類型。", "error")
        elif not reason: flash("請填寫提案原因。", "error")
        else:
            before_data = after_data = target_itinerary_id = None
            if change_type in ("update", "delete"):
                existing = None
                if target_id:
                    cursor.execute("SELECT * FROM itineraries WHERE itinerary_id=%s AND trip_id=%s", (target_id, trip_id))
                    existing = cursor.fetchone()
                if not existing:
                    flash("找不到要變更的行程項目。", "error")
                    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")
                target_itinerary_id = existing["itinerary_id"]
                before_data = _itinerary_snapshot(existing)
                title = (f"修改「{existing['title']}」" if change_type == "update" else f"刪除「{existing['title']}」")
                if change_type == "update":
                    after_data = _itinerary_change_from_form(request.form, before_data)
            else:
                after_data = _itinerary_change_from_form(request.form)
                if not after_data.get("title") or not after_data.get("itinerary_date"):
                    flash("新增項目至少要填寫名稱與日期。", "error")
                    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")
                title = f"新增「{after_data['title']}」"

            cursor.execute("""INSERT INTO proposals (trip_id,proposer_id,proposal_type,target_itinerary_id,change_type,before_data,after_data,title,description,content_review_status)
                              VALUES (%s,%s,'itinerary_change',%s,%s,%s,%s,%s,%s,'not_required')""",
                           (trip_id, session["user_id"], target_itinerary_id, change_type,
                            json.dumps(before_data, ensure_ascii=False) if before_data is not None else None,
                            json.dumps(after_data, ensure_ascii=False) if after_data is not None else None,
                            title, reason))
            connection.commit()
            flash("行程變更提案已送出，旅伴可以一起討論。", "success")
    except Exception:
        connection.rollback(); flash("送出提案失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/proposals/<int:proposal_id>/apply-change", methods=["POST"])
@login_required("member")
def apply_itinerary_change(trip_id, proposal_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM proposals WHERE proposal_id=%s AND trip_id=%s AND proposal_type='itinerary_change'", (proposal_id, trip_id))
        proposal = cursor.fetchone()

        if not trip or not proposal: flash("找不到這個提案。", "error")
        elif trip["member_role"] != "owner": flash("只有行程建立者可以套用行程變更。", "error")
        elif proposal["status"] != "approved": flash("只有已通過的提案可以套用。", "error")
        else:
            after = json.loads(proposal["after_data"]) if proposal["after_data"] else None
            if proposal["change_type"] == "delete":
                cursor.execute("DELETE FROM itineraries WHERE itinerary_id=%s AND trip_id=%s", (proposal["target_itinerary_id"], trip_id))
            elif proposal["change_type"] == "update":
                cursor.execute("SELECT itinerary_id FROM itineraries WHERE itinerary_id=%s AND trip_id=%s", (proposal["target_itinerary_id"], trip_id))
                if not cursor.fetchone():
                    flash("原本的行程項目已不存在，無法套用。", "error")
                    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")
                cursor.execute("""UPDATE itineraries SET title=%s,item_type=%s,itinerary_date=%s,start_time=%s,end_time=%s,is_all_day=%s,address=%s,transport_method=%s,transport_minutes=%s,estimated_cost=%s,notes=%s
                                  WHERE itinerary_id=%s""", (after["title"], after["item_type"], after["itinerary_date"], after["start_time"], after["end_time"], after["is_all_day"], after["address"], after["transport_method"], after["transport_minutes"], after["estimated_cost"], after["notes"], proposal["target_itinerary_id"]))
            else:
                cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s", (trip_id, after["itinerary_date"])); order = cursor.fetchone()["next_order"]
                cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,address,transport_method,transport_minutes,estimated_cost,notes,sort_order)
                                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (trip_id, session["user_id"], after["itinerary_date"], after["item_type"] or "other", after["title"], after["start_time"], after["end_time"], after["is_all_day"], after["address"], after["transport_method"], after["transport_minutes"] or 0, after["estimated_cost"] or 0, after["notes"], order))
            cursor.execute("UPDATE proposals SET status='added' WHERE proposal_id=%s", (proposal_id,))
            connection.commit(); flash("行程變更已套用。", "success")
    except Exception:
        connection.rollback(); flash("套用失敗，請再試一次。", "error")
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


def _comment_anchor(comment):
    if comment.get("proposal_id"): return "#proposals"
    return "#chat"


@member_bp.route("/trips/<int:trip_id>/comments", methods=["POST"])
@login_required("member")
def add_comment(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    anchor = "#chat"
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        content = request.form.get("content", "").strip()
        parent_id = request.form.get("parent_comment_id", "").strip() or None
        proposal_id = request.form.get("proposal_id", "").strip() or None

        if proposal_id:
            cursor.execute("SELECT proposal_id FROM proposals WHERE proposal_id=%s AND trip_id=%s", (proposal_id, trip_id))
            if not cursor.fetchone(): proposal_id = None
            else: anchor = "#proposals"

        if not trip: flash("你沒有留言的權限。", "error")
        elif not proposal_id: flash("留言只保留在提案底下；行程的討論請到聊天室跟旅伴聊。", "error")
        elif not content: flash("留言內容不能是空的。", "error")
        else:
            if parent_id:
                cursor.execute("SELECT comment_id FROM comments WHERE comment_id=%s AND trip_id=%s", (parent_id, trip_id))
                if not cursor.fetchone():
                    parent_id = None
            cursor.execute("""INSERT INTO comments (trip_id,user_id,parent_comment_id,itinerary_id,proposal_id,content)
                              VALUES (%s,%s,%s,%s,%s,%s)""", (trip_id, session["user_id"], parent_id, None, proposal_id, content))
            _notify_mentions(cursor, trip, _load_mention_members(cursor, trip_id), content, anchor, session["user_id"])
            connection.commit()
            flash("留言已送出。", "success")
    except Exception:
        connection.rollback(); flash("留言失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + anchor)


@member_bp.route("/trips/<int:trip_id>/comments/<int:comment_id>/edit", methods=["POST"])
@login_required("member")
def edit_comment(trip_id, comment_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    anchor = "#chat"
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM comments WHERE comment_id=%s AND trip_id=%s", (comment_id, trip_id))
        comment = cursor.fetchone()
        content = request.form.get("content", "").strip()
        if comment: anchor = _comment_anchor(comment)

        if not trip or not comment: flash("找不到這則留言。", "error")
        elif comment["user_id"] != session["user_id"]: flash("只有留言者本人可以修改留言。", "error")
        elif comment["status"] != "visible": flash("這則留言已被刪除，無法修改。", "error")
        elif not content: flash("留言內容不能是空的。", "error")
        else:
            cursor.execute("UPDATE comments SET content=%s WHERE comment_id=%s", (content, comment_id))
            # 編輯時只通知這次新加進來的提及，原本就被提及的人不重複通知
            mention_members = _load_mention_members(cursor, trip_id)
            _notify_mentions(cursor, trip, mention_members, content, anchor, session["user_id"],
                             exclude_ids=_mentioned_user_ids(comment["content"], mention_members))
            connection.commit()
            flash("留言已更新。", "success")
    except Exception:
        connection.rollback(); flash("修改失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + anchor)


@member_bp.route("/trips/<int:trip_id>/comments/<int:comment_id>/delete", methods=["POST"])
@login_required("member")
def delete_comment(trip_id, comment_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    anchor = "#chat"
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM comments WHERE comment_id=%s AND trip_id=%s", (comment_id, trip_id))
        comment = cursor.fetchone()
        if comment: anchor = _comment_anchor(comment)

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
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + anchor)


@member_bp.route("/trips/<int:trip_id>/comments/<int:comment_id>/report", methods=["POST"])
@login_required("member")
def report_comment(trip_id, comment_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    anchor = "#chat"
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM comments WHERE comment_id=%s AND trip_id=%s", (comment_id, trip_id))
        comment = cursor.fetchone()
        reason = request.form.get("reason", "").strip()
        description = request.form.get("description", "").strip()
        if comment: anchor = _comment_anchor(comment)

        if not trip or not comment: flash("找不到這則留言。", "error")
        elif comment["user_id"] == session["user_id"]: flash("不能檢舉自己的留言。", "error")
        elif reason not in COMMENT_REPORT_REASONS: flash("請選擇檢舉原因。", "error")
        elif len(description) > 500: flash("說明請勿超過 500 字。", "error")
        else:
            cursor.execute("""SELECT report_id FROM reports WHERE reporter_id=%s AND target_type='comment' AND target_id=%s
                              AND status IN ('pending','processing') LIMIT 1""", (session["user_id"], comment_id))
            if cursor.fetchone():
                flash("你已檢舉過這則留言，管理員正在處理。", "error")
            else:
                cursor.execute("""INSERT INTO reports (reporter_id, target_type, target_id, reason, description)
                                  VALUES (%s, 'comment', %s, %s, %s)""", (session["user_id"], comment_id, COMMENT_REPORT_PREFIX + reason, description or None))
                connection.commit()
                flash("檢舉已送出，系統管理員會查看。", "success")
    except Exception:
        connection.rollback(); flash("檢舉失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + anchor)


CHAT_MAX_LENGTH = 1000
_chat_reply_ready = False
_chat_reply_checked_at = 0.0


def _chat_reply_available(cursor):
    """聊天室「回覆」要用到 reply_to_message_id 欄位(database/migrate_1127_chat_reply.sql)。
    還沒加欄位時聊天室照常用，只是不能回覆；每 60 秒最多重新檢查一次。"""
    global _chat_reply_ready, _chat_reply_checked_at
    import time as _time
    if _chat_reply_ready: return True
    if _time.time() - _chat_reply_checked_at < 60: return False
    _chat_reply_checked_at = _time.time()
    try:
        cursor.execute("SELECT reply_to_message_id FROM trip_chat_messages LIMIT 0")
        cursor.fetchall()
        _chat_reply_ready = True
    except Exception:
        pass
    return _chat_reply_ready


def _chat_message_sql(with_reply):
    """聊天訊息的 SELECT 欄位與 JOIN；有回覆欄位時順便帶出「被回覆的那則」的作者與內容。"""
    columns = "m.message_id, m.user_id, m.content, m.created_at, u.full_name, u.nickname"
    joins = "FROM trip_chat_messages m JOIN users u ON u.user_id = m.user_id"
    if with_reply:
        columns += (", m.reply_to_message_id, p.content AS reply_content, p.user_id AS reply_user_id,"
                    " pu.full_name AS reply_full_name, pu.nickname AS reply_nickname")
        joins += (" LEFT JOIN trip_chat_messages p ON p.message_id = m.reply_to_message_id AND p.trip_id = m.trip_id"
                  " LEFT JOIN users pu ON pu.user_id = p.user_id")
    return columns, joins


def _chat_reply_payload(row):
    if not row.get("reply_to_message_id"): return None
    if row.get("reply_content") is None:
        return {"id": row["reply_to_message_id"], "name": "", "content": "原訊息已不存在"}
    content = "訊息已由團長移除" if row["reply_content"] == REMOVED_CHAT_CONTENT else row["reply_content"]
    return {"id": row["reply_to_message_id"], "user_id": row["reply_user_id"],
            "name": row["reply_nickname"] or row["reply_full_name"],
            "content": content if len(content) <= 80 else content[:80] + "…"}


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


def _post_chat_message(cursor, trip_id, user_id, content, reply_to=None):
    if reply_to:
        cursor.execute("INSERT INTO trip_chat_messages (trip_id,user_id,content,reply_to_message_id) VALUES (%s,%s,%s,%s)",
                       (trip_id, user_id, content, reply_to))
    else:
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
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            return jsonify(error="你沒有查看此行程的權限。"), 403
        after = request.args.get("after", 0, type=int)
        can_reply = _chat_reply_available(cursor)
        columns, joins = _chat_message_sql(can_reply)
        if after > 0:
            cursor.execute(f"""SELECT {columns} {joins}
                               WHERE m.trip_id=%s AND m.message_id > %s ORDER BY m.message_id""", (trip_id, after))
            rows = cursor.fetchall()
        else:
            cursor.execute(f"""SELECT * FROM (
                                   SELECT {columns} {joins}
                                   WHERE m.trip_id=%s ORDER BY m.message_id DESC LIMIT 200
                               ) recent ORDER BY message_id""", (trip_id,))
            rows = cursor.fetchall()
        members = _chat_members(cursor, trip_id)
        cursor.execute("SELECT COALESCE(MAX(message_id),0) AS latest FROM trip_chat_messages WHERE trip_id=%s", (trip_id,))
        latest_id = int(cursor.fetchone()["latest"])
        cursor.execute("SELECT message_id FROM trip_chat_messages WHERE trip_id=%s AND content=%s", (trip_id, REMOVED_CHAT_CONTENT))
        removed_ids = [row["message_id"] for row in cursor.fetchall()]
        payload = {
            "me": session["user_id"],
            "latest_id": latest_id,
            "messages": [{
                "id": r["message_id"], "user_id": r["user_id"], "name": _display_name(r),
                "content": "訊息已由團長移除" if r["content"] == REMOVED_CHAT_CONTENT else r["content"],
                "removed": r["content"] == REMOVED_CHAT_CONTENT, "time": r["created_at"].strftime("%m/%d %H:%M"),
                "reply": _chat_reply_payload(r),
            } for r in rows],
            "can_moderate": trip["member_role"] == "owner",
            "can_reply": can_reply,
            "removed_ids": removed_ids,
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
    body = request.get_json(silent=True) or {}
    content = (body.get("content") or "").strip()
    reply_to = body.get("reply_to")
    reply_to = reply_to if isinstance(reply_to, int) and not isinstance(reply_to, bool) and reply_to > 0 else None
    if not content or content == REMOVED_CHAT_CONTENT: return jsonify(error="訊息不能是空的或使用系統保留文字。"), 400
    if len(content) > CHAT_MAX_LENGTH: return jsonify(error=f"訊息最多 {CHAT_MAX_LENGTH} 字。"), 400
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            return jsonify(error="你沒有這個行程的聊天權限。"), 403
        if blocked_term(cursor, content):
            return jsonify(error="訊息包含禁止內容，請修改後再送出。"), 400
        replied = None
        if reply_to:
            if not _chat_reply_available(cursor):
                return jsonify(error="聊天室回覆功能還沒開通(資料庫還沒更新)，請先直接傳訊息。"), 400
            cursor.execute("SELECT user_id, content FROM trip_chat_messages WHERE message_id=%s AND trip_id=%s", (reply_to, trip_id))
            replied = cursor.fetchone()
            if not replied or replied["content"] == REMOVED_CHAT_CONTENT:
                return jsonify(error="要回覆的訊息不存在或已被移除。"), 400
        message_id = _post_chat_message(cursor, trip_id, session["user_id"], content, reply_to=reply_to)
        mention_members = _load_mention_members(cursor, trip_id)
        notified = set()
        if replied and replied["user_id"] != session["user_id"]:
            # 被回覆的人一定會收到通知(就算沒有 @ 他)
            author = next((m for m in mention_members if m["user_id"] == session["user_id"]), {})
            author_name = author.get("nickname") or author.get("full_name") or "旅伴"
            snippet = content if len(content) <= 60 else content[:60] + "…"
            send_notification(cursor, replied["user_id"], "mention", "comment", "有人回覆了你的聊天訊息",
                              f"{author_name} 在「{trip['trip_name']}」的聊天室回覆了你：{snippet}",
                              url_for("member.trip_detail", trip_id=trip_id) + "#chat", trip_id=trip_id)
            notified.add(replied["user_id"])
        _notify_mentions(cursor, trip, mention_members, content, "#chat", session["user_id"], exclude_ids=notified, place="聊天室")
        connection.commit()
    except Exception:
        connection.rollback(); return jsonify(error="訊息送出失敗，請再試一次。"), 500
    finally:
        cursor.close(); connection.close()
    return jsonify(ok=True, message_id=message_id)


@member_bp.route("/trips/<int:trip_id>/chat/<int:message_id>/remove", methods=["POST"])
@login_required("member")
def chat_remove(trip_id, message_id):
    connection = get_db_connection()
    if connection is None: return jsonify(error="目前無法連線資料庫。"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            return jsonify(error="只有行程發起人可以移除訊息。"), 403
        if not remove_trip_message(cursor, trip_id, message_id, session["user_id"]):
            return jsonify(error="找不到可移除的訊息。"), 404
        connection.commit()
    except Exception:
        connection.rollback()
        return jsonify(error="移除失敗，請再試一次。"), 500
    finally:
        cursor.close()
        connection.close()
    return jsonify(ok=True)


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
        elif _linked_active_friend_group(cursor, trip_id): flash("這是揪團行程，請讓旅伴從揪團頁申請加入。", "error")
        else:
            cursor.execute("SELECT user_id,email FROM users WHERE username=%s AND role='member' AND status='active'", (username,)); invitee=cursor.fetchone()
            if not invitee: flash("找不到可邀請的一般會員帳號。", "error")
            else:
                cursor.execute("SELECT join_status FROM trip_members WHERE trip_id=%s AND user_id=%s",(trip_id,invitee["user_id"]))
                membership = cursor.fetchone()
                if membership and membership["join_status"] == "accepted": flash("此會員已經在行程中。", "error")
                else:
                    cursor.execute("SELECT invitation_id FROM trip_invitations WHERE trip_id=%s AND invitee_id=%s AND status='pending'",(trip_id,invitee["user_id"]))
                    if cursor.fetchone(): flash("已經有一筆待回覆的邀請了。", "error")
                    else:
                        code=secrets.token_urlsafe(8)
                        cursor.execute("INSERT INTO trip_invitations (trip_id,inviter_id,invitee_id,invitee_email,invite_code,assigned_role,expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",(trip_id,session["user_id"],invitee["user_id"],invitee["email"],code,role,expires_at))
                        send_notification(cursor, invitee["user_id"], "trip", "invitation", "收到旅程邀請", f"你被邀請加入「{trip['trip_name']}」", url_for('member.my_trips') + "#invitations", trip_id=trip_id)
                        connection.commit(); flash("邀請已送出。", "success")
    except Exception:
        connection.rollback(); flash("送出邀請失敗。", "error")
    finally: cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail",trip_id=trip_id)+"#members")


@member_bp.route("/trips/<int:trip_id>/invite-link", methods=["POST"])
@login_required("member")
def create_invite_link(trip_id):
    role = request.form.get("assigned_role", "viewer")
    expires_at = request.form.get("expires_at", "").strip() or None
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有建立者可以產生邀請連結。", "error")
        elif role not in ("editor", "viewer"):
            flash("請選擇有效的成員權限。", "error")
        elif _linked_active_friend_group(cursor, trip_id):
            flash("這是揪團行程，不能另外產生邀請連結。", "error")
        else:
            cursor.execute("""SELECT invitation_id FROM trip_invitations
                WHERE trip_id=%s AND invitee_id IS NULL AND status='pending'
                  AND (expires_at IS NULL OR expires_at > NOW())""", (trip_id,))
            if cursor.fetchone():
                flash("已經有一個啟用中的邀請連結了，請先關閉再產生新的。", "error")
            else:
                cursor.execute("""INSERT INTO trip_invitations
                    (trip_id,inviter_id,invitee_id,invite_code,invite_token,assigned_role,expires_at)
                    VALUES (%s,%s,NULL,%s,%s,%s,%s)""",
                    (trip_id, session["user_id"], secrets.token_urlsafe(8), secrets.token_urlsafe(24), role, expires_at))
                connection.commit()
                flash("邀請連結已產生，複製下方連結分享給旅伴吧。", "success")
    except Exception:
        connection.rollback(); flash("產生邀請連結失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#members")


@member_bp.route("/trips/<int:trip_id>/invite-link/<int:invitation_id>/close", methods=["POST"])
@login_required("member")
def close_invite_link(trip_id, invitation_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有建立者可以關閉邀請連結。", "error")
        else:
            cursor.execute("""UPDATE trip_invitations SET status='cancelled'
                WHERE invitation_id=%s AND trip_id=%s AND invitee_id IS NULL""", (invitation_id, trip_id))
            connection.commit()
            flash("邀請連結已關閉，舊連結將無法再加入行程。", "success")
    except Exception:
        connection.rollback(); flash("關閉邀請連結失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#members")


@member_bp.route("/invite/<token>")
def accept_invite_link(token):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("visitor"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""SELECT ti.*, t.trip_name, t.start_date, t.end_date,
                                  co.name AS country, ci.name AS city
                          FROM trip_invitations ti
                          JOIN trips t ON t.trip_id = ti.trip_id
                          JOIN countries co ON co.country_id = t.country_id
                          JOIN cities ci ON ci.city_id = t.city_id
                          WHERE ti.invite_token=%s AND ti.invitee_id IS NULL""", (token,))
        invitation = cursor.fetchone()
    finally:
        cursor.close(); connection.close()

    if not invitation or invitation["status"] != "pending" or (invitation["expires_at"] and invitation["expires_at"] < datetime.now()):
        flash("這個邀請連結已經失效，請向行程建立者索取新的連結。", "error")
        return redirect(url_for("member.dashboard") if "user_id" in session else url_for("visitor"))

    if "user_id" not in session:
        session["pending_invite_token"] = token
        flash("請先登入或註冊會員帳號，才能用這個連結加入行程。", "success")
        return redirect(url_for("login"))

    if session.get("role") != "member":
        flash("只有一般會員可以用邀請連結加入行程。", "error")
        return redirect(url_for("member.dashboard"))

    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT trip_member_id, join_status FROM trip_members WHERE trip_id=%s AND user_id=%s",
                       (invitation["trip_id"], session["user_id"]))
        already_member = cursor.fetchone()
    finally:
        cursor.close(); connection.close()

    if already_member and already_member["join_status"] == "accepted":
        flash("你已經是這趟行程的成員了。", "success")
        return redirect(url_for("member.trip_detail", trip_id=invitation["trip_id"]))

    return render_template("member/invite_link.html", invitation=invitation)


@member_bp.route("/invite/<token>/accept", methods=["POST"])
@login_required("member")
def confirm_invite_link(token):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM trip_invitations WHERE invite_token=%s AND invitee_id IS NULL", (token,))
        invitation = cursor.fetchone()
        if not invitation or invitation["status"] != "pending" or (invitation["expires_at"] and invitation["expires_at"] < datetime.now()):
            flash("這個邀請連結已經失效，請向行程建立者索取新的連結。", "error")
            return redirect(url_for("member.dashboard"))
        trip_id = invitation["trip_id"]
        if _linked_active_friend_group(cursor, trip_id):
            flash("這個行程已有揪團，請改從揪團頁申請加入。", "error")
            return redirect(url_for("friend_groups.index"))
        cursor.execute("SELECT trip_member_id, join_status FROM trip_members WHERE trip_id=%s AND user_id=%s", (trip_id, session["user_id"]))
        membership = cursor.fetchone()
        if membership and membership["join_status"] == "accepted":
            flash("你已經是這趟行程的成員了。", "success")
        else:
            cursor.execute("""INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at)
                VALUES (%s,%s,%s,'accepted',NOW())
                ON DUPLICATE KEY UPDATE member_role=VALUES(member_role), join_status='accepted', joined_at=NOW()""",
                (trip_id, session["user_id"], invitation["assigned_role"]))
            connection.commit()
            flash("已成功加入行程！", "success")
    except Exception:
        connection.rollback(); flash("加入行程失敗，請再試一次。", "error")
        return redirect(url_for("member.dashboard"))
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id))


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
                cursor.execute("""
                    UPDATE friend_group_members m JOIN friend_groups g ON g.group_id=m.group_id
                    SET m.status='left', m.show_profile=0, m.responded_at=NOW()
                    WHERE g.trip_id=%s AND m.user_id=%s AND m.status='approved'
                """, (trip_id, member_user_id))
                send_notification(cursor, member_user_id, "trip", "permission", "已被移出行程", f"你已被移出行程「{trip['trip_name']}」", url_for('member.dashboard'), trip_id=trip_id)
                connection.commit()
                flash("已移除該成員。", "success")
    except Exception:
        connection.rollback(); flash("移除成員失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#members")


@member_bp.route("/trips/<int:trip_id>/requests/<int:member_user_id>/approve", methods=["POST"])
@login_required("member")
def approve_trip_request(trip_id, member_user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有建立者可以審核加入申請。", "error")
        elif _linked_active_friend_group(cursor, trip_id):
            flash("這是揪團行程，請到揪團管理頁審核申請。", "error")
        else:
            cursor.execute("SELECT trip_id FROM trips WHERE trip_id=%s FOR UPDATE", (trip_id,))
            cursor.fetchone()
            cursor.execute("SELECT COUNT(*) AS c FROM trip_members WHERE trip_id=%s AND join_status='accepted'", (trip_id,))
            if trip["people_count"] and cursor.fetchone()["c"] >= trip["people_count"]:
                flash("行程已額滿，不能再核准新成員。", "error")
                return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#members")
            cursor.execute("SELECT trip_member_id FROM trip_members WHERE trip_id=%s AND user_id=%s AND join_status='requested'", (trip_id, member_user_id))
            if not cursor.fetchone():
                flash("找不到這筆申請。", "error")
            else:
                cursor.execute("UPDATE trip_members SET join_status='accepted', joined_at=NOW() WHERE trip_id=%s AND user_id=%s", (trip_id, member_user_id))
                send_notification(cursor, member_user_id, "trip", "permission", "加入申請已通過", f"你申請加入「{trip['trip_name']}」已經通過了", url_for('member.trip_detail', trip_id=trip_id), trip_id=trip_id)
                connection.commit()
                flash("已核准加入申請。", "success")
    except Exception:
        connection.rollback(); flash("審核失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#members")


@member_bp.route("/trips/<int:trip_id>/requests/<int:member_user_id>/reject", methods=["POST"])
@login_required("member")
def reject_trip_request(trip_id, member_user_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有建立者可以審核加入申請。", "error")
        else:
            cursor.execute("SELECT trip_member_id FROM trip_members WHERE trip_id=%s AND user_id=%s AND join_status='requested'", (trip_id, member_user_id))
            if not cursor.fetchone():
                flash("找不到這筆申請。", "error")
            else:
                cursor.execute("UPDATE trip_members SET join_status='rejected' WHERE trip_id=%s AND user_id=%s", (trip_id, member_user_id))
                connection.commit()
                flash("已婉拒這筆申請。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
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
        elif _linked_active_friend_group(cursor, invite["trip_id"]):
            flash("這個行程已有揪團，請改從揪團頁申請加入。", "error")
        else:
            cursor.execute("UPDATE trip_invitations SET status='accepted',responded_at=NOW() WHERE invitation_id=%s",(invitation_id,))
            cursor.execute("""INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at)
                VALUES (%s,%s,%s,'accepted',NOW())
                ON DUPLICATE KEY UPDATE member_role=VALUES(member_role), join_status='accepted', joined_at=NOW()""",
                (invite["trip_id"],session["user_id"],invite["assigned_role"]))
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
        cursor.execute("SELECT user_id,username,full_name,nickname,email,avatar_path,created_at,status,"
                       "line_sub IS NOT NULL AS line_linked,line_friend,"
                       "(password_hash IS NOT NULL OR google_sub IS NOT NULL) AS can_unbind_line "
                       "FROM users WHERE user_id=%s",(session["user_id"],)); user=cursor.fetchone()
        if user:
            user["status_label"] = {
                "active": "正常",
                "under_review": "審查中",
                "disabled": "已停用",
                "deleted": "已刪除",
            }.get(user["status"], user["status"])
        if request.method == "POST":
            nickname=request.form.get("nickname","").strip(); email=request.form.get("email","").strip()
            username=request.form.get("username","").strip()
            if not email: flash("電子郵件不可空白。", "error")
            elif not re.fullmatch(r"[A-Za-z0-9]{1,9}", username): flash("帳號請輸入9碼以內的英文或數字。", "error")
            else:
                cursor.execute("SELECT user_id FROM users WHERE email=%s AND user_id<>%s",(email,session["user_id"])); existing=cursor.fetchone()
                cursor.execute("SELECT user_id FROM users WHERE username=%s AND user_id<>%s",(username,session["user_id"])); username_taken=cursor.fetchone()
                if existing: flash("此電子郵件已被使用。", "error")
                elif username_taken: flash("這個帳號已經有人使用了。", "error")
                else:
                    # 頭像：有選新圖片就換新圖；有勾「移除頭像」就清空，改回顯示暱稱第一個字
                    old_avatar = user["avatar_path"]; avatar_path = old_avatar
                    try:
                        uploaded_path = save_uploaded_image(request.files.get("avatar"), "avatars")
                    except ValueError as exc:
                        flash(str(exc), "error"); return redirect(url_for("member.profile"))
                    if uploaded_path: avatar_path = uploaded_path
                    elif request.form.get("remove_avatar") == "1": avatar_path = None
                    cursor.execute("UPDATE users SET username=%s,nickname=%s,email=%s,avatar_path=%s WHERE user_id=%s",(username,nickname or None,email,avatar_path,session["user_id"])); connection.commit()
                    if old_avatar != avatar_path and old_avatar and not old_avatar.startswith("http"): delete_uploaded_image(old_avatar)
                    session["username"]=username; session["nickname"]=nickname; flash("個人資料已更新。", "success"); return redirect(url_for("member.profile"))
        notification_preferences = get_preferences(cursor, session["user_id"])
    finally: cursor.close(); connection.close()
    return render_template("member/profile.html", user=user, notification_categories=NOTIFICATION_CATEGORIES,
                           notification_preferences=notification_preferences)


@member_bp.route("/profile/notifications", methods=["POST"])
@login_required("member")
def update_notification_preferences():
    connection = _connection_or_home()
    if connection is None:
        return redirect(url_for("member.profile"))
    cursor = connection.cursor()
    try:
        enabled = set(request.form.getlist("categories")) & set(NOTIFICATION_CATEGORIES)
        save_preferences(cursor, session["user_id"], enabled)
        connection.commit()
        flash("通知設定已更新。", "success")
    except Exception as error:
        connection.rollback()
        print("更新通知設定失敗：", error)
        flash("通知設定更新失敗，請先確認是否已執行資料庫更新。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.profile") + "#notification-settings")


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
