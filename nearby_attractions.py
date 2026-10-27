"""Find published attractions near a trip stop using stored coordinates."""

from math import asin, cos, isfinite, radians, sin, sqrt


def _coordinates(attraction):
    try:
        latitude = float(attraction["latitude"])
        longitude = float(attraction["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (isfinite(latitude) and isfinite(longitude)):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    if latitude == 0 and longitude == 0:
        return None
    return latitude, longitude


def _distance_km(first, second):
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    half_lat = sin((lat2 - lat1) / 2) ** 2
    half_lon = sin((lon2 - lon1) / 2) ** 2
    arc = half_lat + cos(lat1) * cos(lat2) * half_lon
    return 6371.0088 * 2 * asin(min(1, sqrt(arc)))


def find_nearby_attractions(cursor, source, trip_id, itinerary_date, radius_km=5, limit=5):
    """Return nearest active sites not already added to this trip's day."""
    origin = _coordinates(source)
    if origin is None:
        return []

    latitude, longitude = origin
    latitude_span = radius_km / 110
    longitude_span = min(180, radius_km / (110 * max(abs(cos(radians(latitude))), 0.01)))
    cursor.execute("""
        SELECT a.attraction_id, a.name, a.address, a.image_path, a.city_id,
               a.latitude, a.longitude, ci.name AS city
        FROM attractions a
        JOIN cities ci ON ci.city_id = a.city_id
        WHERE a.country_id = %s AND a.attraction_id <> %s
          AND a.status = 'active' AND a.deleted_at IS NULL
          AND a.latitude BETWEEN %s AND %s
          AND a.longitude BETWEEN %s AND %s
          AND NOT EXISTS (
              SELECT 1 FROM itineraries i
              WHERE i.trip_id = %s AND i.itinerary_date = %s
                AND i.attraction_id = a.attraction_id
          )
    """, (
        source["country_id"], source["attraction_id"],
        latitude - latitude_span, latitude + latitude_span,
        longitude - longitude_span, longitude + longitude_span,
        trip_id, itinerary_date,
    ))
    nearby = []
    for candidate in cursor.fetchall():
        coordinates = _coordinates(candidate)
        if coordinates is None:
            continue
        distance = _distance_km(origin, coordinates)
        if distance <= radius_km:
            candidate["distance_km"] = distance
            candidate["distance_label"] = (
                f"約 {max(10, round(distance * 100) * 10):.0f} 公尺" if distance < 1
                else f"約 {distance:.1f} 公里"
            )
            nearby.append(candidate)
    nearby.sort(key=lambda item: (item["distance_km"], item["attraction_id"]))
    return nearby[:limit]
