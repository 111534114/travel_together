"""Shared restaurant ranking queries for member pages (mirrors attraction_rankings.py)."""

from attraction_rankings import TAIWAN_COUNTIES  # noqa: F401  (re-exported for callers that need the county list)


_RANKING_FROM = """
    FROM restaurants r
    JOIN countries co ON co.country_id = r.country_id
    JOIN cities ci ON ci.city_id = r.city_id
    LEFT JOIN (
        SELECT restaurant_id, COUNT(*) AS favorite_count
        FROM favorites
        WHERE target_type = 'restaurant'
        GROUP BY restaurant_id
    ) f ON f.restaurant_id = r.restaurant_id
    LEFT JOIN (
        SELECT i.restaurant_id, COUNT(*) AS itinerary_count
        FROM itineraries i
        JOIN trips t ON t.trip_id = i.trip_id
        WHERE t.deleted_at IS NULL AND i.restaurant_id IS NOT NULL
        GROUP BY i.restaurant_id
    ) i ON i.restaurant_id = r.restaurant_id
"""


def _ranking_where(country_id=None, city_id=None, keyword="", positive_only=False,
                   county_name=None, favorites_only=False):
    conditions = ["r.status = 'active'", "r.deleted_at IS NULL"]
    params = []
    if country_id:
        conditions.append("r.country_id = %s")
        params.append(country_id)
    if city_id:
        conditions.append("r.city_id = %s")
        params.append(city_id)
    if county_name:
        conditions.append("co.name IN ('台灣', '臺灣', 'Taiwan')")
        conditions.append("REPLACE(ci.name, '臺', '台') = %s")
        params.append(county_name.replace("臺", "台"))
    if keyword:
        conditions.append("(r.name LIKE %s OR r.address LIKE %s)")
        params.extend((f"%{keyword}%", f"%{keyword}%"))
    if positive_only:
        conditions.append("COALESCE(i.itinerary_count, 0) > 0")
    if favorites_only:
        conditions.append("COALESCE(f.favorite_count, 0) > 0")
    return " AND ".join(conditions), params


def fetch_restaurant_rankings(cursor, *, country_id=None, city_id=None, keyword="",
                              positive_only=False, limit=20, offset=0,
                              county_name=None, favorites_only=False, sort_by="itineraries"):
    """Rank active restaurants by itinerary uses or favorites."""
    where, params = _ranking_where(country_id, city_id, keyword, positive_only,
                                   county_name, favorites_only)
    if sort_by not in ("itineraries", "favorites"):
        raise ValueError("Unsupported restaurant ranking sort")
    order = ("favorite_count DESC, itinerary_count DESC" if sort_by == "favorites"
             else "itinerary_count DESC, favorite_count DESC")
    cursor.execute(f"""
        SELECT r.restaurant_id, r.country_id, r.city_id, r.name, r.address,
               r.image_path, co.name AS country, ci.name AS city,
               COALESCE(f.favorite_count, 0) AS favorite_count,
               COALESCE(i.itinerary_count, 0) AS itinerary_count
        {_RANKING_FROM}
        WHERE {where}
        ORDER BY {order}, r.name ASC, r.restaurant_id ASC
        LIMIT %s OFFSET %s
    """, tuple(params + [limit, offset]))
    return cursor.fetchall()


def count_restaurant_rankings(cursor, *, country_id=None, city_id=None, keyword="",
                              positive_only=False):
    where, params = _ranking_where(country_id, city_id, keyword, positive_only)
    cursor.execute(f"""
        SELECT COUNT(*) AS total
        {_RANKING_FROM}
        WHERE {where}
    """, tuple(params))
    return cursor.fetchone()["total"]
