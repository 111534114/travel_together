"""Shared accommodation ranking queries for member pages (mirrors attraction_rankings.py)."""

from attraction_rankings import TAIWAN_COUNTIES  # noqa: F401  (re-exported for callers that need the county list)


_RANKING_FROM = """
    FROM accommodations ac
    JOIN countries co ON co.country_id = ac.country_id
    JOIN cities ci ON ci.city_id = ac.city_id
    LEFT JOIN (
        SELECT accommodation_id, COUNT(*) AS favorite_count
        FROM favorites
        WHERE target_type = 'accommodation'
        GROUP BY accommodation_id
    ) f ON f.accommodation_id = ac.accommodation_id
    LEFT JOIN (
        SELECT i.accommodation_id, COUNT(*) AS itinerary_count
        FROM itineraries i
        JOIN trips t ON t.trip_id = i.trip_id
        WHERE t.deleted_at IS NULL AND i.accommodation_id IS NOT NULL
        GROUP BY i.accommodation_id
    ) i ON i.accommodation_id = ac.accommodation_id
"""


def _ranking_where(country_id=None, city_id=None, keyword="", positive_only=False,
                   county_name=None, favorites_only=False):
    conditions = ["ac.status = 'active'", "ac.deleted_at IS NULL"]
    params = []
    if country_id:
        conditions.append("ac.country_id = %s")
        params.append(country_id)
    if city_id:
        conditions.append("ac.city_id = %s")
        params.append(city_id)
    if county_name:
        conditions.append("co.name IN ('台灣', '臺灣', 'Taiwan')")
        conditions.append("REPLACE(ci.name, '臺', '台') = %s")
        params.append(county_name.replace("臺", "台"))
    if keyword:
        conditions.append("(ac.name LIKE %s OR ac.address LIKE %s)")
        params.extend((f"%{keyword}%", f"%{keyword}%"))
    if positive_only:
        conditions.append("COALESCE(i.itinerary_count, 0) > 0")
    if favorites_only:
        conditions.append("COALESCE(f.favorite_count, 0) > 0")
    return " AND ".join(conditions), params


def fetch_accommodation_rankings(cursor, *, country_id=None, city_id=None, keyword="",
                                 positive_only=False, limit=20, offset=0,
                                 county_name=None, favorites_only=False, sort_by="itineraries"):
    """Rank active accommodations by itinerary uses or favorites."""
    where, params = _ranking_where(country_id, city_id, keyword, positive_only,
                                   county_name, favorites_only)
    if sort_by not in ("itineraries", "favorites"):
        raise ValueError("Unsupported accommodation ranking sort")
    order = ("favorite_count DESC, itinerary_count DESC" if sort_by == "favorites"
             else "itinerary_count DESC, favorite_count DESC")
    cursor.execute(f"""
        SELECT ac.accommodation_id, ac.country_id, ac.city_id, ac.name, ac.address,
               ac.image_path, co.name AS country, ci.name AS city,
               COALESCE(f.favorite_count, 0) AS favorite_count,
               COALESCE(i.itinerary_count, 0) AS itinerary_count
        {_RANKING_FROM}
        WHERE {where}
        ORDER BY {order}, ac.name ASC, ac.accommodation_id ASC
        LIMIT %s OFFSET %s
    """, tuple(params + [limit, offset]))
    return cursor.fetchall()


def count_accommodation_rankings(cursor, *, country_id=None, city_id=None, keyword="",
                                 positive_only=False):
    where, params = _ranking_where(country_id, city_id, keyword, positive_only)
    cursor.execute(f"""
        SELECT COUNT(*) AS total
        {_RANKING_FROM}
        WHERE {where}
    """, tuple(params))
    return cursor.fetchone()["total"]
