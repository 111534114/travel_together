import time  # 用來記錄快取抓取時間，判斷是否需要重新呼叫 API

import truststore  # 改用作業系統原生憑證庫驗證 SSL，修正 Python 3.13 誤判台灣政府網站(TWCA憑證)憑證無效的已知問題
truststore.inject_into_ssl()

import requests  # 匯入 requests，用來呼叫中央氣象署開放資料 API

from config import CWA_API_KEY  # 匯入中央氣象署開放資料平台的授權碼

# F-D0047-091：中央氣象署「鄉鎮天氣預報-臺灣未來1週天氣預報」資料集，
# 用 LocationName 篩選「臺灣各縣市」時，會回傳該縣市整體一筆資料(不會拆成一堆鄉鎮)，
# 內容是未來 7 天、每 12 小時一筆的天氣現象、最高溫、最低溫等資料。
API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-091"

CACHE_TTL_SECONDS = 6 * 60 * 60  # 快取存活時間(6小時)：這份資料不需要每次訪客進站都重打 API

# 中央氣象署的 WeatherCode 數字代碼沒有公開的文字對照表(官網天氣圖示對照表是圖片，抓不到)，
# 改用天氣現象的文字描述本身判斷 emoji，比較準確也不用維護一份猜測的代碼表。
# 用「關鍵字, emoji」的清單依序比對(由重到輕、由特殊到一般)，符合第一個關鍵字就採用該 emoji。
WEATHER_TEXT_EMOJI = [
    ("雷", "⛈️"),
    ("雪", "❄️"),
    ("霧", "🌫️"),
    ("陣雨", "🌦️"),
    ("大雨", "🌧️"),
    ("雨", "🌧️"),
    ("多雲", "⛅"),
    ("陰", "☁️"),
    ("晴", "☀️"),
]
DEFAULT_EMOJI = "🌡️"  # 找不到符合的關鍵字時使用的預設圖示


def _weather_emoji(weather_text):  # 定義函式：依天氣現象文字描述，判斷對應的 emoji 圖示
    for keyword, emoji in WEATHER_TEXT_EMOJI:  # 依序比對關鍵字(排在前面的優先權較高)
        if keyword in (weather_text or ""):
            return emoji
    return DEFAULT_EMOJI  # 都沒符合就用預設圖示


_cache = {"fetched_at": 0, "data": {}}  # 模組層級的簡單記憶體快取：{正規化後的縣市名: 天氣資料}


class WeatherApiError(Exception):  # 定義自訂例外類別，代表呼叫中央氣象署 API 時發生的錯誤
    pass


def is_configured():  # 定義函式：檢查目前是否已經設定 API 授權碼
    return bool(CWA_API_KEY)  # 授權碼非空字串才算已設定


def normalize_city_name(name):  # 定義函式：統一縣市名稱的用字
    # 氣象署 API 用正式字「臺」(臺北市、臺東縣...)，但我們資料庫存的是常用字「台」(台北市)，
    # 兩者是不同的 Unicode 字元，直接字串比對會比對不到，所以統一轉成「台」再比對。
    return (name or "").replace("臺", "台")


def _fetch_raw():  # 定義函式：呼叫中央氣象署開放資料 API，回傳原始 JSON
    response = requests.get(  # 發送 GET 請求
        API_URL,
        params={  # 網址參數
            "Authorization": CWA_API_KEY,  # 開放資料平台的授權碼
            "format": "JSON",  # 要求回傳 JSON 格式
        },
        timeout=15  # 最多等待 15 秒，避免請求卡住拖慢訪客頁面(這份資料全台灣一次回傳，內容較大)
    )

    if not response.ok:  # 如果 HTTP 狀態碼不是 2xx(代表授權碼錯誤、格式錯誤等)
        raise WeatherApiError(response.text)  # 拋出例外，帶上原始錯誤內容

    return response.json()  # 把回應內容解析成 Python 字典


def _element_value(time_entry, key):  # 定義函式：從單一時間區段裡，取出指定欄位的值
    values = time_entry.get("ElementValue") or []  # ElementValue 是一個只有一筆資料的清單

    if not values:  # 如果沒有值
        return None  # 回傳 None

    return values[0].get(key)  # 取第一筆資料裡指定欄位的值


def _group_periods_by_day(periods):  # 定義函式：把每 12 小時一筆的資料，兩兩(白天+夜晚)合併成一天
    days = []  # 準備回傳用的逐日清單

    for i in range(0, len(periods), 2):  # 每次跳 2 筆，把白天和夜晚合併成一天
        chunk = periods[i:i + 2]  # 取出這一天的 1~2 筆資料(通常是白天+夜晚兩筆)

        if not chunk:  # 保險起見，避免空清單
            continue

        max_values = [p["max"] for p in chunk if p["max"] is not None]  # 收集這天所有的最高溫數值
        min_values = [p["min"] for p in chunk if p["min"] is not None]  # 收集這天所有的最低溫數值
        daytime = chunk[0]  # 用白天(第一筆，通常是 06:00~18:00)代表這一天的天氣現象與圖示

        days.append({
            "date": (daytime["start"] or "")[:10],  # 只取日期部分(例如 2026-09-10)
            "weather": daytime["weather"],  # 天氣現象文字(例如「晴時多雲」)
            "emoji": daytime["emoji"],  # 對應的 emoji 圖示
            "max": max(max_values, key=int) if max_values else None,  # 這一天(白天+夜晚)的最高溫
            "min": min(min_values, key=int) if min_values else None,  # 這一天(白天+夜晚)的最低溫
        })

    return days


def _parse_locations(raw):  # 定義函式：把中央氣象署回傳的原始資料，整理成 {正規化縣市名: 天氣資料} 的字典
    result = {}  # 準備回傳用的字典

    try:  # 資料結構固定但保險起見用 try/except 包起來，避免格式異動時整個網站掛掉
        location_groups = raw["records"]["Locations"]
    except (KeyError, TypeError):  # 如果取不到預期的巢狀結構
        return result  # 回傳空字典

    for group in location_groups:  # 逐一處理每個地區分組(通常只有「臺灣」這一組)
        for location in group.get("Location", []):  # 逐一處理分組底下的每個縣市
            name = location.get("LocationName")  # 取得縣市名稱(例如「花蓮縣」)

            if not name:  # 如果沒有縣市名稱
                continue  # 跳過這筆資料

            elements = {  # 把這個縣市底下的天氣要素，依名稱整理成字典，方便取用
                el.get("ElementName"): el.get("Time", [])
                for el in location.get("WeatherElement", [])
            }
            wx_times = elements.get("天氣現象", [])  # 取得天氣現象(晴、陰、陣雨等)的逐時段資料
            max_times = elements.get("最高溫度", [])  # 取得最高溫的逐時段資料
            min_times = elements.get("最低溫度", [])  # 取得最低溫的逐時段資料

            periods = []  # 準備這個縣市每 12 小時一筆的天氣清單

            for idx, item in enumerate(wx_times):  # 逐時段組合天氣現象、最高溫、最低溫
                weather_text = _element_value(item, "Weather") or ""  # 天氣現象文字(例如「多雲短暫陣雨」)

                periods.append({
                    "start": item.get("StartTime", ""),  # 這個時段的開始時間
                    "weather": weather_text,  # 天氣現象文字
                    "emoji": _weather_emoji(weather_text),  # 依文字描述判斷的 emoji 圖示
                    "max": max_times[idx].get("ElementValue", [{}])[0].get("MaxTemperature") if idx < len(max_times) else None,
                    "min": min_times[idx].get("ElementValue", [{}])[0].get("MinTemperature") if idx < len(min_times) else None,
                })

            if not periods:  # 如果這個縣市完全沒有可用的逐時段資料
                continue  # 跳過

            days = _group_periods_by_day(periods)  # 把逐 12 小時資料合併成逐日資料(通常會是 7 天)

            if not days:  # 如果合併後沒有任何一天的資料
                continue

            result[normalize_city_name(name)] = {  # 用正規化過的名稱當 key，才能跟資料庫的縣市名稱比對
                "location_name": name,  # 氣象署原本的縣市名稱(顯示用)
                "today": days[0],  # 最近一天的天氣，卡片摘要用
                "days": days,  # 完整的逐日清單(通常 7 天)，Modal 完整預報用
            }

    return result  # 回傳整理好的 {正規化縣市名: 天氣資料} 字典


def _get_all_weather():  # 定義函式：取得(必要時重新抓取)全部縣市的天氣資料，內部帶快取
    now = time.time()  # 取得目前時間戳記
    cache_expired = (now - _cache["fetched_at"]) > CACHE_TTL_SECONDS  # 判斷快取是否已經過期

    if cache_expired or not _cache["data"]:  # 如果快取過期，或還沒抓過任何資料
        try:  # 嘗試重新呼叫 API 更新快取
            raw = _fetch_raw()
            _cache["data"] = _parse_locations(raw)
            _cache["fetched_at"] = now
        except Exception as error:  # 如果呼叫失敗(網路問題、授權碼錯誤等)
            print("取得中央氣象署天氣資料失敗：", error)  # 在伺服器端印出錯誤內容方便除錯
            # 呼叫失敗時沿用舊的快取資料(可能是空字典，也可能是之前抓到的資料)，不讓例外往上炸掉頁面

    return _cache["data"]  # 回傳目前快取內容


def get_weather_by_cities(city_names):  # 定義函式：依城市名稱清單，回傳這些城市的天氣資料
    """
    傳入城市名稱清單(例如 ['台北市', '花蓮縣', '東京都'])，回傳 {原始城市名: 天氣資料} 字典。
    只有中央氣象署有資料的台灣縣市才會出現在回傳結果裡，查不到的城市(例如國外城市)會被忽略。
    """
    if not is_configured() or not city_names:  # 如果沒有設定授權碼，或沒有要查的城市
        return {}  # 直接回傳空字典，不呼叫 API

    all_weather = _get_all_weather()  # 取得(或使用快取的)全部縣市天氣資料
    unique_names = list(dict.fromkeys(city_names))  # 去除重複城市名稱，並保留原本的順序

    result = {}  # 準備回傳用的字典(key 用原始城市名，方便前端直接顯示)

    for name in unique_names:  # 逐一檢查每個要查的城市名稱
        key = normalize_city_name(name)  # 正規化後才能跟氣象署的縣市名稱比對

        if key in all_weather:  # 如果氣象署有這個縣市的資料
            result[name] = all_weather[key]  # 用原始名稱當 key，存入回傳結果

    return result  # 回傳查得到資料的城市天氣
