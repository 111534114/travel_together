"""智慧排程、交通估算、附近住宿與預算估算。

規則計算（不需要 AI）負責保底：依座標排出順路的順序、估算每段交通方式／時間／費用、排出建議時間。
有設定 AI 時，再請 AI 依營業時間、用餐時段與南北向動線微調順序；AI 失敗就用規則結果，不會卡住。
所有金額以新臺幣（TWD）計，資料庫的票價、每晚房價也是新臺幣。
"""

from datetime import date, time
from math import asin, ceil, cos, isfinite, radians, sin, sqrt
import re

from ai_client import AIUnavailable, ai_ready, ask_json

DAY_START_MINUTES = 9 * 60
DEFAULT_DURATIONS = {"attraction": 90, "restaurant": 60, "shopping": 60, "amusement_park": 360,
                     "meeting": 15, "transport": 30, "free_time": 60, "accommodation": 0, "other": 60}
MEAL_TARGETS = [12 * 60, 18 * 60 + 30, 15 * 60]
MEAL_PER_PERSON = {"low": 200, "medium": 500, "high": 1200, "luxury": 3000}
DEFAULT_MEAL_PER_PERSON = 400
LODGING_TIERS = {"budget": ("平價", 1800), "mid": ("中價位", 3500), "high": ("高價位", 7000)}
WEEKDAYS = "一二三四五六日"


# ---------- 距離與交通估算 ----------

def coordinates(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (isfinite(lat) and isfinite(lng)) or not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        return None
    return lat, lng


def distance_km(first, second):
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    arc = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * asin(min(1, sqrt(arc)))


def distance_label(km):
    return f"約 {max(10, round(km * 100) * 10):.0f} 公尺" if km < 1 else f"約 {km:.1f} 公里"


def estimate_leg(km):
    """依直線距離估算交通方式、時間（分鐘）與每人費用（新臺幣）。實際路程通常比直線遠，已乘上繞路係數。"""
    road_km = km * 1.3
    if km < 1.0:
        method, minutes, cost = "步行", ceil(road_km / 4.5 * 60) + 2, 0
    elif km < 20:
        method, minutes, cost = "大眾運輸（捷運／公車）", round(10 + road_km / 22 * 60), round(20 + road_km * 2)
    elif km < 80:
        method, minutes, cost = "開車／計程車", round(10 + road_km / 45 * 60), round(road_km * 10)
    else:
        method, minutes, cost = "長途交通（高鐵／火車）", round(30 + road_km / 120 * 60), round(road_km * 3.5)
    return {"method": method, "minutes": max(3, minutes), "cost": cost,
            "distance_km": round(km, 2), "distance_label": distance_label(km), "estimated_by": "rule"}


# ---------- 排序 ----------

def _route_length(points):
    return sum(distance_km(points[i], points[i + 1]) for i in range(len(points) - 1))


def _nearest_neighbor(start, items):
    remaining = list(items)
    route, current = [], start
    while remaining:
        nxt = min(remaining, key=lambda it: distance_km(current, it["coords"]))
        route.append(nxt)
        remaining.remove(nxt)
        current = nxt["coords"]
    return route


def _two_opt(start, route):
    """反轉路線中的片段，消除交叉，縮短總距離（起點固定、終點開放）。"""
    improved = True
    while improved and len(route) > 2:
        improved = False
        for i in range(len(route) - 1):
            for j in range(i + 1, len(route)):
                candidate = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                points_old = ([start] if start else []) + [it["coords"] for it in route]
                points_new = ([start] if start else []) + [it["coords"] for it in candidate]
                if _route_length(points_new) + 1e-9 < _route_length(points_old):
                    route, improved = candidate, True
    return route


def _duration(item):
    if item.get("duration"):
        return int(item["duration"])
    return DEFAULT_DURATIONS.get(item.get("item_type"), 60)


def opening_minutes(opening_hours):
    """從營業時間文字（例如「17:00-24:00」「週一至週日 09:00–17:00」）取出開門時間（分鐘）。"""
    match = re.search(r"([01]?\d|2[0-3])[:：]([0-5]\d)", str(opening_hours or ""))
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def _earliest_start(item):
    """這一站最早可以開始的時間：開門時間、或使用者原本排的時間（例如夜市排在晚上），取較晚者。"""
    candidates = [opening_minutes(item.get("opening_hours"))]
    original = item.get("start_time")
    if isinstance(original, time):
        candidates.append(original.hour * 60 + original.minute)
    candidates = [c for c in candidates if c is not None]
    return max(candidates) if candidates else None


def schedule(ordered, day_start=DAY_START_MINUTES):
    """依順序計算每一站的交通（與前一站）與建議開始時間；不會早於開門時間或原本排定的時間。"""
    rows, clock, previous = [], day_start, None
    for index, item in enumerate(ordered):
        leg = None
        if index > 0:
            if previous.get("coords") and item.get("coords"):
                leg = estimate_leg(distance_km(previous["coords"], item["coords"]))
                clock += leg["minutes"]
            else:
                clock += 15
        earliest = _earliest_start(item)
        if earliest is not None and earliest > clock:
            clock = earliest
        rows.append({**item, "leg": leg, "start_minutes": None if item.get("is_all_day") else clock})
        clock += _duration(item)
        previous = item
    return rows


def _insert_meals(start, route, restaurants, day_start):
    """把餐廳插進路線中「離用餐時段最近、又不會繞太遠」的位置。"""
    for meal_index, restaurant in enumerate(restaurants):
        target = MEAL_TARGETS[meal_index % len(MEAL_TARGETS)]
        best, best_cost = None, None
        for position in range(len(route) + 1):
            candidate = route[:position] + [restaurant] + route[position:]
            timeline = schedule(([{"coords": start, "item_type": "meeting", "duration": 0}] if start else []) + candidate, day_start)
            arrival = next(row["start_minutes"] for row in timeline if row is not None and row.get("itinerary_id") == restaurant["itinerary_id"])
            points = ([start] if start else []) + [it["coords"] for it in candidate if it.get("coords")]
            cost = _route_length(points) * 2 + abs(arrival - target) / 20
            if best_cost is None or cost < best_cost:
                best, best_cost = candidate, cost
        route = best
    return route


def plan_day_route(items, day_start=DAY_START_MINUTES):
    """規則排程：住宿（退房）固定在最前、晚上入住的住宿放最後；有座標的站點依最近距離排序並消除交叉，
    餐廳插在午餐／晚餐時段附近；沒有座標的站點保持原本相對順序放在後面。"""
    items = [dict(it, coords=coordinates(it.get("lat"), it.get("lng"))) for it in items]
    head, tail, movable = [], [], []
    for index, item in enumerate(items):
        if item.get("item_type") == "accommodation":
            (head if index == 0 and len(items) > 1 else tail).append(item)
        else:
            movable.append(item)
    geo = [it for it in movable if it["coords"] and it.get("item_type") != "restaurant"]
    meals = [it for it in movable if it["coords"] and it.get("item_type") == "restaurant"]
    no_geo = [it for it in movable if not it["coords"]]
    start = head[0]["coords"] if head and head[0]["coords"] else None
    if geo:
        if start is None:
            first = geo[0]
            route = [first] + _two_opt(first["coords"], _nearest_neighbor(first["coords"], geo[1:]))
        else:
            route = _two_opt(start, _nearest_neighbor(start, geo))
    else:
        route = []
    route = _insert_meals(start, route, meals, day_start) if meals else route
    return head + route + no_geo + tail


# ---------- AI 微調 ----------

def _hhmm_to_minutes(value):
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", str(value or "").strip())
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def minutes_to_hhmm(minutes):
    if minutes is None:
        return ""
    minutes = max(0, min(int(minutes), 23 * 60 + 59))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def ai_refine_day(items, baseline, itinerary_date, city):
    """請 AI 依營業時間、用餐時段與動線調整順序。回傳 (排序後的項目, 每站 AI 時間 dict, 說明, 小提醒)。"""
    by_id = {it["itinerary_id"]: it for it in items}
    lines = []
    for it in items:
        coords = coordinates(it.get("lat"), it.get("lng"))
        lines.append({
            "id": it["itinerary_id"], "type": it.get("item_type"), "title": it.get("title"),
            "opening_hours": it.get("opening_hours") or "", "stay_minutes": _duration(it),
            "lat": round(coords[0], 5) if coords else None, "lng": round(coords[1], 5) if coords else None,
            "address": it.get("address") or "",
        })
    weekday = WEEKDAYS[itinerary_date.weekday()] if isinstance(itinerary_date, date) else ""
    prompt = (
        "你是旅遊動線規劃助手，所有文字使用繁體中文。只回傳 JSON 物件，不要 Markdown。\n"
        f"目的地：{city}。日期：{itinerary_date}（週{weekday}）。\n"
        "請重新排列以下同一天的行程站點，讓動線順路（避免來回折返，可依南北或東西方向一路走）、"
        "配合營業時間、午餐約 11:30–13:30、晚餐約 17:30–19:30 安排在餐廳，熱門景點盡量避開人潮尖峰。"
        "住宿若是當天退房放最前面、入住放最後面。不可新增或刪除站點，每個 id 都要出現一次。\n"
        f"站點：{lines}\n"
        f"系統依距離算出的參考順序：{[it['itinerary_id'] for it in baseline]}\n"
        '回傳格式：{"order":[id,...],"start_times":{"id":"HH:MM"},'
        '"legs":{"id":{"method":"到這一站的交通方式","minutes":整數}},'
        '"reason":"一到兩句說明為什麼這樣排","tips":["最多三則提醒，例如營業時間或人潮"]}。'
        "legs 只需要填沒有經緯度的站點；不確定的時間請合理估算，不要捏造即時班次或價格。"
    )
    payload = ask_json(prompt)
    order = payload.get("order")
    try:
        order = [int(x) for x in order]
    except (TypeError, ValueError) as error:
        raise AIUnavailable("AI 回傳的順序格式不正確。") from error
    if sorted(order) != sorted(by_id):
        raise AIUnavailable("AI 回傳的順序和行程站點不一致。")
    times = {}
    for key, value in (payload.get("start_times") or {}).items():
        minutes = _hhmm_to_minutes(value)
        if str(key).isdigit() and int(key) in by_id and minutes is not None:
            times[int(key)] = minutes
    legs = {}
    for key, value in (payload.get("legs") or {}).items():
        if not (str(key).isdigit() and int(key) in by_id and isinstance(value, dict)):
            continue
        try:
            minutes = int(value.get("minutes"))
        except (TypeError, ValueError):
            continue
        method = str(value.get("method") or "").strip()[:60]
        if method and 0 < minutes <= 600:
            legs[int(key)] = {"method": method, "minutes": minutes, "cost": None,
                              "distance_km": None, "distance_label": "", "estimated_by": "ai"}
    tips = [str(tip).strip()[:120] for tip in (payload.get("tips") or []) if str(tip).strip()][:3]
    return [by_id[i] for i in order], times, str(payload.get("reason") or "").strip()[:300], legs, tips


def smart_schedule_day(items, itinerary_date, city, use_ai=True):
    """排一天的行程，回傳預覽資料。items 需含 itinerary_id、item_type、title、lat、lng、duration、opening_hours、
    start_time（time 或 None）、is_all_day。"""
    if not items:
        return {"items": [], "source": "rule", "reason": "", "tips": [], "changed": False}
    first_start = items[0].get("start_time")
    day_start = DAY_START_MINUTES
    if isinstance(first_start, time):
        day_start = first_start.hour * 60 + first_start.minute
    baseline = plan_day_route(items, day_start)
    ordered, source, reason, ai_times, ai_legs, tips = baseline, "rule", "", {}, {}, []
    note = ""
    if use_ai and ai_ready() and len(items) > 1:
        try:
            ordered, ai_times, reason, ai_legs, tips = ai_refine_day(items, baseline, itinerary_date, city)
            source = "ai"
        except AIUnavailable as error:
            note = f"AI 暫時無法使用（{error}），先用距離規則排序。"
    ordered = [dict(it, coords=coordinates(it.get("lat"), it.get("lng"))) for it in ordered]
    timeline = schedule(ordered, day_start)
    previous_minutes = -1
    for row in timeline:
        if row["leg"] is None and row["itinerary_id"] in ai_legs:
            row["leg"] = ai_legs[row["itinerary_id"]]
        ai_minutes = ai_times.get(row["itinerary_id"])
        if row["start_minutes"] is not None and ai_minutes is not None and ai_minutes >= previous_minutes:
            row["start_minutes"] = ai_minutes
        if row["start_minutes"] is not None:
            previous_minutes = row["start_minutes"]
    if not reason:
        reason = "依各站之間的距離排出最順路的順序，餐廳安排在午餐、晚餐時段附近。"
    original_ids = [it["itinerary_id"] for it in items]
    result_items = [{
        "itinerary_id": row["itinerary_id"], "title": row.get("title"), "item_type": row.get("item_type"),
        "start_time": minutes_to_hhmm(row["start_minutes"]), "is_all_day": bool(row.get("is_all_day")),
        "has_coords": bool(row.get("coords")),
        "leg": row["leg"],
    } for row in timeline]
    return {"items": result_items, "source": source, "reason": reason, "tips": tips, "note": note,
            "changed": [r["itinerary_id"] for r in result_items] != original_ids}


# ---------- 附近住宿 ----------

def find_nearby_accommodations(cursor, origin, country_id, radius_km=5, limit=6):
    """依座標找附近的住宿；半徑內找不到時會放寬到 15 公里。"""
    origin = coordinates(*origin) if origin else None
    if origin is None:
        return []
    for radius in (radius_km, 15):
        lat, lng = origin
        lat_span = radius / 110
        lng_span = min(180, radius / (110 * max(abs(cos(radians(lat))), 0.01)))
        cursor.execute("""
            SELECT accommodation_id, name, address, accommodation_type, price_per_night,
                   image_path, latitude, longitude, check_in_time
            FROM accommodations
            WHERE country_id=%s AND status='active' AND deleted_at IS NULL
              AND latitude BETWEEN %s AND %s AND longitude BETWEEN %s AND %s
        """, (country_id, lat - lat_span, lat + lat_span, lng - lng_span, lng + lng_span))
        found = []
        for row in cursor.fetchall():
            coords = coordinates(row["latitude"], row["longitude"])
            if not coords:
                continue
            km = distance_km(origin, coords)
            if km <= radius:
                row["distance_km"] = km
                row["distance_label"] = distance_label(km)
                found.append(row)
        if found:
            found.sort(key=lambda r: (r["distance_km"], r["accommodation_id"]))
            return found[:limit]
    return []


# ---------- 預算估算 ----------

def estimate_budget(itinerary, people, nights, lodging_prices, tier="mid"):
    """依已排入的行程估算預算（新臺幣）。

    itinerary：行程項目，需含 item_type、estimated_cost、ticket_price、price_level、price_per_night、
              lat、lng、itinerary_date、accommodation_id。
    lodging_prices：每晚的住宿單價（已排入或推薦住宿的房價），沒有的晚上用 tier 參考價。
    """
    people = max(1, int(people or 1))
    rooms = ceil(people / 2)
    tier_label, tier_price = LODGING_TIERS.get(tier, LODGING_TIERS["mid"])
    tickets = meals = transport = other = 0.0
    notes = []
    previous_by_day = {}
    for item in itinerary:
        cost = float(item.get("estimated_cost") or 0)
        kind = item.get("item_type")
        if kind == "accommodation":
            continue
        if kind == "attraction" or kind == "amusement_park":
            tickets += cost if cost else float(item.get("ticket_price") or 0) * people
        elif kind == "restaurant":
            meals += cost if cost else MEAL_PER_PERSON.get(item.get("price_level"), DEFAULT_MEAL_PER_PERSON) * people
        elif kind == "transport":
            transport += cost
        else:
            other += cost
        day = item.get("itinerary_date")
        coords = coordinates(item.get("lat"), item.get("lng"))
        if coords:
            prev = previous_by_day.get(day)
            if prev:
                transport += estimate_leg(distance_km(prev, coords))["cost"] * people
            previous_by_day[day] = coords
    lodging = 0.0
    reference_nights = 0
    for night in range(nights):
        price = lodging_prices[night] if night < len(lodging_prices) else None
        if price:
            lodging += float(price) * rooms
        else:
            lodging += tier_price * rooms
            reference_nights += 1
    if reference_nights:
        notes.append(f"有 {reference_nights} 晚沒有房價資料，以{tier_label}每房每晚約 NT$ {tier_price:,} 估算。")
    meal_days = len({item.get("itinerary_date") for item in itinerary}) or max(nights, 1)
    restaurant_count = sum(1 for item in itinerary if item.get("item_type") == "restaurant")
    if restaurant_count < meal_days * 2:
        missing = meal_days * 2 - restaurant_count
        meals += missing * DEFAULT_MEAL_PER_PERSON * people
        notes.append(f"另有約 {missing} 餐尚未安排餐廳，以每人每餐 NT$ {DEFAULT_MEAL_PER_PERSON} 估算。")
    lines = [
        {"key": "lodging", "label": f"住宿（{nights} 晚 × {rooms} 間）", "amount": round(lodging)},
        {"key": "tickets", "label": "景點門票", "amount": round(tickets)},
        {"key": "meals", "label": "餐飲", "amount": round(meals)},
        {"key": "transport", "label": "當地交通", "amount": round(transport)},
        {"key": "other", "label": "其他", "amount": round(other)},
    ]
    total = sum(line["amount"] for line in lines)
    return {"lines": lines, "total": total, "per_person": round(total / people), "people": people,
            "rooms": rooms, "nights": nights, "tier": tier, "tier_label": tier_label, "notes": notes}
