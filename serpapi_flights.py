"""串接 SerpApi 的「Google Flights」API，取得真實、每天浮動的機票報價
(SerpApi 幫我們查 Google Flights 的搜尋結果並整理成 JSON，不是我們自己爬蟲)。

沒有設定 SERPAPI_API_KEY，或是查詢失敗時，這裡的函式一律回傳 None，
呼叫端（app.py）就會自動改用下一個資料來源(Amadeus 或本地資料庫)，不會讓網站整個掛掉。
"""
from decimal import Decimal
import time

import requests

from config import SERPAPI_API_KEY
from flight_links import to_iata

SEARCH_URL = "https://serpapi.com/search"

# Google Flights 的艙等是英文，介面統一用中文顯示
CABIN_CLASS_LABELS = {
    "economy": "經濟艙",
    "premium economy": "豪華經濟艙",
    "business": "商務艙",
    "first": "頭等艙",
}


def _translate_cabin_class(travel_class):
    if not travel_class:
        return "經濟艙"
    return CABIN_CLASS_LABELS.get(travel_class.strip().lower(), travel_class)

_cache = {}  # {(origin,destination,depart,return,adults): (expires_at, offers)}
CACHE_TTL_SECONDS = 600  # 同一條航線/日期 10 分鐘內重複搜尋就不用再呼叫一次 API，省免費額度

_booking_cache = {}  # {booking_token: (expires_at, redirect_dict_or_None)}
BOOKING_CACHE_TTL_SECONDS = 1800


def is_configured():
    return bool(SERPAPI_API_KEY)


def search_flight_offers(origin_keyword, destination_keyword, departure_date, return_date=None, adults=1, max_results=12):
    """回傳一份機票清單(格式跟本地 flights 資料表一致，可以直接丟給既有的 flight_search.html 樣板)，
    查不到/沒設定金鑰/查詢失敗都回傳 None，呼叫端要自己 fallback。"""
    if not is_configured() or not departure_date:
        return None
    origin = to_iata(origin_keyword)
    destination = to_iata(destination_keyword)
    if not origin or not destination:
        return None

    cache_key = (origin, destination, departure_date, return_date, adults)
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]

    params = {
        "engine": "google_flights",
        "api_key": SERPAPI_API_KEY,
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "type": "1" if return_date else "2",  # 1=來回 2=單程
        "currency": "TWD",
        "adults": adults,
        "hl": "zh-tw",
    }
    if return_date:
        params["return_date"] = return_date

    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        offers = _parse_offers(resp.json(), max_results)
        _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, offers)
        return offers
    except Exception as error:
        print("SerpApi 機票查詢失敗：", error)
        return None


def cheapest_price(origin_keyword, destination_keyword, departure_date, return_date=None, adults=1):
    """只要拿最低價(給日期選擇列用)，不需要組完整的航班卡片資料。"""
    offers = search_flight_offers(origin_keyword, destination_keyword, departure_date, return_date, adults)
    if not offers:
        return None
    return min(offer["price"] for offer in offers)


def get_booking_redirect(origin_keyword, destination_keyword, departure_date, booking_token, return_date=None, adults=1):
    """用 booking_token 再查一次，拿到「這個確切航班」在真正訂票網站(航空公司官網或 OTA 像 Gotogate)的連結。

    這是 SerpApi 自己的文件沒寫的用法(文件只說 booking_token 是輸入參數，沒說回傳裡
    藏著 booking_options[].together.booking_request)，是直接拿真的 API 金鑰測出來的：
    - 這次呼叫要等 30~45 秒(比一般搜尋慢很多，Google 要重新即時核價)，所以 timeout 要拉長。
    - 回傳的 booking_options 其實是 Google Flights 自己的「比價」清單，同一班飛機常常有多個訂票來源
      (航空公司官網 + 多個 OTA)，每個來源價格可能不同，這裡會自動挑最便宜的那個來轉址。
    - 回傳的 booking_request 是 Google 的點擊追蹤轉址，格式是 {"url": "...", "post_data": "u=<一長串編碼過的值>"}，
      要用 POST 把 post_data 當成表單送到 url，才會真的跳到訂票網站那頁(不是直接 GET 那個 url)。
    查不到就回傳 None，呼叫端要自己 fallback(例如改連到 Skyscanner 搜尋頁)。
    """
    if not is_configured() or not booking_token:
        return None

    cached = _booking_cache.get(booking_token)
    if cached and cached[0] > time.time():
        return cached[1]

    origin = to_iata(origin_keyword)
    destination = to_iata(destination_keyword)
    if not origin or not destination:
        return None

    params = {
        "engine": "google_flights",
        "api_key": SERPAPI_API_KEY,
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "type": "1" if return_date else "2",
        "currency": "TWD",
        "adults": adults,
        "hl": "zh-tw",
        "booking_token": booking_token,
    }
    if return_date:
        params["return_date"] = return_date

    result = None
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        booking_options = data.get("booking_options") or []

        candidates = []
        for option in booking_options:
            leg = option.get("together") or option.get("departing")
            if not leg:
                continue
            booking_request = leg.get("booking_request")
            if not booking_request or not booking_request.get("url") or not booking_request.get("post_data"):
                continue
            candidates.append({
                "book_with": leg.get("book_with") or "",
                "price": leg.get("price"),
                "url": booking_request["url"],
                "post_data": booking_request["post_data"],
            })

        if candidates:
            cheapest = min(candidates, key=lambda c: c["price"] if c["price"] is not None else float("inf"))
            result = {
                "url": cheapest["url"],
                "post_data": cheapest["post_data"],
                "book_with": cheapest["book_with"],
                "price": cheapest["price"],
                "options": [{"book_with": c["book_with"], "price": c["price"]} for c in candidates],
            }
    except Exception as error:
        print("SerpApi 訂票連結查詢失敗：", error)
        result = None

    _booking_cache[booking_token] = (time.time() + BOOKING_CACHE_TTL_SECONDS, result)
    return result


def _parse_offers(data, max_results):
    results = []
    for bucket in ("best_flights", "other_flights"):
        for item in data.get(bucket, []):
            if len(results) >= max_results:
                return results
            try:
                segments = item["flights"]
                first_seg, last_seg = segments[0], segments[-1]
                results.append({
                    "flight_id": "serpapi-" + str(abs(hash((item.get("price"), first_seg.get("flight_number"), first_seg["departure_airport"]["time"])))),
                    "airline_name": first_seg.get("airline") or "未知航空公司",
                    "airline_logo": first_seg.get("airline_logo"),  # Google 自己託管的航空公司 logo 網址，不用自己存圖檔
                    "flight_number": first_seg.get("flight_number", ""),
                    "departure_time": first_seg["departure_airport"]["time"][11:16],
                    "arrival_time": last_seg["arrival_airport"]["time"][11:16],
                    "duration_minutes": item.get("total_duration") or sum(s.get("duration") or 0 for s in segments),
                    "price": Decimal(str(item["price"])),  # 跟本地資料庫的 DECIMAL 價格型別一致，
                    # 避免跟 booking_search.py 裡用 Decimal 做價格篩選/排序時 float 對 Decimal 比較直接噴錯
                    "cabin_class": _translate_cabin_class(first_seg.get("travel_class")),
                    "stops": len(segments) - 1,
                    "seats_available": None,  # Google Flights 不提供剩餘座位數，不要顯示假數字
                    "origin_city": first_seg["departure_airport"].get("id", ""),
                    "destination_city": last_seg["arrival_airport"].get("id", ""),
                    "origin_country": "",
                    "destination_country": "",
                    "is_live": True,
                    "booking_token": item.get("booking_token"),
                })
            except (KeyError, IndexError, TypeError, ValueError):
                continue
    return results
