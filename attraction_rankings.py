"""Shared attraction ranking queries for the admin dashboard and member pages."""

TAIWAN_COUNTIES = (
    "台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市", "基隆市",
    "新竹市", "嘉義市", "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣",
    "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "台東縣", "澎湖縣", "金門縣", "連江縣",
)


_RANKING_FROM = """
    FROM attractions a
    JOIN countries co ON co.country_id = a.country_id
    JOIN cities ci ON ci.city_id = a.city_id
    LEFT JOIN (
        SELECT attraction_id, COUNT(*) AS favorite_count
        FROM favorites
        WHERE target_type = 'attraction'
        GROUP BY attraction_id
    ) f ON f.attraction_id = a.attraction_id
    LEFT JOIN (
        SELECT i.attraction_id, COUNT(*) AS itinerary_count
        FROM itineraries i
        JOIN trips t ON t.trip_id = i.trip_id
        WHERE t.deleted_at IS NULL AND i.attraction_id IS NOT NULL
        GROUP BY i.attraction_id
    ) i ON i.attraction_id = a.attraction_id
"""


def _ranking_where(country_id=None, city_id=None, keyword="", positive_only=False,
                   county_name=None, favorites_only=False):
    conditions = ["a.status = 'active'", "a.deleted_at IS NULL"]
    params = []
    if country_id:
        conditions.append("a.country_id = %s")
        params.append(country_id)
    if city_id:
        conditions.append("a.city_id = %s")
        params.append(city_id)
    if county_name:
        conditions.append("co.name IN ('台灣', '臺灣', 'Taiwan')")
        conditions.append("REPLACE(ci.name, '臺', '台') = %s")
        params.append(county_name.replace("臺", "台"))
    if keyword:
        conditions.append("(a.name LIKE %s OR a.address LIKE %s)")
        params.extend((f"%{keyword}%", f"%{keyword}%"))
    if positive_only:
        conditions.append("COALESCE(i.itinerary_count, 0) > 0")
    if favorites_only:
        conditions.append("COALESCE(f.favorite_count, 0) > 0")
    return " AND ".join(conditions), params


def fetch_attraction_rankings(cursor, *, country_id=None, city_id=None, keyword="",
                              positive_only=False, limit=20, offset=0,
                              county_name=None, favorites_only=False, sort_by="itineraries"):
    """Rank active attractions by itinerary uses or favorites."""
    where, params = _ranking_where(country_id, city_id, keyword, positive_only,
                                   county_name, favorites_only)
    if sort_by not in ("itineraries", "favorites"):
        raise ValueError("Unsupported attraction ranking sort")
    order = ("favorite_count DESC, itinerary_count DESC" if sort_by == "favorites"
             else "itinerary_count DESC, favorite_count DESC")
    cursor.execute(f"""
        SELECT a.attraction_id, a.country_id, a.city_id, a.name, a.address,
               a.image_path, co.name AS country, ci.name AS city,
               COALESCE(f.favorite_count, 0) AS favorite_count,
               COALESCE(i.itinerary_count, 0) AS itinerary_count
        {_RANKING_FROM}
        WHERE {where}
        ORDER BY {order}, a.name ASC, a.attraction_id ASC
        LIMIT %s OFFSET %s
    """, tuple(params + [limit, offset]))
    return cursor.fetchall()


def count_attraction_rankings(cursor, *, country_id=None, city_id=None, keyword="",
                              positive_only=False):
    where, params = _ranking_where(country_id, city_id, keyword, positive_only)
    cursor.execute(f"""
        SELECT COUNT(*) AS total
        {_RANKING_FROM}
        WHERE {where}
    """, tuple(params))
    return cursor.fetchone()["total"]
