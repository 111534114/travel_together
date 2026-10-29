"""串接 Amadeus Self-Service「Flight Offers Search」API，取得會隨日期浮動的真實機票報價。

沒有設定 AMADEUS_API_KEY / AMADEUS_API_SECRET，或是 API 呼叫失敗時，這裡的函式一律回傳 None，
呼叫端（app.py）就會自動改用本地資料庫裡固定班表的機票資料，不會讓網站整個掛掉。
"""
from decimal import Decimal
import time

import requests

from config import AMADEUS_API_KEY, AMADEUS_API_SECRET
from flight_links import to_iata as _to_iata

TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"

_token_cache = {"value": None, "expires_at": 0}
_offer_cache = {}  # {(origin,destination,date,adults): (expires_at, offers)}
CACHE_TTL_SECONDS = 600  # 同一條航線/日期 10 分鐘內重複搜尋就不用再呼叫一次 API，省額度


def is_configured():
    return bool(AMADEUS_API_KEY and AMADEUS_API_SECRET)


def _get_access_token():
    now = time.time()
    if _token_cache["value"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["value"]
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": AMADEUS_API_KEY,
                "client_secret": AMADEUS_API_SECRET,
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["value"] = data["access_token"]
        _token_cache["expires_at"] = now + int(data.get("expires_in", 1700))
        return _token_cache["value"]
    except Exception as error:
        print("Amadeus 取得 access token 失敗：", error)
        return None


def search_flight_offers(origin_keyword, destination_keyword, departure_date, adults=1, max_results=12):
    """回傳一份機票清單(格式跟本地 flights 資料表一致，可以直接丟給既有的 flight_search.html 樣板)，
    查不到/沒設定金鑰/查詢失敗都回傳 None，呼叫端要自己 fallback 回本地資料庫。"""
    if not is_configured() or not departure_date:
        return None
    origin = _to_iata(origin_keyword)
    destination = _to_iata(destination_keyword)
    if not origin or not destination:
        return None

    cache_key = (origin, destination, departure_date, adults)
    cached = _offer_cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]

    token = _get_access_token()
    if not token:
        return None

    try:
        resp = requests.get(
            SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "adults": adults,
                "currencyCode": "TWD",
                "max": max_results,
            },
            timeout=10,
        )
        resp.raise_for_status()
        offers = _parse_offers(resp.json().get("data", []))
        _offer_cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, offers)
        return offers
    except Exception as error:
        print("Amadeus 機票查詢失敗：", error)
        return None


def cheapest_price(origin_keyword, destination_keyword, departure_date, adults=1):
    """只要拿最低價(給日期選擇列用)，不需要組完整的航班卡片資料。"""
    offers = search_flight_offers(origin_keyword, destination_keyword, departure_date, adults)
    if not offers:
        return None
    return min(offer["price"] for offer in offers)


def _iso_duration_to_minutes(value):
    """把 Amadeus 的 ISO 8601 區間格式(例如 PT4H10M)轉成分鐘數。"""
    if not value or not value.startswith("PT"):
        return 0
    hours = minutes = 0
    number = ""
    for ch in value[2:]:
        if ch.isdigit():
            number += ch
        elif ch == "H":
            hours = int(number or 0); number = ""
        elif ch == "M":
            minutes = int(number or 0); number = ""
    return hours * 60 + minutes


def _parse_offers(raw_offers):
    results = []
    for offer in raw_offers:
        try:
            itinerary = offer["itineraries"][0]
            segments = itinerary["segments"]
            first_seg, last_seg = segments[0], segments[-1]
            results.append({
                "flight_id": "amadeus-" + offer["id"],
                "airline_name": first_seg["carrierCode"],
                "flight_number": first_seg["carrierCode"] + first_seg["number"],
                "departure_time": first_seg["departure"]["at"][11:16],
                "arrival_time": last_seg["arrival"]["at"][11:16],
                "duration_minutes": _iso_duration_to_minutes(itinerary.get("duration")),
                "price": Decimal(offer["price"]["total"]),  # 跟本地資料庫的 DECIMAL 價格型別一致，
                # 避免跟 booking_search.py 裡用 Decimal 做價格篩選/排序時 float 對 Decimal 比較直接噴錯
                "cabin_class": "經濟艙",
                "stops": len(segments) - 1,
                "seats_available": int(offer.get("numberOfBookableSeats") or 9),
                "origin_city": first_seg["departure"]["iataCode"],
                "destination_city": last_seg["arrival"]["iataCode"],
                "origin_country": "",
                "destination_country": "",
                "is_live": True,
            })
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return results
