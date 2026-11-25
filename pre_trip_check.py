"""出發前檢查：出發前 3 天、前 1 天自動檢查行程，行程頁也能隨時看。

全部用規則判斷(不用 AI)，快、免費、結果固定：
- 🌧️ 天氣：降雨、太熱太冷、氣象署特報、颱風(只有台灣縣市、未來一週)
- 🕒 營業時間：排到公休日、不在營業時間內(看得懂 Google 地點的格式才檢查)
- 🏨 住宿：哪幾晚行程裡沒有住宿
- ⏱️ 行程太趕：時間重疊、一天排太滿、兩個地方很遠卻沒寫交通方式
- 💰 預算：行程預估花費超過總預算
- 📅 日期：有項目排在旅程期間以外

每個問題都附一句「請助理幫忙」用的提問，行程頁點了就交給行程助理。
"""

import re
from datetime import date, timedelta

import smart_trip
import weather
from trip_assistant import load_items

WEEKDAY_NAMES = "一二三四五六日"
DAY_LIMIT_MINUTES = 12 * 60  # 一天排超過 12 小時就提醒太滿
FAR_KM = 15  # 兩個連續地點超過這個距離、又沒寫交通方式就提醒
WEATHER_DAYS = 7  # 氣象署只有一週內的預報
LEVEL_ORDER = {"danger": 0, "warn": 1, "info": 2}
KIND_ICONS = {"weather": "🌧️", "hours": "🕒", "lodging": "🏨", "schedule": "⏱️", "budget": "💰", "date": "📅"}

_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[–\-~～至到]\s*(\d{1,2}):(\d{2})")
_DAY_PART = re.compile(r"星期([一二三四五六日天])\s*[:：]\s*(.*)")


# ---------- 營業時間 ----------

def parse_opening_hours(text):
    """把營業時間文字變成 {星期幾(0=週一): "closed" 或 [(開始分鐘, 結束分鐘), ...]}。

    看得懂 Google 地點的格式(「星期一: 休息；星期二: 09:00 – 17:30」「24 小時營業」「11:30 – 14:30, 17:00 – 00:00」)，
    也看得懂沒寫星期幾的「11:00 – 21:00」(每天都一樣)。看不懂、或文字被截斷的那天就不放進結果(不檢查)。
    """
    text = (text or "").strip()
    if not text:
        return {}
    result = {}
    parts = [part.strip() for part in re.split(r"[；;\n]", text) if part.strip()]
    has_weekdays = any(_DAY_PART.match(part) for part in parts)
    if not has_weekdays:
        ranges = _ranges(text)
        return {day: ranges for day in range(7)} if ranges else {}
    for part in parts:
        match = _DAY_PART.match(part)
        if not match:
            continue
        day = WEEKDAY_NAMES.index(match.group(1)) if match.group(1) in WEEKDAY_NAMES else 6
        value = match.group(2)
        if "休息" in value or "公休" in value or "不營業" in value:
            result[day] = "closed"
        elif "24 小時" in value or "24小時" in value:
            result[day] = [(0, 24 * 60)]
        else:
            ranges = _ranges(value)
            if ranges:
                result[day] = ranges
    return result


def _ranges(text):
    ranges = []
    for h1, m1, h2, m2 in _RANGE.findall(text):
        start, end = int(h1) * 60 + int(m1), int(h2) * 60 + int(m2)
        if end <= start:  # 「17:00 – 00:00」「22:00 – 02:00」營業到半夜
            end += 24 * 60
        ranges.append((start, end))
    return ranges


def _minutes(value):
    if value is None:
        return None
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60)
    text = str(value)
    if len(text) >= 5 and text[2] == ":":
        return int(text[:2]) * 60 + int(text[3:5])
    return None


def _hm(minutes):
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _duration(item):
    start, end = _minutes(item["start_time"]), _minutes(item["end_time"])
    if start is not None and end is not None and end > start:
        return end - start
    return smart_trip.DEFAULT_DURATIONS.get(item["item_type"], 60)


# ---------- 小工具 ----------

def _day(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def day_text(value):
    day = _day(value)
    return f"{day.month}/{day.day}（{WEEKDAY_NAMES[day.weekday()]}）"


def _span(days):
    """[(日期, 溫度), ...] → 「11/28（六）～12/1（二）」或「11/28（六）」。"""
    first, last = days[0][0], days[-1][0]
    return day_text(first) if first == last else f"{day_text(first)}～{day_text(last)}"


def _issue(kind, level, text, ask=None, day=None):
    return {"kind": kind, "icon": KIND_ICONS[kind], "level": level, "text": text, "ask": ask,
            "date": str(day) if day else None}


# ---------- 各項檢查 ----------

def check_dates(trip, items):
    start, end = _day(trip["start_date"]), _day(trip["end_date"])
    issues = []
    for item in items:
        day = _day(item["itinerary_date"])
        if day < start or day > end:
            issues.append(_issue(
                "date", "danger", f"「{item['title']}」排在 {day_text(day)}，不在旅程期間（{day_text(start)}～{day_text(end)}）內",
                f"「{item['title']}」排在旅程期間以外的 {day}，幫我移到旅程期間內適合的一天", day))
    return issues


def check_weather(trip, items, today):
    city = trip.get("city")
    if not city or not weather.is_configured():
        return []
    issues = []
    hot_days, cool_days = [], []  # 太熱、太冷的日子合併成一句，不要每天各一條
    start, end = _day(trip["start_date"]), _day(trip["end_date"])
    day = max(start, today)
    while day <= end and (day - today).days < WEATHER_DAYS:
        forecast = weather.get_day_forecast(city, day)
        if forecast:
            rain, high, low = forecast.get("rain"), forecast.get("max"), forecast.get("min")
            if rain is not None and rain >= weather.RAINY_PERCENT:
                outdoor = any(_day(i["itinerary_date"]) == day and i["item_type"] in ("attraction", "amusement_park") for i in items)
                issues.append(_issue(
                    "weather", "warn", f"{day_text(day)} 降雨機率 {rain}%，記得帶傘" + ("，戶外景點可以考慮換成室內的" if outdoor else ""),
                    f"{day} 降雨機率 {rain}%，幫我把那天的戶外景點換成室內的" if outdoor else None, day))
            if high is not None and high >= weather.HOT_CELSIUS:
                hot_days.append((day, high))
            if low is not None and low <= weather.COOL_CELSIUS:
                cool_days.append((day, low))
        for hazard in weather.get_city_warnings(city, day) or []:
            issues.append(_issue("weather", "danger", f"{day_text(day)} {weather.describe_warning(hazard)}",
                                 f"{day} 有{hazard.get('phenomena', '天氣')}特報，幫我調整那天的行程，避開危險的地方", day))
        day += timedelta(days=1)
    if hot_days:
        issues.append(_issue("weather", "info", f"{_span(hot_days)} 最高約 {max(t for _, t in hot_days)}°C，注意防曬、多喝水",
                             None, hot_days[0][0]))
    if cool_days:
        issues.append(_issue("weather", "info", f"{_span(cool_days)} 最低約 {min(t for _, t in cool_days)}°C，記得帶外套",
                             None, cool_days[0][0]))
    if weather.is_taiwan_city(city) and (start - today).days <= 3 and today <= end:
        typhoon = weather.get_typhoon_notice()
        if typhoon:
            issues.append(_issue("weather", "danger", f"🌀 {typhoon['headline']}：{typhoon['name']}，請留意交通與行程",
                                 "現在有颱風，幫我看看行程有哪些需要調整"))
    # 同一天的天氣提醒合併，避免警特報在每一天都重複出現
    seen, unique = set(), []
    for issue in issues:
        if issue["text"] not in seen:
            seen.add(issue["text"]); unique.append(issue)
    return unique


def check_opening_hours(items):
    issues = []
    for item in items:
        hours = parse_opening_hours(item.get("opening_hours"))
        if not hours or item["is_all_day"]:
            continue
        day = _day(item["itinerary_date"])
        today_hours = hours.get(day.weekday())
        if today_hours == "closed":
            issues.append(_issue("hours", "danger", f"「{item['title']}」{day_text(day)} 公休",
                                 f"「{item['title']}」在 {day} 公休，幫我換到它有開的日子，或換一個類似的地方", day))
            continue
        start = _minutes(item["start_time"])
        if not today_hours or start is None:
            continue
        end = start + _duration(item)
        if not any(open_at <= start and end <= close_at for open_at, close_at in today_hours):
            opening = "、".join(f"{_hm(a)}–{_hm(b)}" for a, b in today_hours)
            issues.append(_issue("hours", "warn", f"「{item['title']}」{day_text(day)} 營業時間是 {opening}，你排在 {_hm(start)}–{_hm(end)}",
                                 f"「{item['title']}」{day} 的營業時間是 {opening}，幫我把它調到營業時間內", day))
    return issues


def check_lodging(trip, items):
    start, end = _day(trip["start_date"]), _day(trip["end_date"])
    nights = (end - start).days
    booked = {_day(i["itinerary_date"]) for i in items if i["item_type"] == "accommodation"}
    missing = [start + timedelta(days=n) for n in range(nights) if start + timedelta(days=n) not in booked]
    if not missing:
        return []
    shown = "、".join(day_text(d) for d in missing[:4])
    text = f"{shown} 等共 {len(missing)} 晚還沒有安排住宿" if len(missing) > 4 else f"{shown} 晚上還沒有安排住宿"
    return [_issue("lodging", "warn", text,
                   f"{missing[0]} 晚上還沒有住宿，幫我在那天最後一個景點附近找住宿加進行程", missing[0])]


def check_schedule(items):
    issues = []
    by_day = {}
    for item in items:
        by_day.setdefault(_day(item["itinerary_date"]), []).append(item)
    for day, day_items in sorted(by_day.items()):
        timed = sorted((i for i in day_items if _minutes(i["start_time"]) is not None and not i["is_all_day"]),
                       key=lambda i: _minutes(i["start_time"]))
        for first, second in zip(timed, timed[1:]):
            first_end = _minutes(first["start_time"]) + _duration(first)
            if _minutes(second["start_time"]) < first_end:
                issues.append(_issue("schedule", "warn", f"{day_text(day)}「{first['title']}」和「{second['title']}」時間重疊",
                                     f"{day} 的「{first['title']}」和「{second['title']}」時間重疊，幫我重新排時間", day))
        busy = sum(_duration(i) + int(i.get("transport_minutes") or 0) for i in day_items if not i["is_all_day"])
        if busy > DAY_LIMIT_MINUTES:
            issues.append(_issue("schedule", "warn", f"{day_text(day)} 排了大約 {busy // 60} 小時，可能有點太滿",
                                 f"{day} 排太滿了，幫我排輕鬆一點", day))
        ordered = sorted(day_items, key=lambda i: i.get("sort_order") or 0)
        for first, second in zip(ordered, ordered[1:]):
            a = smart_trip.coordinates(first.get("lat"), first.get("lng"))
            b = smart_trip.coordinates(second.get("lat"), second.get("lng"))
            if a and b and not second.get("transport_method"):
                km = smart_trip.distance_km(a, b)
                if km >= FAR_KM:
                    issues.append(_issue("schedule", "info", f"{day_text(day)}「{first['title']}」到「{second['title']}」大約 {km:.0f} 公里，還沒寫交通方式",
                                         f"{day} 從「{first['title']}」到「{second['title']}」要怎麼去比較好？", day))
    return issues


def check_budget(trip, items):
    """行程項目的預估費用沒有記幣別(有的是行程幣別、有的是網站資料的新臺幣)，換算會不準，
    所以跟行程頁的預算比較一樣，只檢查用新臺幣的行程。"""
    budget = float(trip.get("total_budget") or 0)
    if budget <= 0 or (trip.get("currency") or "TWD").upper() != "TWD":
        return []
    planned = sum(float(i.get("estimated_cost") or 0) for i in items)
    if planned <= budget:
        return []
    return [_issue("budget", "warn", f"行程預估花費約 NT$ {planned:,.0f}，超過總預算 NT$ {budget:,.0f}",
                   "行程花費超過預算了，幫我找可以省錢的地方")]


def run_checks(cursor, trip, today=None):
    """回傳這趟行程的問題清單(依嚴重程度、日期排序)。trip 需要 trip_id、start_date、end_date、city、total_budget、currency。"""
    today = today or date.today()
    items = load_items(cursor, trip["trip_id"])
    issues = (check_dates(trip, items) + check_weather(trip, items, today) + check_opening_hours(items)
              + check_lodging(trip, items) + check_schedule(items) + check_budget(trip, items))
    issues.sort(key=lambda i: (LEVEL_ORDER[i["level"]], i["date"] or "", i["kind"]))
    return issues


def summary_lines(issues, limit=5):
    """給 LINE 卡片、網站通知用的幾行字。"""
    lines = [f"{issue['icon']} {issue['text']}" for issue in issues[:limit]]
    if len(issues) > limit:
        lines.append(f"…還有 {len(issues) - limit} 項，到行程頁看全部")
    return lines
