"""行程內「旅伴偏好」：每位成員在每趟行程填一份，並統計成團體偏好。

成員還沒填過這趟行程時，會先拿交友揪團的旅遊人格問卷（traveler_profiles）當預設值。
"""
from decimal import Decimal, InvalidOperation

from mysql.connector import Error

ACTIVITY_TAGS = ["觀光景點", "在地美食", "購物", "戶外活動", "文化體驗", "夜生活", "拍照打卡", "放鬆度假"]
DIET_LABELS = {"none": "不限", "vegetarian": "素食", "halal": "清真", "no_beef": "不吃牛", "no_seafood": "不吃海鮮", "other": "其他（請在特殊需求說明）"}
TRANSPORT_LABELS = {"any": "皆可", "public": "大眾運輸", "drive": "自行開車", "taxi": "計程車／叫車", "carpool": "共乘"}
WALK_LABELS = {"low": "低（盡量少走路）", "medium": "中", "high": "高（不介意多走）"}
INTENSITY_LABELS = {"relaxed": "輕鬆型", "standard": "標準型", "packed": "充實型", "family": "親子型", "senior_friendly": "長輩友善型"}

_TABLE_MISSING = 1146  # MySQL：資料表不存在（還沒執行 migrate_1029_trip_member_preferences.sql）
_MAX_PLACES = 20
_MAX_SPECIAL_NEEDS = 500


def _split_places(text):
    """textarea 一行一個地點，去掉空白與重複，保留填寫順序。"""
    places = []
    for line in (text or "").splitlines():
        place = line.strip()[:100]
        if place and place not in places:
            places.append(place)
    return places[:_MAX_PLACES]


def _split_tags(value):
    return [tag for tag in (value or "").split(",") if tag]


def parse_form(form):
    """把表單轉成要存進資料庫的欄位，回傳 (data, errors)。"""
    errors = []
    like = [tag for tag in form.getlist("like_activities") if tag in ACTIVITY_TAGS]
    dislike = [tag for tag in form.getlist("dislike_activities") if tag in ACTIVITY_TAGS]
    if set(like) & set(dislike):
        errors.append("同一個活動不能同時勾選喜歡和不喜歡。")

    budget_limit = None
    raw_budget = form.get("budget_limit", "").strip()
    if raw_budget:
        try:
            budget_limit = Decimal(raw_budget)
        except InvalidOperation:
            budget_limit = None
        if budget_limit is None or budget_limit < 0 or budget_limit >= Decimal("10000000000"):
            errors.append("可接受預算請填 0 以上的數字。")
            budget_limit = None

    diet = form.get("diet", "none")
    transport_pref = form.get("transport_pref", "any")
    walk_tolerance = form.get("walk_tolerance", "medium")
    intensity = form.get("intensity") or None
    special_needs = form.get("special_needs", "").strip()
    if len(special_needs) > _MAX_SPECIAL_NEEDS:
        errors.append(f"特殊需求最多 {_MAX_SPECIAL_NEEDS} 字。")

    data = {
        "like_activities": ",".join(like) or None,
        "dislike_activities": ",".join(dislike) or None,
        "must_visit": "\n".join(_split_places(form.get("must_visit"))) or None,
        "avoid_places": "\n".join(_split_places(form.get("avoid_places"))) or None,
        "budget_limit": budget_limit,
        "diet": diet if diet in DIET_LABELS else "none",
        "transport_pref": transport_pref if transport_pref in TRANSPORT_LABELS else "any",
        "walk_tolerance": walk_tolerance if walk_tolerance in WALK_LABELS else "medium",
        "intensity": intensity if intensity in INTENSITY_LABELS else None,
        "special_needs": special_needs or None,
    }
    return data, errors


def save_preference(cursor, trip_id, user_id, data):
    cursor.execute("""
        INSERT INTO trip_member_preferences
            (trip_id, user_id, like_activities, dislike_activities, must_visit, avoid_places,
             budget_limit, diet, transport_pref, walk_tolerance, intensity, special_needs)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            like_activities=VALUES(like_activities), dislike_activities=VALUES(dislike_activities),
            must_visit=VALUES(must_visit), avoid_places=VALUES(avoid_places), budget_limit=VALUES(budget_limit),
            diet=VALUES(diet), transport_pref=VALUES(transport_pref), walk_tolerance=VALUES(walk_tolerance),
            intensity=VALUES(intensity), special_needs=VALUES(special_needs)
    """, (trip_id, user_id, data["like_activities"], data["dislike_activities"], data["must_visit"],
          data["avoid_places"], data["budget_limit"], data["diet"], data["transport_pref"],
          data["walk_tolerance"], data["intensity"], data["special_needs"]))


def load_trip_preferences(cursor, trip_id):
    """目前仍在行程裡的成員填過的偏好；資料表還沒建立時回傳 None。"""
    try:
        cursor.execute("""
            SELECT p.* FROM trip_member_preferences p
            JOIN trip_members tm ON tm.trip_id=p.trip_id AND tm.user_id=p.user_id AND tm.join_status='accepted'
            WHERE p.trip_id=%s
        """, (trip_id,))
    except Error as error:
        if getattr(error, "errno", None) != _TABLE_MISSING:
            raise
        return None
    return cursor.fetchall()


def my_form_values(cursor, rows, user_id):
    """表單要帶入的值：先用這趟行程填過的，沒有就用旅遊人格問卷，再沒有就空白。

    回傳 (values, source)，source 是 'trip'、'profile' 或 None。
    """
    mine = next((row for row in rows or [] if row["user_id"] == user_id), None)
    source = "trip" if mine else None
    if mine is None:
        cursor.execute("""SELECT like_activities, dislike_activities, diet, transport_pref, walk_tolerance
                          FROM traveler_profiles WHERE user_id=%s""", (user_id,))
        mine = cursor.fetchone()
        source = "profile" if mine else None
    mine = mine or {}
    return {
        "like_activities": _split_tags(mine.get("like_activities")),
        "dislike_activities": _split_tags(mine.get("dislike_activities")),
        "must_visit": mine.get("must_visit") or "",
        "avoid_places": mine.get("avoid_places") or "",
        "budget_limit": mine.get("budget_limit"),
        "diet": mine.get("diet") or "none",
        "transport_pref": mine.get("transport_pref") or "any",
        "walk_tolerance": mine.get("walk_tolerance") or "medium",
        "intensity": mine.get("intensity"),
        "special_needs": mine.get("special_needs") or "",
    }, source


def _bars(counts, labels, total):
    """把計數轉成 [(名稱, 人數, 百分比)]，百分比以填寫人數為分母。"""
    return [(labels.get(key, key), count, round(count * 100 / total) if total else 0) for key, count in counts]


def summarize(rows):
    """團體偏好統計，給行程頁的統計區塊用。"""
    rows = rows or []
    total = len(rows)

    like_counts = {tag: 0 for tag in ACTIVITY_TAGS}
    intensity_counts = {key: 0 for key in INTENSITY_LABELS}
    must_visit, avoid_places, budgets = {}, {}, []
    for row in rows:
        for tag in _split_tags(row["like_activities"]):
            if tag in like_counts:
                like_counts[tag] += 1
        if row["intensity"] in intensity_counts:
            intensity_counts[row["intensity"]] += 1
        for place in _split_places(row["must_visit"]):
            must_visit[place] = must_visit.get(place, 0) + 1
        for place in _split_places(row["avoid_places"]):
            avoid_places[place] = avoid_places.get(place, 0) + 1
        if row["budget_limit"] is not None:
            budgets.append(Decimal(row["budget_limit"]))

    by_count = lambda counts: sorted(counts.items(), key=lambda item: -item[1])
    return {
        "respondents": total,
        "activities": _bars(by_count(like_counts), {}, total),
        "intensity": _bars(intensity_counts.items(), INTENSITY_LABELS, total),
        "average_budget": (sum(budgets) / len(budgets)).quantize(Decimal("1")) if budgets else None,
        "budget_count": len(budgets),
        "must_visit": by_count(must_visit),
        "avoid_places": by_count(avoid_places),
    }
