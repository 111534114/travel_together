"""串接 SerpApi 的「Google Flights」API，取得真實、每天浮動的機票報價
(SerpApi 幫我們查 Google Flights 的搜尋結果並整理成 JSON，不是我們自己爬蟲)。

沒有設定 SERPAPI_API_KEY，或是查詢失敗時，這裡的函式一律回傳 None，
呼叫端（app.py）就會自動改用下一個資料來源(Amadeus 或本地資料庫)，不會讓網站整個掛掉。
"""
from decimal import Decimal
import re
import time

import requests

from config import SERPAPI_API_KEY
from flight_links import to_iata

SEARCH_URL = "https://serpapi.com/search"

def _translate_cabin_class(travel_class):
    """Google Flights 的艙等字串格式不一致：預設(不指定 travel_class 查詢參數)查經濟艙時回傳 "Economy"，
    但指定 travel_class 參數查特定艙等時卻回傳 "Business Class"/"First Class" 這種多了「 Class」的格式，
    直接整串比對字典會對不到，所以改成用「字串裡有沒有包含關鍵字」來比對，兩種格式都吃得到。"""
    if not travel_class:
        return "經濟艙"
    low = travel_class.strip().lower()
    if "premium economy" in low:
        return "豪華經濟艙"
    if "business" in low:
        return "商務艙"
    if "first" in low:
        return "頭等艙"
    if "economy" in low:
        return "經濟艙"
    return travel_class

_cache = {}  # {(origin,destination,depart,return,adults): (expires_at, offers)}
CACHE_TTL_SECONDS = 600  # 同一條航線/日期 10 分鐘內重複搜尋就不用再呼叫一次 API，省免費額度

_booking_cache = {}  # {booking_token: (expires_at, redirect_dict_or_None)}
BOOKING_CACHE_TTL_SECONDS = 1800


def is_configured():
    return bool(SERPAPI_API_KEY)


#  Google Flights 的艙等查詢參數(travel_class)：不給的話預設只會查經濟艙，商務艙/頭等艙的航班
# 完全不會出現在結果裡(不是被我們篩掉，是 Google 自己根本沒回傳)，要指定對應代碼才查得到。
CABIN_CLASS_QUERY_CODES = {"經濟艙": "1", "豪華經濟艙": "2", "商務艙": "3", "頭等艙": "4"}


def search_flight_offers(origin_keyword, destination_keyword, departure_date, return_date=None, adults=1, cabin_class=None):
    """回傳一份機票清單(格式跟本地 flights 資料表一致，可以直接丟給既有的 flight_search.html 樣板)，
    把 SerpApi 當天查到的航班全部回傳，不做人為的筆數上限──有篩選需求(價格/直飛等)讓使用者自己
    用搜尋結果頁的篩選面板去篩，不要在這裡就先砍掉一部分資料。
    cabin_class 是中文艙等名稱(例如「商務艙」)，不給就是預設的經濟艙(Google Flights 的預設值)，
    要查其他艙等要帶這個參數(見 CABIN_CLASS_QUERY_CODES)，所以「艙等」篩選選了特定艙等時，
    呼叫端(app.py)要另外重新查一次，不是用同一批經濟艙資料用本地篩選。
    查不到/沒設定金鑰/查詢失敗都回傳 None，呼叫端要自己 fallback。"""
    if not is_configured() or not departure_date:
        return None
    origin = to_iata(origin_keyword)
    destination = to_iata(destination_keyword)
    if not origin or not destination:
        return None

    cache_key = (origin, destination, departure_date, return_date, adults, cabin_class)
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
    if cabin_class and cabin_class in CABIN_CLASS_QUERY_CODES:
        params["travel_class"] = CABIN_CLASS_QUERY_CODES[cabin_class]

    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        offers = _parse_offers(resp.json())
        _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, offers)
        return offers
    except Exception as error:
        print("SerpApi 機票查詢失敗：", error)
        return None


def search_return_offers(origin_keyword, destination_keyword, departure_date, return_date, departure_token, adults=1, cabin_class=None):
    """來回搜尋的第二步：帶著 departure_token 再查一次，拿到「真的配這班去程」的回程選項清單，
    每個選項的 price 已經是去程+回程的真實來回總價(不是去程跟回程分開加總估的)，
    而且每個選項都有 booking_token，可以直接丟給 get_booking_redirect() 查真正的訂票連結。
    cabin_class 要跟產生這個 departure_token 的那次搜尋用同一個艙等，才會跟原本選的去程艙等一致。
    查不到/沒設定金鑰/缺參數都回傳 None。"""
    if not is_configured() or not departure_date or not return_date or not departure_token:
        return None
    origin = to_iata(origin_keyword)
    destination = to_iata(destination_keyword)
    if not origin or not destination:
        return None

    cache_key = ("return", origin, destination, departure_date, return_date, departure_token, adults, cabin_class)
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]

    params = {
        "engine": "google_flights",
        "api_key": SERPAPI_API_KEY,
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "return_date": return_date,
        "type": "1",
        "currency": "TWD",
        "adults": adults,
        "hl": "zh-tw",
        "departure_token": departure_token,
    }
    if cabin_class and cabin_class in CABIN_CLASS_QUERY_CODES:
        params["travel_class"] = CABIN_CLASS_QUERY_CODES[cabin_class]

    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=20)
        resp.raise_for_status()
        offers = _parse_offers(resp.json())
        _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, offers)
        return offers
    except Exception as error:
        print("SerpApi 回程選項查詢失敗：", error)
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
            # 只挑「together」：一次訂到去程+回程(或單程)的單一連結。
            # 來回票如果最便宜的組合要跨兩家不同的航空公司分開訂(departing/returning 各自的連結)，
            # 這裡故意跳過不選，因為沒辦法只用一個連結完成訂票，寧可退回比價網站的連結，不要給錯誤導向。
            leg = option.get("together")
            if not leg:
                continue
            booking_request = leg.get("booking_request")
            if not booking_request or not booking_request.get("url") or not booking_request.get("post_data"):
                continue
            candidates.append({
                "book_with": leg.get("book_with") or "",
                "price": leg.get("price"),
                "is_airline": bool(leg.get("airline")),
                "url": booking_request["url"],
                "post_data": booking_request["post_data"],
            })

        if candidates:
            # 優先導向航空公司官網(airline=True)；該班沒有官網直訂選項時才退而求其次選最便宜的 OTA
            airline_candidates = [c for c in candidates if c["is_airline"]]
            pool = airline_candidates or candidates
            cheapest = min(pool, key=lambda c: c["price"] if c["price"] is not None else float("inf"))
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


def _parse_amenities(extensions):
    """把 SerpApi 的 extensions(機上設施，英文+部分已經是中文單位混雜的字串，例如
    "Above average legroom (81 公分)")轉成統一的中文標籤。只處理真的有資料的項目，
    碳排放量不算「機上設施」，不放進這個清單裡(有需要的話另外顯示)。
    Google Flights 的資料本身就沒有「艙等餐點」「準點率」「航廈」這些欄位，這裡沒辦法生出這些資訊。"""
    amenities = []
    for ext in extensions or []:
        low = ext.lower()
        if "legroom" in low:
            cm_match = re.search(r"\((\d+\s*公分)\)", ext)
            cm_suffix = f"（{cm_match.group(1)}）" if cm_match else ""
            if "above average" in low:
                amenities.append({"icon": "legroom", "label": f"座距較寬鬆{cm_suffix}"})
            elif "below average" in low:
                amenities.append({"icon": "legroom", "label": f"座距較窄{cm_suffix}"})
            else:
                amenities.append({"icon": "legroom", "label": f"一般座距{cm_suffix}"})
        elif "wi-fi" in low or "wifi" in low:
            amenities.append({"icon": "wifi", "label": "Wi-Fi（免費）" if "free" in low else "Wi-Fi（收費）"})
        elif "usb" in low and "power" in low:
            amenities.append({"icon": "power", "label": "座位附電源與 USB 插座"})
        elif "usb" in low:
            amenities.append({"icon": "power", "label": "座位附 USB 插座"})
        elif "power" in low:
            amenities.append({"icon": "power", "label": "座位附電源插座"})
        elif "on-demand video" in low:
            amenities.append({"icon": "screen", "label": "個人螢幕點播影音"})
        elif "stream media" in low:
            amenities.append({"icon": "screen", "label": "可串流影音到個人裝置"})
    return amenities


# 機型字串(例如 "Airbus A330"、"Boeing 737")對應的機身尺寸分類，是公開的飛機規格知識(不是瞎猜)：
# 寬體客機(雙走道，通常飛長程/洲際線)分類成「大型飛機」，窄體客機(單走道，短中程線常見)分類成「中型飛機」，
# 支線客機(通常機型較小，短程/支線航班)分類成「小型飛機」。查不到(機型字串沒對到已知關鍵字)就不分類，
# 不要亂猜一個尺寸給使用者。
_WIDEBODY_KEYWORDS = ("a330", "a340", "a350", "a380", "767", "777", "787", "747")
_NARROWBODY_KEYWORDS = ("a220", "a318", "a319", "a320", "a321", "737", "757", "md-", "md8", "md9")
_REGIONAL_KEYWORDS = ("embraer", "e170", "e175", "e190", "e195", "erj", "crj", "dash 8", "dhc", "atr")


def _airplane_category(airplane_name):
    low = (airplane_name or "").lower()
    if not low:
        return None
    if any(key in low for key in _WIDEBODY_KEYWORDS):
        return "大型飛機"
    if any(key in low for key in _NARROWBODY_KEYWORDS):
        return "中型飛機"
    if any(key in low for key in _REGIONAL_KEYWORDS):
        return "小型飛機"
    return None


def _parse_layovers(layovers):
    """中停城市清單：SerpApi 的 layovers 本身就有中文機場名稱(因為查詢時帶 hl=zh-tw)、
    機場代碼、中停時間(分鐘)，直接整理格式，不用自己再查一次。"""
    results = []
    for layover in layovers or []:
        try:
            results.append({
                "iata": layover["id"],
                "name": layover.get("name") or layover["id"],
                "duration_minutes": layover.get("duration"),
            })
        except (KeyError, TypeError):
            continue
    return results


def _parse_offers(data):
    results = []
    for bucket in ("best_flights", "other_flights"):
        for item in data.get(bucket, []):
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
                    "amenities": _parse_amenities(first_seg.get("extensions")),
                    "stops": len(segments) - 1,
                    "seats_available": None,  # Google Flights 不提供剩餘座位數，不要顯示假數字
                    "origin_city": first_seg["departure_airport"].get("id", ""),
                    "destination_city": last_seg["arrival_airport"].get("id", ""),
                    "origin_country": "",
                    "destination_country": "",
                    "airplane_category": _airplane_category(first_seg.get("airplane")),
                    "layovers": _parse_layovers(item.get("layovers")),
                    # 多段中停時，用時間最長的那段中停時間當代表值，給「中停時長」篩選用
                    "layover_minutes": max((l["duration_minutes"] for l in _parse_layovers(item.get("layovers")) if l["duration_minutes"]), default=None),
                    "is_live": True,
                    "booking_token": item.get("booking_token"),
                    # 來回搜尋第一步（選去程）時 Google 不會直接給 booking_token，而是給 departure_token，
                    # 要帶著這個再查一次才能拿到「真的配這班去程」的回程選項和真實來回總價
                    "departure_token": item.get("departure_token"),
                })
            except (KeyError, IndexError, TypeError, ValueError):
                continue
    return results

