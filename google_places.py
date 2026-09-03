import requests  # 匯入 requests，用來呼叫 Google Places API

from config import GOOGLE_MAPS_API_KEY  # 匯入 Google Places API 金鑰

# 使用「Places API (New)」的文字搜尋端點：一次請求就能拿到地址、經緯度、開放時間、網站等資料，
# 不需要像舊版 Places API 那樣分成「文字搜尋」+「地點詳細資訊」兩次請求。
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"  # Google 地點文字搜尋 API(新版)網址

FIELD_MASK = (  # 定義要跟 Google 要哪些欄位，只要必要欄位可以省流量、省費用
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.websiteUri,places.regularOpeningHours,places.addressComponents,"
    "places.googleMapsUri,places.primaryTypeDisplayName,places.editorialSummary,"
    "places.priceLevel"
)

PRICE_LEVEL_MAP = {  # 定義 Google 價位等級對應到我們資料庫用的價位等級(只有餐廳會用到)
    "PRICE_LEVEL_FREE": "low",
    "PRICE_LEVEL_INEXPENSIVE": "low",
    "PRICE_LEVEL_MODERATE": "medium",
    "PRICE_LEVEL_EXPENSIVE": "high",
    "PRICE_LEVEL_VERY_EXPENSIVE": "luxury",
}


class PlacesApiError(Exception):  # 定義自訂例外類別，代表呼叫 Google Places API 時發生的錯誤
    pass


def is_configured():  # 定義函式：檢查目前是否已經設定 API 金鑰
    return bool(GOOGLE_MAPS_API_KEY)  # 金鑰非空字串才算已設定


def search_place(query):  # 定義函式：用文字搜尋一個地點，回傳最相符的第一筆結果(找不到回傳 None)
    response = requests.post(  # 發送 POST 請求到新版文字搜尋 API(新版 API 一律用 POST + JSON body)
        TEXT_SEARCH_URL,
        headers={  # 新版 API 用 HTTP header 帶金鑰跟欄位遮罩，不是用網址參數
            "Content-Type": "application/json",  # 告知伺服器請求內容是 JSON
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,  # API 金鑰
            "X-Goog-FieldMask": FIELD_MASK,  # 指定要回傳的欄位，避免要到用不到的資料
        },
        json={  # 請求內容(JSON 格式)
            "textQuery": query,  # 使用者輸入的地點名稱/查詢字串
            "languageCode": "zh-TW",  # 要求回傳繁體中文結果，方便跟資料庫既有的中文國家/城市名稱比對
        },
        timeout=10  # 最多等待 10 秒，避免請求卡住
    )

    if not response.ok:  # 如果 HTTP 狀態碼不是 2xx(代表金鑰錯誤、權限不足、格式錯誤等)
        message = response.text  # 預設錯誤訊息為原始回應內容
        try:  # 嘗試把錯誤內容解析成 Google 慣用的錯誤格式
            error_body = response.json().get("error", {})  # 取得錯誤區塊
            message = error_body.get("message", message)  # 取得更精簡的錯誤說明(如果有的話)
        except ValueError:  # 如果回應內容不是合法的 JSON
            pass  # 就沿用原始的錯誤內容
        raise PlacesApiError(message)  # 拋出例外，帶上錯誤說明

    data = response.json()  # 把回應內容解析成 Python 字典
    places = data.get("places") or []  # 取得搜尋結果清單(找不到地點時，Google 會回傳空物件，沒有 places 欄位)

    if not places:  # 如果結果清單是空的
        return None  # 回傳 None，代表找不到符合的地點

    return places[0]  # 回傳相關性最高的第一筆結果


def extract_country_and_city(address_components):  # 定義函式：從 Google 回傳的地址組成裡，抓出國家名稱與城市名稱
    country = None  # 預設國家為 None
    city = None  # 預設城市為 None
    admin_area = None  # 預設「一級行政區」為 None，當作城市抓不到時的備用值

    for component in address_components or []:  # 逐一檢查每個地址組成片段
        types = component.get("types", [])  # 取得這個片段的類型清單(例如 country、locality)
        long_text = component.get("longText")  # 取得這個片段的完整名稱(新版 API 欄位叫 longText)

        if "country" in types:  # 如果這個片段是國家
            country = long_text  # 記錄為國家名稱

        if "locality" in types:  # 如果這個片段是「城市/鄉鎮」層級
            city = long_text  # 記錄為城市名稱

        if "administrative_area_level_1" in types:  # 如果這個片段是「一級行政區」(例如台灣的「台北市」常常是這一層)
            admin_area = long_text  # 記錄下來備用

    return country, (city or admin_area)  # 城市優先用 locality，抓不到才退而求其次用一級行政區


def format_opening_hours(regular_opening_hours):  # 定義函式：把 Google 的開放時間資料轉成單行文字，方便存進資料庫
    if not regular_opening_hours:  # 如果沒有開放時間資料
        return None  # 回傳 None

    weekday_descriptions = regular_opening_hours.get("weekdayDescriptions")  # 取得每天的開放時間文字清單(例如「星期一: 09:00–17:00」)

    if not weekday_descriptions:  # 如果沒有每天的文字資料
        return None  # 回傳 None

    return "；".join(weekday_descriptions)  # 用中文分號把每天的資訊接成一行文字


def extract_place_fields(place):  # 定義函式：把 Google 回傳的單筆地點資料，整理成我們資料庫需要的欄位
    name = (place.get("displayName") or {}).get("text")  # 取得地點名稱(新版 API 巢狀在 displayName.text 裡)
    address = place.get("formattedAddress")  # 取得完整地址
    location = place.get("location") or {}  # 取得地理位置區塊
    latitude = location.get("latitude")  # 取得緯度
    longitude = location.get("longitude")  # 取得經度
    website_url = place.get("websiteUri") or place.get("googleMapsUri")  # 取得官方網站，沒有就用 Google 地圖連結
    opening_hours_text = format_opening_hours(place.get("regularOpeningHours"))  # 把開放時間轉成單行文字
    country_name, city_name = extract_country_and_city(place.get("addressComponents"))  # 解析出國家與城市名稱
    category_name = (place.get("primaryTypeDisplayName") or {}).get("text")  # 取得 Google 判斷的地點類型中文名稱(例如「觀光景點」「博物館」)，當作分類
    description = (place.get("editorialSummary") or {}).get("text")  # 取得 Google 官方簡介(不是每個地點都有)
    price_level = PRICE_LEVEL_MAP.get(place.get("priceLevel"))  # 把 Google 的價位等級轉成我們資料庫用的等級(找不到對應就是 None)

    return {  # 回傳整理好的欄位字典
        "name": name,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "website_url": website_url,
        "opening_hours": opening_hours_text,
        "country_name": country_name,
        "city_name": city_name,
        "category_name": category_name,
        "description": description,
        "price_level": price_level,
    }
