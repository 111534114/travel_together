"""訪客按了「要登入才能用」的按鈕：先記住按了什麼，登入後自動完成，再帶回原本的頁面。

適用：探索景點／餐廳／住宿的「收藏」「加入行程」、景點相簿「上傳照片」，
以及訂房／機票／火車搜尋結果的「♡ 收藏」。

- 訪客端(app.visitor_remember_action)：把按鈕原本要送去的網址(target)和目前頁面(back)交給 remember()，
  只接受下面 RULES 列出的動作，其他一律拒絕。
- 登入後(member.run_pending_action)：run() 依動作執行。收藏一律「只加入、不取消」(原本的按鈕是切換式的)；
  「加入行程」要選哪一趟、哪一天，所以不自動完成，而是回到原本頁面並自動打開「加入行程」視窗；
  「上傳照片」的檔案沒辦法跨登入保留，所以回到相簿區塊。
"""

import json
import re
from decimal import Decimal, InvalidOperation

import tdx_trains
from booking_search import LIVE_TRAIN_KEY_SQL, TABLES as BOOKING_TABLES, TRAIN_TYPE_LABELS, _live_train_key

PLACE_KINDS = {"attractions": "attraction", "restaurants": "restaurant", "accommodations": "accommodation"}
PLACE_LABELS = {"attraction": "景點", "restaurant": "餐廳", "accommodation": "住宿"}

RULES = [  # (動作, 按鈕原本要送去的網址)
    ("place_favorite", re.compile(r"^/member/(attractions|restaurants|accommodations)/(\d+)/favorite$")),
    ("add_to_trip", re.compile(r"^/member/(attractions|restaurants|accommodations)/(\d+)/add-to-trip$")),
    ("album_post", re.compile(r"^/member/attractions/(\d+)/posts$")),
    ("booking_favorite", re.compile(r"^/member/booking-favorites/(hotel|flight|train)/(\d+)$")),
    ("live_favorite", re.compile(r"^/member/booking-favorites/live$")),
    ("live_train", re.compile(r"^/member/booking-favorites/train/live$")),
]

MESSAGES = {
    "place_favorite": "登入後就會自動幫你收藏。",
    "add_to_trip": "登入後會回到這一頁，直接打開「加入行程」讓你選要加到哪一趟。",
    "album_post": "登入後會回到這一頁的相簿，就可以上傳照片了。",
    "booking_favorite": "登入後就會自動幫你收藏。",
    "live_favorite": "登入後就會自動幫你收藏。",
    "live_train": "登入後就會自動幫你收藏這班車。",
}


def safe_back(path):
    path = str(path or "")
    if not path.startswith("/") or path.startswith("//") or any(ch in path for ch in "\\\r\n"):
        return None
    return path[:500]


def remember(target, back, form):
    """檢查訪客按的按鈕，回傳要存進 session 的動作 dict；不認得的動作回傳 None。"""
    back = safe_back(back)
    target = str(target or "").split("?")[0]
    if not back:
        return None
    for action, pattern in RULES:
        match = pattern.match(target)
        if not match:
            continue
        data = {}
        if action in ("place_favorite", "add_to_trip"):
            data = {"kind": PLACE_KINDS[match.group(1)], "id": int(match.group(2))}
        elif action == "album_post":
            data = {"id": int(match.group(1))}
        elif action == "booking_favorite":
            data = {"kind": match.group(1), "id": int(match.group(2))}
        elif action == "live_favorite":
            try:
                fav = json.loads(form.get("fav") or "{}")
            except ValueError:
                return None
            if not isinstance(fav, dict) or fav.get("kind") not in ("hotel", "flight") or not str(fav.get("key") or "").strip():
                return None
            data = {key: str(fav.get(key) or "")[:1000] for key in ("kind", "key", "title", "subtitle", "price", "link")}
        elif action == "live_train":
            data = {key: str(form.get(key) or "")[:100] for key in ("live_id", "from", "to", "date", "rail")}
            if not data["live_id"] or not data["from"] or not data["to"]:
                return None
        return {"type": action, "data": data, "back": back}
    return None


def _with_param(path, name, value):
    base, _, anchor = path.partition("#")
    joiner = "&" if "?" in base else "?"
    return f"{base}{joiner}{name}={value}"


def run(cursor, user_id, action):
    """登入後執行。回傳 (給使用者看的訊息, 訊息類型, 要回去的網址)。呼叫端負責 commit。cursor 需為 dictionary=True。"""
    kind, data, back = action.get("type"), action.get("data") or {}, safe_back(action.get("back")) or "/member/"

    if kind == "add_to_trip":
        return "登入好了！選擇要把它加到哪一趟、哪一天吧。", "success", _with_param(back, "add_to_trip", f"{data['kind']}-{int(data['id'])}")

    if kind == "album_post":
        return "登入好了！現在可以上傳照片、分享心得了。", "success", back.split("#")[0] + "#album"

    if kind == "place_favorite":
        place = data["kind"]
        if place not in PLACE_LABELS:
            return "收藏失敗，請再試一次。", "error", back
        column = f"{place}_id"
        cursor.execute(f"SELECT favorite_id FROM favorites WHERE user_id=%s AND {column}=%s", (user_id, int(data["id"])))
        if cursor.fetchone():
            return f"這個{PLACE_LABELS[place]}已經在你的收藏裡了。", "success", back
        cursor.execute(f"INSERT INTO favorites (user_id, target_type, {column}) VALUES (%s,%s,%s)", (user_id, place, int(data["id"])))
        return f"已經幫你收藏這個{PLACE_LABELS[place]}！", "success", back

    if kind == "booking_favorite":
        if data["kind"] not in BOOKING_TABLES:
            return "收藏失敗，請再試一次。", "error", back
        table, key = BOOKING_TABLES[data["kind"]]
        extra = " AND deleted_at IS NULL" if data["kind"] == "hotel" else ""
        status_sql = "status IN ('active','hidden')" if data["kind"] == "train" else "status='active'"
        cursor.execute(f"SELECT {key} FROM {table} WHERE {key}=%s AND {status_sql}" + extra, (int(data["id"]),))
        if not cursor.fetchone():
            return "這個項目已經下架，沒辦法收藏。", "error", back
        cursor.execute("INSERT IGNORE INTO booking_favorites(user_id,kind,target_id) VALUES (%s,%s,%s)", (user_id, data["kind"], int(data["id"])))
        return "已經幫你加入收藏！", "success", back

    if kind == "live_favorite":
        link = data.get("link") or None
        if link and not (link.startswith(("https://", "http://")) or safe_back(link)):
            link = None
        try:
            price = Decimal(str(data["price"])) if data.get("price") not in (None, "") else None
            if price is not None and not (price.is_finite() and 0 <= price <= 100000000):
                price = None
        except InvalidOperation:
            price = None
        title = (data.get("title") or "").strip()[:200]
        if not title:
            return "收藏失敗，請再試一次。", "error", back
        cursor.execute(
            """INSERT INTO booking_live_favorites(user_id,kind,item_key,title,subtitle,price,link)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE title=VALUES(title), subtitle=VALUES(subtitle), price=VALUES(price), link=VALUES(link)""",
            (user_id, data["kind"], data["key"][:190], title, (data.get("subtitle") or "")[:300] or None, price, link),
        )
        return "已經幫你加入收藏！", "success", back

    if kind == "live_train":  # 跟原本的收藏一樣：不相信表單資料，重新查 TDX 確認這班車
        rail = data.get("rail") if data.get("rail") in TRAIN_TYPE_LABELS else None
        rows = tdx_trains.search_trains(data["from"], data["to"], data.get("date") or None, rail)
        row = next((r for r in rows or [] if r["train_id"] == data["live_id"]), None)
        if row is None:
            return "找不到這班車次，可能班表已更新，請重新搜尋後再收藏。", "error", back
        train_key = _live_train_key(row)
        cursor.execute(LIVE_TRAIN_KEY_SQL, train_key)
        found = cursor.fetchone()
        if found:
            train_id = found["train_id"]
        else:
            cursor.execute(
                """INSERT INTO trains (train_type, train_number, car_class, origin_station, destination_station,
                                       departure_time, arrival_time, duration_minutes, price, seats_available, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,'hidden')""",
                train_key[:5] + (row["departure_time"], row["arrival_time"], row["duration_minutes"], row["price"]),
            )
            train_id = cursor.lastrowid
        cursor.execute("INSERT IGNORE INTO booking_favorites(user_id,kind,target_id) VALUES (%s,%s,%s)", (user_id, "train", train_id))
        return "已經幫你收藏這班車！", "success", back

    return "", "success", back
