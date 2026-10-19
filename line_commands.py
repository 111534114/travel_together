"""Keyword replies for the LINE official account."""

from datetime import date, datetime

from mysql.connector import Error

from config import PUBLIC_BASE_URL
from db import get_db_connection
from utils import format_hm
import line_flex as flex
import weather


NEXT_TRIP = "下一趟旅程"
TODO = "待辦事項"
MY_TRIPS = "我的行程"
HELP = "使用說明"
COMMANDS = (NEXT_TRIP, TODO, MY_TRIPS, HELP)
ALIASES = {"說明": HELP, "help": HELP, "選單": HELP, "行程": MY_TRIPS, "待辦": TODO, "下一趟": NEXT_TRIP}
LIST_LIMIT = 5
WEEKDAYS = "一二三四五六日"


def _link(path):
    return f"{PUBLIC_BASE_URL}{path}" if PUBLIC_BASE_URL else ""


def _with_link(lines, label, path):
    url = _link(path)
    if url:
        lines += ["", f"{label}：{url}"]
    return "\n".join(lines)


def _day(value):
    return f"{value.month}/{value.day}（{WEEKDAYS[value.weekday()]}）"


def _period(trip):
    if trip["start_date"] == trip["end_date"]:
        return _day(trip["start_date"])
    return f"{_day(trip['start_date'])} – {_day(trip['end_date'])}"


def help_text():
    return _with_link([
        "可以點下方按鈕，或直接輸入關鍵字：",
        f"・{NEXT_TRIP}：最近一趟旅程的日期和安排",
        f"・{TODO}：還沒投的票、還沒付的分帳",
        f"・{MY_TRIPS}：所有即將出發的行程",
        "", "行程出發前一天，也會自動傳 LINE 提醒你。",
    ], "打開網站", "/member/")


def unlinked_text():
    lines = ["你的 LINE 還沒有和網站帳號連動，連動後就能在這裡查詢行程。"]
    if PUBLIC_BASE_URL:
        lines += ["", f"還沒有帳號：用 LINE 登入註冊 {PUBLIC_BASE_URL}/auth/line/login",
                  f"已經有帳號：登入後到個人資料頁按「綁定 LINE」 {PUBLIC_BASE_URL}/member/profile"]
    else:
        lines.append("請到網站使用「LINE 登入」，或登入後在個人資料頁按「綁定 LINE」。")
    return "\n".join(lines)


def _find_user(cursor, line_sub):
    cursor.execute(
        "SELECT user_id, nickname, full_name FROM users WHERE line_sub=%s AND status='active' LIMIT 1",
        (line_sub,),
    )
    return cursor.fetchone()


def _upcoming_trips(cursor, user_id, limit):
    cursor.execute(
        """
        SELECT t.trip_id, t.trip_name, t.start_date, t.end_date, t.cover_image_path,
               co.name AS country, ci.name AS city
        FROM trips t
        JOIN trip_members tm ON tm.trip_id=t.trip_id AND tm.user_id=%s AND tm.join_status='accepted'
        JOIN countries co ON co.country_id=t.country_id
        JOIN cities ci ON ci.city_id=t.city_id
        WHERE t.deleted_at IS NULL AND t.status <> 'cancelled' AND t.end_date >= %s
        ORDER BY t.start_date, t.trip_id LIMIT %s
        """,
        (user_id, date.today(), limit),
    )
    return cursor.fetchall()


def _notice_card(alt_text, kicker, title, message, buttons):  # 沒有資料時的簡單卡片
    return flex.flex_message(alt_text, flex.bubble(
        flex.header(kicker, title), [flex.text(message, size="sm", color=flex.MUTED)], buttons, size="kilo"))


def _countdown(trip, today):  # 回傳（倒數文字, 要顯示哪一天的安排, 該天的標題）
    if trip["start_date"] <= today:
        return f"旅程進行中・第 {(today - trip['start_date']).days + 1} 天", today, "今天的安排"
    days_left = (trip["start_date"] - today).days
    return ("明天就要出發囉！" if days_left == 1 else f"還有 {days_left} 天出發"), trip["start_date"], "第一天安排"


def next_trip_card(cursor, user_id):
    trips = _upcoming_trips(cursor, user_id, 1)
    if not trips:
        return _notice_card("目前沒有即將出發的行程", "下一趟旅程", "還沒有行程", "要不要揪團規劃下一趟旅程？",
                            [flex.uri_button("建立行程", "/member/trips/new")])
    trip = trips[0]
    countdown, show_date, show_label = _countdown(trip, date.today())
    cursor.execute(
        "SELECT title,start_time,is_all_day FROM itineraries WHERE trip_id=%s AND itinerary_date=%s "
        "ORDER BY is_all_day DESC,start_time IS NULL,start_time,sort_order",
        (trip["trip_id"], show_date),
    )
    items = cursor.fetchall()
    body = [
        flex.info_row("日期", _period(trip)),
        flex.info_row("地點", f"{trip['country']} {trip['city']}"),
    ]
    forecast = weather.get_day_forecast(trip["city"], show_date)  # 出發日（旅程中則是今天）的天氣；國外城市或超過一週查不到
    if forecast:
        body.append(flex.info_row("天氣", weather.describe_forecast(forecast)))
        body += [flex.text(tip, size="xs", color="#8A6200") for tip in weather.travel_tips(forecast)]
    body += [
        flex.separator(),
        flex.text(show_label, size="sm", weight="bold", color=flex.PRIMARY_DEEP, margin="lg"),
    ]
    if items:
        for item in items[:LIST_LIMIT]:
            time_text = format_hm(item["start_time"]) if item["start_time"] and not item["is_all_day"] else "全天"
            body.append(flex.box("baseline", [
                flex.text(time_text, size="sm", color=flex.PRIMARY, weight="bold", flex=2),
                flex.text(item["title"], size="sm", color=flex.INK, flex=6),
            ], spacing="sm"))
        if len(items) > LIST_LIMIT:
            body.append(flex.text(f"…還有 {len(items) - LIST_LIMIT} 項", size="xs", color=flex.MUTED))
    else:
        body.append(flex.text("還沒有安排行程項目", size="sm", color=flex.MUTED))
    card = flex.bubble(
        flex.header(f"🧳 {countdown}", trip["trip_name"]), body,
        [flex.uri_button("查看行程", f"/member/trips/{trip['trip_id']}"), flex.message_button("看待辦事項", TODO)],
        hero_url=flex.image_url(trip.get("cover_image_path")),
    )
    return flex.flex_message(f"{countdown}：{trip['trip_name']}（{_period(trip)}）", card)


def my_trips_card(cursor, user_id):
    trips = _upcoming_trips(cursor, user_id, LIST_LIMIT)
    if not trips:
        return _notice_card("目前沒有即將出發的行程", "我的行程", "還沒有行程", "目前沒有即將出發的行程。",
                            [flex.uri_button("建立行程", "/member/trips/new")])
    today = date.today()
    bubbles = []
    for trip in trips:
        countdown = _countdown(trip, today)[0]
        bubbles.append(flex.bubble(
            flex.header(countdown, trip["trip_name"]),
            [flex.info_row("日期", _period(trip)), flex.info_row("地點", f"{trip['country']} {trip['city']}")],
            [flex.uri_button("查看行程", f"/member/trips/{trip['trip_id']}")],
            hero_url=flex.image_url(trip.get("cover_image_path")), size="kilo",
        ))
    names = "、".join(trip["trip_name"] for trip in trips)
    return flex.flex_message(f"即將出發的行程：{names}", flex.carousel(bubbles))


def todo_card(cursor, user_id):
    cursor.execute(
        """
        SELECT v.title,v.deadline_at,t.trip_id,t.trip_name FROM votes v
        JOIN trips t ON t.trip_id=v.trip_id AND t.deleted_at IS NULL
        JOIN trip_members tm ON tm.trip_id=v.trip_id AND tm.user_id=%s AND tm.join_status='accepted'
        WHERE v.status='open' AND v.deadline_at>%s
          AND NOT EXISTS (SELECT 1 FROM vote_records r WHERE r.vote_id=v.vote_id AND r.user_id=%s)
        ORDER BY v.deadline_at
        """,
        (user_id, datetime.now(), user_id),
    )
    votes = cursor.fetchall()
    cursor.execute(
        """
        SELECT e.expense_name,e.currency,s.split_amount,t.trip_name,
               COALESCE(NULLIF(p.nickname,''),p.full_name) AS payer_name
        FROM expense_splits s JOIN expenses e ON e.expense_id=s.expense_id
        JOIN trips t ON t.trip_id=e.trip_id AND t.deleted_at IS NULL
        JOIN users p ON p.user_id=e.payer_id
        WHERE s.user_id=%s AND s.settlement_status='unpaid' AND e.payer_id<>%s
        ORDER BY e.expense_date,e.expense_id
        """,
        (user_id, user_id),
    )
    splits = cursor.fetchall()
    if not votes and not splits:
        return _notice_card("目前沒有待辦事項", "待辦事項", "✅ 都處理完了", "目前沒有待辦事項，可以安心等出發！",
                            [flex.message_button("看下一趟旅程", NEXT_TRIP)])

    def section(title, rows, total):
        contents = [flex.text(title, size="sm", weight="bold", color=flex.PRIMARY_DEEP)] + rows
        if total > LIST_LIMIT:
            contents.append(flex.text(f"…還有 {total - LIST_LIMIT} 項", size="xs", color=flex.MUTED))
        return flex.box("vertical", contents, spacing="sm")

    body = []
    if votes:
        body.append(section(f"🗳️ 還沒投票（{len(votes)}）", [
            flex.box("vertical", [
                flex.text(vote["title"], size="sm", color=flex.INK, weight="bold"),
                flex.text(f"{vote['trip_name']}・{vote['deadline_at'].strftime('%m/%d %H:%M')} 截止", size="xs", color=flex.MUTED),
            ]) for vote in votes[:LIST_LIMIT]], len(votes)))
    if splits:
        if body:
            body.append(flex.separator())
        body.append(section(f"💰 還沒付的分帳（{len(splits)}）", [
            flex.box("horizontal", [
                flex.box("vertical", [
                    flex.text(split["expense_name"], size="sm", color=flex.INK, weight="bold"),
                    flex.text(f"{split['trip_name']}・付給 {split['payer_name']}", size="xs", color=flex.MUTED),
                ], flex=5),
                flex.text(f"{split['currency']} {split['split_amount']:,.0f}", size="sm", color=flex.INK,
                          weight="bold", align="end", gravity="center", flex=3),
            ]) for split in splits[:LIST_LIMIT]], len(splits)))
    parts = [f"{len(votes)} 個投票" if votes else "", f"{len(splits)} 筆分帳" if splits else ""]
    summary = "、".join(part for part in parts if part)
    card = flex.bubble(flex.header("📋 待辦事項", f"還有 {summary}待處理", color=flex.PRIMARY_DEEP), body,
                       [flex.uri_button("到網站處理", "/member/")])
    return flex.flex_message(f"待辦事項：{summary}待處理", card)


def unknown_text():  # 看不懂的訊息（或貼圖、圖片）給的提示，搭配快速回覆按鈕使用
    return (
        "抱歉，我還看不懂這則訊息 🙇\n"
        "可以點下方按鈕，或輸入：\n"
        f"・{NEXT_TRIP}\n・{TODO}\n・{MY_TRIPS}"
    )


# 句子裡有包含關鍵字也算（例如「我想看下一趟旅程」），先比對較長的詞，避免被短詞搶先
_KEYWORDS = sorted([(word, word) for word in COMMANDS] + list(ALIASES.items()), key=lambda pair: -len(pair[0]))


def normalize(text):
    text = (text or "").strip()
    if text in COMMANDS:
        return text
    if text.lower() in ALIASES:
        return ALIASES[text.lower()]
    lowered = text.lower()
    for word, command in _KEYWORDS:
        if word.lower() in lowered:
            return command
    return None


def reply_for(line_sub, text):  # 回傳文字（str）或卡片訊息（dict），交給 line_messaging.reply_message 送出
    command = normalize(text)
    if command is None:
        return unknown_text()
    if command == HELP:
        return help_text()
    connection = get_db_connection()
    if connection is None:
        return "系統暫時無法查詢，請稍後再試。"
    cursor = connection.cursor(dictionary=True)
    try:
        user = _find_user(cursor, line_sub)
        if user is None:
            return unlinked_text()
        if command == NEXT_TRIP:
            return next_trip_card(cursor, user["user_id"])
        if command == TODO:
            return todo_card(cursor, user["user_id"])
        return my_trips_card(cursor, user["user_id"])
    except Error as error:
        print("LINE 關鍵字查詢失敗：", error)
        return "系統暫時無法查詢，請稍後再試。"
    finally:
        cursor.close()
        connection.close()
