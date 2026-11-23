"""地點名稱比對：判斷兩個景點／餐廳／住宿名稱是不是同一個地方，並找出資料庫裡相似的既有資料。

例如「台北101」「臺北 101」「TAIPEI 101」會被視為同一個；「象山步道」和「象山親山步道」很相似。
只用字串規則，不呼叫 AI，結果固定、可測試，提案預審的「自動收下」規則也用它判斷，不會被 AI 說服。
"""

import re
import unicodedata
from difflib import SequenceMatcher

# 名稱比對前要拿掉的符號(全形半形都含)
_PUNCTUATION = re.compile(r"[\s\-‐‑–—_·・•.,，、。:：;；'\"’“”()（）\[\]【】「」『』/／&＆!！?？~～]+")

CATALOG_TABLES = {
    "attraction": ("attractions", "attraction_id"),
    "restaurant": ("restaurants", "restaurant_id"),
    "accommodation": ("accommodations", "accommodation_id"),
}

DUPLICATE_SCORE = 0.85  # 相似度達到這個值就當作「可能重複」，自動收下會被擋下來
SIMILAR_SCORE = 0.6  # 列給管理員參考的最低相似度


def normalize_name(name):
    """統一寫法：全形轉半形、英文轉小寫、臺→台、拿掉空白與標點。"""
    text = unicodedata.normalize("NFKC", name or "").lower().replace("臺", "台")
    return _PUNCTUATION.sub("", text)


def normalize_region(name):
    """城市／國家名稱比對用：再拿掉結尾的「市、縣、都、府、區…」這類行政區字。"""
    text = normalize_name(name)
    return re.sub(r"(特別市|特別自治道|自治區|市|縣|都|府|道|區|省|州)$", "", text)


def similarity(first, second):
    """回傳 0～1 的相似度；完全相同(統一寫法後)是 1，一個名稱完整包含另一個(至少 2 個字)是 0.9。"""
    a, b = normalize_name(first), normalize_name(second)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    score = SequenceMatcher(None, a, b).ratio()
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 2 and shorter in longer:
        score = max(score, 0.9)
    return round(score, 3)


def same_region(first, second):
    """兩個城市(或國家)名稱是不是同一個，例如「臺北市」和「台北」。"""
    a, b = normalize_region(first), normalize_region(second)
    return bool(a and b and (a == b or a in b or b in a))


def find_similar_places(cursor, item_type, name, city_id, exclude_proposal_id=None, limit=5):
    """找同一個城市裡名稱相似的既有資料與其他待審提案。cursor 需為 dictionary=True。

    回傳 [{"source": "catalog"|"proposal", "id", "name", "address", "status", "score"}]，依相似度由高到低。
    """
    if item_type not in CATALOG_TABLES or not name:
        return []
    table, id_column = CATALOG_TABLES[item_type]
    matches = []
    cursor.execute(
        f"SELECT {id_column} AS id, name, address, status FROM {table} WHERE city_id = %s AND deleted_at IS NULL",
        (city_id,),
    )
    for row in cursor.fetchall():
        score = similarity(name, row["name"])
        if score >= SIMILAR_SCORE:
            matches.append({"source": "catalog", "id": row["id"], "name": row["name"],
                            "address": row.get("address"), "status": row.get("status"), "score": score})
    cursor.execute(
        """
        SELECT p.proposal_id AS id, p.title AS name, p.location AS address, p.content_review_status AS status
        FROM proposals p JOIN trips t ON t.trip_id = p.trip_id
        WHERE p.proposal_type = %s AND t.city_id = %s AND p.content_review_status = 'pending'
          AND p.proposal_id <> %s
        """,
        (item_type, city_id, exclude_proposal_id or 0),
    )
    for row in cursor.fetchall():
        score = similarity(name, row["name"])
        if score >= SIMILAR_SCORE:
            matches.append({"source": "proposal", "id": row["id"], "name": row["name"],
                            "address": row.get("address"), "status": row.get("status"), "score": score})
    matches.sort(key=lambda match: -match["score"])
    return matches[:limit]


# ---------- 網站裡的景點／餐廳／住宿：搜尋與查詢(行程頁名稱搜尋框、新增行程項目、行程助理共用) ----------

SITE_PLACE_COLUMNS = {  # 類型 -> (資料表, 主鍵, 費用欄位, 行程項目連結欄位)
    "attraction": ("attractions", "attraction_id", "ticket_price", "attraction_id"),
    "restaurant": ("restaurants", "restaurant_id", "0", "restaurant_id"),
    "accommodation": ("accommodations", "accommodation_id", "price_per_night", "accommodation_id"),
}


def search_site_places(cursor, item_type, keyword, city_id, country_id, limit=8):
    """搜尋同一個國家、已上架的資料；同城市的排前面。沒給關鍵字時只列同城市的。cursor 需為 dictionary=True。"""
    if item_type not in SITE_PLACE_COLUMNS:
        return []
    table, id_column, cost_sql, _ = SITE_PLACE_COLUMNS[item_type]
    params = [city_id, country_id]
    keyword = (keyword or "").strip()[:50]
    if keyword:
        like = "%" + keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        keyword_sql = "AND (x.name LIKE %s OR REPLACE(x.name,'臺','台') LIKE %s)"
        params += [like, like.replace("臺", "台")]
    else:
        keyword_sql = "AND x.city_id = %s"
        params.append(city_id)
    cursor.execute(f"""
        SELECT x.{id_column} AS id, x.name, x.address, {cost_sql} AS cost, x.image_path,
               x.latitude, x.longitude, ci.name AS city, (x.city_id = %s) AS same_city
        FROM {table} x LEFT JOIN cities ci ON ci.city_id = x.city_id
        WHERE x.country_id = %s AND x.status = 'active' AND x.deleted_at IS NULL {keyword_sql}
        ORDER BY same_city DESC, CHAR_LENGTH(x.name) ASC, x.name ASC
        LIMIT {int(limit)}
    """, params)
    return cursor.fetchall()


def find_site_place(cursor, item_type, name, country_id):
    """用完整名稱找同一個國家、已上架的資料，找不到回傳 None。"""
    if item_type not in SITE_PLACE_COLUMNS or not name:
        return None
    table, id_column, cost_sql, _ = SITE_PLACE_COLUMNS[item_type]
    cursor.execute(
        f"""SELECT {id_column} AS id, name, address, {cost_sql} AS cost, latitude, longitude
            FROM {table} WHERE name = %s AND country_id = %s AND status = 'active' AND deleted_at IS NULL LIMIT 1""",
        (name, country_id),
    )
    return cursor.fetchone()
