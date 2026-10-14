"""Keyword replies for the LINE official account."""

from datetime import date, datetime

from mysql.connector import Error

from config import PUBLIC_BASE_URL
from db import get_db_connection
from utils import format_hm


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
        SELECT t.trip_id, t.trip_name, t.start_date, t.end_date, co.name AS country, ci.name AS city
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


def next_trip_text(cursor, user_id):
    trips = _upcoming_trips(cursor, user_id, 1)
    if not trips:
        return _with_link(["目前沒有即將出發的行程。", "要不要揪團規劃下一趟旅程？"], "建立行程", "/member/trips/new")
    trip = trips[0]
    today = date.today()
    if trip["start_date"] <= today:
        heading = f"🧳 旅程進行中・第 {(today - trip['start_date']).days + 1} 天"
        show_date, show_label = today, "今天的安排"
    else:
        days_left = (trip["start_date"] - today).days
        heading = "🧳 明天就要出發囉！" if days_left == 1 else f"🧳 還有 {days_left} 天出發"
        show_date, show_label = trip["start_date"], "第一天安排"
    cursor.execute(
        "SELECT title,start_time,is_all_day FROM itineraries WHERE trip_id=%s AND itinerary_date=%s "
        "ORDER BY is_all_day DESC,start_time IS NULL,start_time,sort_order",
        (trip["trip_id"], show_date),
    )
    items = cursor.fetchall()
    lines = [heading, "", f"行程：{trip['trip_name']}", f"日期：{_period(trip)}", f"地點：{trip['country']} {trip['city']}"]
    if items:
        lines += ["", f"{show_label}："]
        for item in items[:LIST_LIMIT]:
            time_text = format_hm(item["start_time"]) if item["start_time"] and not item["is_all_day"] else "全天"
            lines.append(f"・{time_text} {item['title']}")
        if len(items) > LIST_LIMIT:
            lines.append(f"…還有 {len(items) - LIST_LIMIT} 項")
    else:
        lines += ["", f"{show_label}：還沒有安排行程項目"]
    return _with_link(lines, "查看行程", f"/member/trips/{trip['trip_id']}")


def my_trips_text(cursor, user_id):
    trips = _upcoming_trips(cursor, user_id, LIST_LIMIT + 1)
    if not trips:
        return _with_link(["目前沒有即將出發的行程。"], "建立行程", "/member/trips/new")
    lines = ["🗓️ 即將出發的行程", ""]
    for index, trip in enumerate(trips[:LIST_LIMIT], 1):
        lines += [f"{index}. {trip['trip_name']}", f"   {_period(trip)}・{trip['city']}"]
    if len(trips) > LIST_LIMIT:
        lines.append("…還有更多行程")
    return _with_link(lines, "查看全部", "/member/")


def todo_text(cursor, user_id):
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
        return "✅ 目前沒有待辦事項，可以安心等出發！"
    lines = ["📋 你的待辦事項"]
    if votes:
        lines += ["", f"🗳️ 還沒投票（{len(votes)}）"]
        for vote in votes[:LIST_LIMIT]:
            lines.append(f"・{vote['trip_name']}｜{vote['title']}（{vote['deadline_at'].strftime('%m/%d %H:%M')} 截止）")
    if splits:
        lines += ["", f"💰 還沒付的分帳（{len(splits)}）"]
        for split in splits[:LIST_LIMIT]:
            lines.append(f"・{split['trip_name']}｜{split['expense_name']}：付給 {split['payer_name']} {split['currency']} {split['split_amount']:,.0f}")
    return _with_link(lines, "到網站處理", "/member/")


def normalize(text):
    text = (text or "").strip()
    return text if text in COMMANDS else ALIASES.get(text.lower())


def reply_for(line_sub, text):
    command = normalize(text)
    if command is None:
        return None
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
            return next_trip_text(cursor, user["user_id"])
        if command == TODO:
            return todo_text(cursor, user["user_id"])
        return my_trips_text(cursor, user["user_id"])
    except Error as error:
        print("LINE 關鍵字查詢失敗：", error)
        return "系統暫時無法查詢，請稍後再試。"
    finally:
        cursor.close()
        connection.close()
