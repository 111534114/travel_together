"""SerpApi 的 Google Hotels 即時住宿搜尋：價格(台幣)、圖片、評分、星級都是 Google Hotels 的真實資料。

每次搜尋(含「下一頁」)都會用掉 1 次 SerpApi 額度，所以同樣的搜尋條件會快取一段時間。
沒有設定金鑰或查詢失敗時回傳 None，呼叫端自己退回資料庫的住宿資料。
"""
import html
import time
from decimal import Decimal

import requests

from config import GOOGLE_MAPS_API_KEY, SERPAPI_HOTELS_API_KEY

SEARCH_URL = "https://serpapi.com/search"
CACHE_TTL_SECONDS = 60 * 60
_cache = {}  # {查詢條件: (過期時間, 結果)}
_name_cache = {}  # {原文飯店名稱: 中文譯名}，同一間飯店不重複翻譯
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


def is_configured():
    return bool(SERPAPI_HOTELS_API_KEY)


def _has_cjk(text):
    return any("一" <= ch <= "鿿" for ch in text)


def _amenity_label(raw):
    mapped = AMENITY_LABELS.get(raw.strip().lower())
    if mapped:
        return mapped
    return raw.strip() if _has_cjk(raw) else None


def _rating_label(score_10):
    if score_10 >= 9:
        return "極佳"
    if score_10 >= 8:
        return "很好"
    if score_10 >= 7:
        return "好"
    return "尚可"


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
    return sorted(flags)


def _parse_detail(item, images, amenities, rating_10, per_night, total):
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
        "rating_10": rating_10,
        "reviews": item.get("reviews") or 0,
        "location_rating": round(float(item["location_rating"]) * 2, 1) if item.get("location_rating") else None,
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


def _translate_names(hotels):
    """Google 只給英文名稱的飯店，用 Google Cloud Translation 翻成繁體中文(同一個專案的 Google 金鑰)。
    譯名是機器翻譯，可能和飯店官方中文名不同，所以原名保留在 original_name(詳情視窗會顯示)。
    翻譯服務沒開通或失敗時維持原名，不影響搜尋結果。"""
    pending = sorted({h["name"] for h in hotels if h["name"] and not _has_cjk(h["name"]) and h["name"] not in _name_cache})
    global _translate_retry_at
    if pending and GOOGLE_MAPS_API_KEY and time.time() >= _translate_retry_at:
        try:
            resp = requests.post(TRANSLATE_URL, params={"key": GOOGLE_MAPS_API_KEY},
                                 json={"q": pending, "source": "en", "target": "zh-TW", "format": "text"}, timeout=20)
            resp.raise_for_status()
            translated = [t["translatedText"] for t in resp.json()["data"]["translations"]]
            for original, zh in zip(pending, translated):
                _name_cache[original] = html.unescape(zh)
        except Exception as error:
            print("飯店名稱翻譯失敗(維持原名)：", error)
            _translate_retry_at = time.time() + 600
    for hotel in hotels:
        zh = _name_cache.get(hotel["name"])
        if zh and zh != hotel["name"]:
            hotel["original_name"] = hotel["name"]
            hotel["name"] = zh
            hotel["detail"]["original_name"] = hotel["original_name"]
            hotel["detail"]["name"] = zh


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
    rating_10 = round(float(rating) * 2, 1) if rating else None
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
        "detail": _parse_detail(item, images, amenities, rating_10, per_night, total_price),
        "rating_10": rating_10,
        "rating_label": _rating_label(rating_10) if rating_10 else "",
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


def search_hotels(destination, check_in, check_out, adults=2, page_token=None):
    """回傳 {"hotels": [...], "next_page_token": str|None}；沒金鑰、沒日期、查詢失敗都回傳 None。
    價格一律是台幣：price 是每晚、total_price 是整段住宿總價。"""
    if not is_configured() or not destination or not check_in or not check_out:
        return None

    cache_key = (destination, check_in, check_out, adults, page_token or "")
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]

    query = destination if any(word in destination for word in ("飯店", "住宿", "旅館", "民宿", "hotel", "Hotel")) else f"{destination} 飯店"
    params = {
        "engine": "google_hotels", "api_key": SERPAPI_HOTELS_API_KEY, "q": query,
        "check_in_date": check_in, "check_out_date": check_out, "adults": adults,
        "currency": "TWD", "hl": "zh-tw", "gl": "tw",
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
        print("SerpApi 住宿查詢失敗：", error)

    if result is not None:
        _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, result)
    return result


def get_offers(property_token, destination, check_in, check_out, adults=2):
    """單一飯店在各訂房網站(官網、Booking.com、Agoda⋯)的價格與訂房連結，每次呼叫用掉 1 次額度，結果快取一小時。
    回傳依每晚價格由低到高排序的清單；沒金鑰或查詢失敗回傳 None。"""
    if not is_configured() or not property_token:
        return None
    cache_key = ("offers", property_token, check_in, check_out, adults)
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]

    params = {
        "engine": "google_hotels", "api_key": SERPAPI_HOTELS_API_KEY, "q": f"{destination} 飯店",
        "check_in_date": check_in, "check_out_date": check_out, "adults": adults,
        "currency": "TWD", "hl": "zh-tw", "gl": "tw", "property_token": property_token,
    }
    result = None
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            print("SerpApi 住宿報價查詢回傳錯誤：", data["error"])
        else:
            offers = []
            for item in data.get("prices") or []:
                price = _price(item.get("rate_per_night"))
                if price is None or not item.get("link"):
                    continue
                total = _price(item.get("total_rate"))
                until = " ".join(part for part in (item.get("free_cancellation_until_date"), item.get("free_cancellation_until_time")) if part)
                offers.append({
                    "source": item.get("source") or "",
                    "official": bool(item.get("official")),
                    "price": float(price),
                    "total_price": float(total) if total else None,
                    "free_cancellation": bool(item.get("free_cancellation")),
                    "free_until": until,
                    "link": item["link"],
                })
            offers.sort(key=lambda o: o["price"])
            result = offers
    except Exception as error:
        print("SerpApi 住宿報價查詢失敗：", error)

    if result is not None:
        _cache[cache_key] = (time.time() + CACHE_TTL_SECONDS, result)
    return result
