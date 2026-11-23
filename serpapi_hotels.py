"""SerpApi 的 Google Hotels 即時住宿搜尋：價格(台幣)、圖片、評分、星級都是 Google Hotels 的真實資料。

每次搜尋(含「下一頁」)都會用掉 1 次 SerpApi 額度，所以同樣的搜尋條件會快取一段時間。
沒有設定金鑰或查詢失敗時回傳 None，呼叫端自己退回資料庫的住宿資料。
"""
import json
import os
import re
import html
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import requests

from config import GOOGLE_MAPS_API_KEY, SERPAPI_HOTELS_API_KEY

SEARCH_URL = "https://serpapi.com/search"
CACHE_TTL_SECONDS = 60 * 60
_cache = {}  # {查詢條件: (過期時間, 結果)}
_name_cache = {}  # {原文飯店名稱: 中文譯名}，同一間飯店不重複翻譯
_NAME_FILE = os.path.join(os.path.dirname(__file__), "database", "hotel_names_zh.json")
try:  # 之前翻好的譯名(重啟後還在)
    with open(_NAME_FILE, encoding="utf-8") as _f:
        _name_cache.update(json.load(_f))
except (OSError, ValueError):
    pass


def _save_names():
    try:
        with open(_NAME_FILE, "w", encoding="utf-8") as f:
            json.dump(_name_cache, f, ensure_ascii=False, indent=0, sort_keys=True)
    except OSError:
        pass  # 存不下來就算了，下次再翻
_translate_retry_at = 0  # 翻譯服務失敗(例如沒開通)後，10 分鐘內不再重試，避免每次搜尋都白打一次
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"

PROPERTY_TYPE_LABELS = {"hotel": "飯店", "vacation rental": "度假租屋"}
TRANSPORT_LABELS = {"walking": "步行", "taxi": "計程車", "public transport": "大眾運輸", "driving": "開車", "bicycling": "騎自行車"}

# Google 回傳的設施名稱中英混雜，這裡統一轉成中文；沒有對應、也不是中文的設施就不顯示，避免畫面出現英文
AMENITY_LABELS = {
    "free wi-fi": "免費 Wi-Fi", "wi-fi": "Wi-Fi", "kid-friendly": "親子友善", "parking ($)": "停車場（收費）",
    "free parking": "免費停車", "parking": "停車場", "restaurant": "餐廳", "accessible": "無障礙設施", "bar": "酒吧",
    "public bath": "大眾浴池", "open air bath": "露天浴池", "pool": "游泳池", "outdoor pool": "室外游泳池",
    "indoor pool": "室內游泳池", "hot tub": "按摩浴缸", "spa": "SPA", "fitness center": "健身中心",
    "air-conditioned": "空調", "breakfast": "早餐", "free breakfast": "免費早餐", "breakfast ($)": "早餐（收費）",
    "pet-friendly": "可攜帶寵物", "airport shuttle": "機場接送", "free airport shuttle": "免費機場接送",
    "kitchen in some rooms": "部分客房有廚房", "kitchen": "廚房", "laundry service": "洗衣服務",
    "beach access": "海灘", "room service": "客房服務", "business center": "商務中心", "smoke-free": "全面禁菸",
    "full-service laundry": "洗衣服務", "water park": "水上樂園",
}



def _safe(error):
    """錯誤訊息的網址常帶著 API 金鑰(?key=...)，印到終端機前先遮掉。"""
    return re.sub(r"(api_key|key)=[^&\s'\")]+", lambda m: m.group(1) + "=***", str(error))

def is_configured():
    return bool(SERPAPI_HOTELS_API_KEY)


def _has_cjk(text):
    return any("一" <= ch <= "鿿" for ch in text)


def _amenity_label(raw):
    mapped = AMENITY_LABELS.get(raw.strip().lower())
    if mapped:
        return mapped
    return raw.strip() if _has_cjk(raw) else None


def _amenity_flags(raw_amenities):
    # 「熱門篩選條件」用：從 Google 回傳的原始設施名稱判斷有沒有停車位、早餐、可帶寵物
    flags = set()
    for raw in raw_amenities:
        low = raw.strip().lower()
        if "parking" in low or "停車" in low:
            flags.add("parking")
        if low in ("breakfast", "free breakfast") or ("早餐" in low and "收費" not in low and "$" not in low):
            flags.add("breakfast")
        if "pet" in low or "寵物" in low:
            flags.add("pets")
        if low == "kid-friendly" or "親子" in low:
            flags.add("kids")
    return sorted(flags)


def _parse_detail(item, images, amenities, rating, per_night, total):
    # 詳情視窗要用的資料：搜尋結果本來就有，不需要再打 API。全部是可以直接轉成 JSON 的基本型別
    nearby = []
    for place in item.get("nearby_places") or []:
        name = place.get("name") or ""
        if not _has_cjk(name):  # 英文地名不顯示，避免畫面出現英文
            continue
        ways = [{"label": TRANSPORT_LABELS.get((t.get("type") or "").lower(), ""), "duration": t.get("duration") or ""}
                for t in place.get("transportations") or []]
        nearby.append({"name": name, "ways": [w for w in ways if w["label"] and w["duration"]]})
    topics = []
    for topic in item.get("reviews_breakdown") or []:
        name = topic.get("name") or ""
        total_mentioned = topic.get("total_mentioned") or 0
        if _has_cjk(name) and total_mentioned:
            topics.append({"name": name, "positive": topic.get("positive") or 0,
                           "negative": topic.get("negative") or 0, "total": total_mentioned})
    coords = item.get("gps_coordinates") or {}
    return {
        "name": item.get("name") or "",
        "address": item.get("address") or "",
        "place_id": item.get("place_id") or "",
        "description": item.get("description") or "",
        "images": [img["full"] for img in images],
        "amenities": amenities,
        "rating": rating,
        "reviews": item.get("reviews") or 0,
        "location_rating": round(float(item["location_rating"]), 1) if item.get("location_rating") else None,
        "rating_counts": [{"stars": r.get("stars"), "count": r.get("count") or 0} for r in item.get("ratings") or []],
        "topics": topics,
        "nearby": nearby,
        "check_in_time": item.get("check_in_time") or "",
        "check_out_time": item.get("check_out_time") or "",
        "website_url": item.get("link") or "",
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
        "star": item.get("extracted_hotel_class"),
        "property_type": PROPERTY_TYPE_LABELS.get(item.get("type"), "其他住宿"),
        "price": float(per_night),
        "total_price": float(total) if total else None,
        "property_token": item.get("property_token") or "",
    }


def _translate_gemini(names):
    """用 Gemini 一次翻一批飯店名稱(每批 25 個)：品牌用台灣通用譯名，地名譯成中文，沒有通用譯名的專有名詞音譯。
    Gemini 沒設定或失敗就略過，由下一個備案接手。"""
    try:
        from ai_client import AIUnavailable, ai_ready, ask_json
    except ImportError:
        return
    if not ai_ready():
        return
    for start in range(0, len(names), 25):
        batch = names[start:start + 25]
        prompt = (
            "把下面的飯店名稱翻成繁體中文(台灣用語)。規則：知名連鎖品牌用台灣通用譯名(Hilton 希爾頓、Marriott 萬豪、Hyatt 凱悅、"
            "Holiday Inn 假日酒店、Ibis 宜必思、Novotel 諾富特、Sheraton 喜來登、Radisson 麗笙)；地名翻成中文；"
            "沒有通用譯名的專有名詞(人名、獨立飯店名)用音譯並保留「飯店」「酒店」「旅館」「民宿」等類別字；"
            "原名已經有中文的保持不變；不要加解釋。只回傳一個 JSON 物件，鍵是原名(必須跟輸入完全一樣)，值是中文譯名。\n"
            + json.dumps(batch, ensure_ascii=False)
        )
        try:
            result = ask_json(prompt, timeout=45)
        except AIUnavailable as error:
            print("飯店名稱 Gemini 翻譯失敗：", error)
            return
        except Exception as error:
            print("飯店名稱 Gemini 翻譯失敗：", _safe(error))
            return
        for original in batch:
            zh = result.get(original)
            if isinstance(zh, str) and _has_cjk(zh) and len(zh) <= 80:
                _name_cache[original] = zh.strip()


def _translate_free(names):
    """備案：Google 翻譯網頁版使用的免金鑰接口(非官方，沒有保證，Google 隨時可能限流或停用)。
    只在官方的 Cloud Translation 沒開通或失敗時才用；一個名稱打一次，用 8 條執行緒同時翻，結果記在 _name_cache。"""
    def one(name):
        try:
            resp = requests.get("https://translate.googleapis.com/translate_a/single",
                                params={"client": "gtx", "sl": "en", "tl": "zh-TW", "dt": "t", "q": name}, timeout=8)
            resp.raise_for_status()
            text = "".join(segment[0] for segment in resp.json()[0] if segment and segment[0])
            return name, text if _has_cjk(text) else None
        except Exception as error:
            print("飯店名稱備用翻譯失敗(維持原名)：", name, _safe(error))
            return name, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, zh in pool.map(one, names):
            if zh:
                _name_cache[name] = zh


def translate_names(hotels):
    """Google 只給英文名稱的飯店，翻成繁體中文：先用 Google Cloud Translation(同一個專案的 Google 金鑰)，
    沒開通或失敗就改用免金鑰的備用接口。譯名是機器翻譯，可能和飯店官方中文名不同，
    所以原名保留在 original_name(詳情視窗會顯示)。全部失敗時維持原名，不影響搜尋結果。"""
    global _translate_retry_at
    pending = sorted({h["name"] for h in hotels if h["name"] and not _has_cjk(h["name"]) and h["name"] not in _name_cache})
    if pending and GOOGLE_MAPS_API_KEY and time.time() >= _translate_retry_at:
        try:
            resp = requests.post(TRANSLATE_URL, params={"key": GOOGLE_MAPS_API_KEY},
                                 json={"q": pending, "source": "en", "target": "zh-TW", "format": "text"}, timeout=20)
            resp.raise_for_status()
            translated = [t["translatedText"] for t in resp.json()["data"]["translations"]]
            for original, zh in zip(pending, translated):
                _name_cache[original] = html.unescape(zh)
        except Exception as error:
            print("飯店名稱官方翻譯失敗(改用備用接口)：", _safe(error))
            _translate_retry_at = time.time() + 600
    pending = [name for name in pending if name not in _name_cache]
    had_pending = bool(pending)
    if pending:
        _translate_gemini(pending)
    pending = [name for name in pending if name not in _name_cache]
    if pending:
        _translate_free(pending)
    if had_pending:
        _save_names()
    for hotel in hotels:
        zh = _name_cache.get(hotel["name"])
        if zh and zh != hotel["name"]:
            hotel["original_name"] = hotel["name"]
            hotel["name"] = zh
            hotel["detail"]["original_name"] = hotel["original_name"]
            hotel["detail"]["name"] = zh


_translate_names = translate_names


def _price(block):
    if not block:
        return None
    value = block.get("extracted_lowest") or block.get("extracted_display_price")
    return Decimal(str(value)) if value else None


def _parse_property(item):
    per_night = _price(item.get("rate_per_night"))
    if per_night is None:
        return None
    rating = item.get("overall_rating")
    rating = round(float(rating), 1) if rating else None  # Google 的評分本來就是 5 分制
    amenities = []
    for raw in item.get("amenities") or []:
        label = _amenity_label(raw)
        if label and label not in amenities:
            amenities.append(label)
    images = [
        {"thumb": img.get("thumbnail") or img.get("original_image"), "full": img.get("original_image") or img.get("thumbnail")}
        for img in (item.get("images") or [])[:9] if img.get("thumbnail") or img.get("original_image")
    ]
    coords = item.get("gps_coordinates") or {}
    deal = item.get("deal") or ""
    total_price = _price(item.get("total_rate"))
    return {
        "name": item.get("name") or "",
        "description": item.get("description") or "",
        "images": images,
        "price": per_night,
        "total_price": total_price,
        "flags": _amenity_flags(item.get("amenities") or []),
        "detail": _parse_detail(item, images, amenities, rating, per_night, total_price),
        "rating": rating,
        "reviews": item.get("reviews") or 0,
        "star": item.get("extracted_hotel_class"),
        "property_type": PROPERTY_TYPE_LABELS.get(item.get("type"), "其他住宿"),
        "amenities": amenities,
        "deal": deal if _has_cjk(deal) else "",
        "website_url": item.get("link") or "",
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
        "check_in_time": item.get("check_in_time") or "",
        "check_out_time": item.get("check_out_time") or "",
    }


def _guest_params(adults, child_ages):
    # SerpApi 沒有「房間數」參數；兒童要用 children + children_ages(1~17 歲，數量要一致)
    params = {"adults": adults}
    if child_ages:
        params["children"] = len(child_ages)
        params["children_ages"] = ",".join(str(age) for age in child_ages)
    return params


def search_hotels(destination, check_in, check_out, adults=2, page_token=None, child_ages=None):
    """搜尋住宿。「城市 國家」(例如「馬斯喀特 阿曼」)Google 有時會因為國名有歧義(阿曼被當成約旦的安曼)而完全搜不到，
    這種情況自動改用只有城市名再搜一次。"""
    result = _search_hotels_once(destination, check_in, check_out, adults, page_token, child_ages)
    if (not result or not result.get("hotels")) and not page_token and " " in (destination or "").strip():
        city_only = destination.strip().split(" ")[0]
        if city_only:
            retry = _search_hotels_once(city_only, check_in, check_out, adults, page_token, child_ages)
            if retry and retry.get("hotels"):
                return retry
    return result


def _search_hotels_once(destination, check_in, check_out, adults=2, page_token=None, child_ages=None):
    """回傳 {"hotels": [...], "next_page_token": str|None}；沒金鑰、沒日期、查詢失敗都回傳 None。
    價格一律是台幣：price 是每晚、total_price 是整段住宿總價。"""
    if not is_configured() or not destination or not check_in or not check_out:
        return None

    child_ages = tuple(child_ages or ())
    cache_key = (destination, check_in, check_out, adults, child_ages, page_token or "")
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]

    query = destination if any(word in destination for word in ("飯店", "住宿", "旅館", "民宿", "hotel", "Hotel")) else f"{destination} 飯店"
    params = {
        "engine": "google_hotels", "api_key": SERPAPI_HOTELS_API_KEY, "q": query,
        "check_in_date": check_in, "check_out_date": check_out,
        "currency": "TWD", "hl": "zh-tw", "gl": "tw", **_guest_params(adults, child_ages),
    }
    if page_token:
        params["next_page_token"] = page_token

    result = None
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            print("SerpApi 住宿查詢回傳錯誤：", data["error"])
        else:
            hotels = [h for h in (_parse_property(p) for p in data.get("properties") or []) if h]
            _translate_names(hotels)
            result = {
                "hotels": hotels,
                "next_page_token": (data.get("serpapi_pagination") or {}).get("next_page_token"),
            }
    except Exception as error:
        print("SerpApi 住宿查詢失敗：", _safe(error))

    if result is not None:
        _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, result)
    return result


def _property_data(property_token, destination, check_in, check_out, adults, child_ages):
    """單一飯店的完整資料(各網站報價、各面向評價統計⋯)，用掉 1 次額度、快取一小時。
    「比價」和「評價整理」共用這一次查詢，不會各花一次額度。失敗回傳 None。"""
    child_ages = tuple(child_ages or ())
    cache_key = ("property", property_token, check_in, check_out, adults, child_ages)
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]
    params = {
        "engine": "google_hotels", "api_key": SERPAPI_HOTELS_API_KEY, "q": f"{destination} 飯店",
        "check_in_date": check_in, "check_out_date": check_out,
        "currency": "TWD", "hl": "zh-tw", "gl": "tw", "property_token": property_token, **_guest_params(adults, child_ages),
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as error:
        print("SerpApi 住宿詳細資料查詢失敗：", _safe(error))
        return None
    if data.get("error"):
        print("SerpApi 住宿詳細資料查詢回傳錯誤：", data["error"])
        return None
    _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, data)
    return data


def get_offers(property_token, destination, check_in, check_out, adults=2, child_ages=None):
    """單一飯店在各訂房網站(官網、Booking.com、Agoda⋯)的價格與訂房連結，每次呼叫用掉 1 次額度，結果快取一小時。
    回傳依每晚價格由低到高排序的清單；沒金鑰或查詢失敗回傳 None。"""
    if not is_configured() or not property_token:
        return None
    data = _property_data(property_token, destination, check_in, check_out, adults, child_ages)
    if data is None:
        return None
    # 列表上的「最低價」取自 Google 的精選報價(featured_prices)，完整比價清單(prices)有時沒有那一家，
    # 所以兩份合併，同一個網站只留最低的一筆，這樣清單最低價才會跟列表上看到的價格一致
    best_by_source = {}
    for item in (data.get("featured_prices") or []) + (data.get("prices") or []):
        price = _price(item.get("rate_per_night"))
        if price is None or not item.get("link"):
            continue
        total = _price(item.get("total_rate"))
        until = " ".join(part for part in (item.get("free_cancellation_until_date"), item.get("free_cancellation_until_time")) if part)
        offer = {
            "source": item.get("source") or "",
            "official": bool(item.get("official")),
            "price": float(price),
            "total_price": float(total) if total else None,
            "free_cancellation": bool(item.get("free_cancellation")),
            "free_until": until,
            "link": item["link"],
        }
        key = offer["source"].lower() or offer["link"]
        if key not in best_by_source or offer["price"] < best_by_source[key]["price"]:
            best_by_source[key] = offer
    return sorted(best_by_source.values(), key=lambda o: o["price"])


def get_review_overview(property_token, destination, check_in, check_out, adults=2, child_ages=None):
    """住客評價總覽：星等分布，以及 Google 整理好的各面向統計(浴室、清潔、服務⋯各有幾則好評、幾則待改善)。
    每個面向帶 token，可以用來只查該面向的留言。沒金鑰或查詢失敗回傳 None。"""
    if not is_configured() or not property_token:
        return None
    data = _property_data(property_token, destination, check_in, check_out, adults, child_ages)
    if data is None:
        return None
    ratings = [{"stars": r["stars"], "count": r.get("count") or 0} for r in data.get("ratings") or [] if r.get("stars")]
    topics = []
    for item in data.get("reviews_breakdown") or []:
        total = item.get("total_mentioned") or 0
        if not item.get("name") or not total:
            continue
        topics.append({
            "name": item["name"], "total": total,
            "positive": item.get("positive") or 0, "negative": item.get("negative") or 0, "neutral": item.get("neutral") or 0,
            "token": item.get("category_token") or "",
        })
    topics.sort(key=lambda t: -t["total"])
    return {"ratings": sorted(ratings, key=lambda r: -r["stars"]), "topics": topics}


def get_reviews(property_token, page_token=None, category_token=None):
    """某間飯店的 Google 住客評論(中文、含星等、日期、全文與飯店回覆)，每次呼叫(含下一頁)用掉 1 次額度，快取一小時。
    回傳 {"reviews": [...], "next_page_token": str|None}；沒金鑰或查詢失敗回傳 None。"""
    if not is_configured() or not property_token:
        return None
    cache_key = ("reviews", property_token, page_token or "", category_token or "")
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]

    params = {"engine": "google_hotels_reviews", "api_key": SERPAPI_HOTELS_API_KEY, "property_token": property_token, "hl": "zh-tw", "gl": "tw"}
    if page_token:
        params["next_page_token"] = page_token
    if category_token:
        params["category_token"] = category_token  # 只查某個面向(清潔、服務⋯)的留言
    result = None
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            print("SerpApi 住宿評論查詢回傳錯誤：", data["error"])
        else:
            reviews = []
            for item in data.get("reviews") or []:
                text = (item.get("snippet") or item.get("extracted_snippet", {}).get("original") or "").strip()
                if not text:
                    continue
                reviews.append({
                    "name": (item.get("user") or {}).get("name") or "匿名住客",
                    "rating": item.get("rating"),
                    "date": item.get("date") or "",
                    "text": text,
                    "reply": ((item.get("response") or {}).get("snippet") or "").strip(),
                    "source": item.get("source") or "Google",
                })
            result = {"reviews": reviews, "next_page_token": (data.get("serpapi_pagination") or {}).get("next_page_token")}
    except Exception as error:
        print("SerpApi 住宿評論查詢失敗：", _safe(error))

    if result is not None:
        _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, result)
    return result
