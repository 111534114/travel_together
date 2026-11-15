"""串接交通部 TDX 運輸資料流通服務，取得高鐵／台鐵「指定日期」的真實班表與票價。

TDX 免費會員的金鑰每分鐘只能呼叫 5 次 API，所以每次查到的資料都會存進 tdx_cache/ 資料夾
(班表 6 小時、票價與車站 7 天)，重開伺服器也不用重查，同一條路線第二次搜尋就完全不打 API。

沒有設定 TDX_CLIENT_ID / TDX_CLIENT_SECRET、站名對不到、或 API 查詢失敗(例如超過次數限制)時，
search_trains 回傳 None，呼叫端（app.py）就改用本地資料庫的 trains 資料表，不會讓網站整個掛掉。
TDX 不提供台鐵剩餘座位，也沒有訂票 API，所以 seats_available 一律是 None，訂票改連到官網的時刻查詢頁
(已帶入起訖站與日期)。
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode
import hashlib
import json
import os
import time

import requests
import truststore  # 改用作業系統原生憑證庫驗證 SSL，修正 Python 3.13 誤判高鐵官網(TWCA憑證)憑證無效的已知問題
truststore.inject_into_ssl()

from config import TDX_CLIENT_ID, TDX_CLIENT_SECRET

TOKEN_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
API_BASE = "https://tdx.transportdata.tw/api/basic"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tdx_cache")
TIMETABLE_TTL_SECONDS = 6 * 3600
FARE_TTL_SECONDS = 7 * 86400
STATION_TTL_SECONDS = 7 * 86400
TAIPEI_TZ = timezone(timedelta(hours=8))

# 官網時刻查詢頁：台鐵可以直接用網址參數帶入起訖站與日期；高鐵要先把條件送到官網的
# /TimeTable/Encrypt 加密(高鐵官網首頁的搜尋按鈕也是這樣做)，再帶 ?search=<密文> 打開時刻表頁
TRA_TIMETABLE_URL = "https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytime"
THSR_TIMETABLE_URL = "https://www.thsrc.com.tw/ArticleContent/a3b630bb-1066-4352-a1ef-58c7b4e8ef7c"
THSR_ENCRYPT_URL = "https://www.thsrc.com.tw/TimeTable/Encrypt"

# 高鐵只有 12 站而且幾乎不會變動，直接寫死，省下一次 API 呼叫
THSR_STATIONS = {
    "南港": "0990", "台北": "1000", "板橋": "1010", "桃園": "1020", "新竹": "1030", "苗栗": "1035",
    "台中": "1040", "彰化": "1043", "雲林": "1047", "嘉義": "1050", "台南": "1060", "左營": "1070",
}
THSR_ALIASES = {"高雄": "左營", "新左營": "左營"}  # 使用者輸入「高雄」時，高鐵要查左營站
# 高鐵官網時刻表頁用的站名代碼
THSR_WEB_CODES = {
    "0990": "NanGang", "1000": "TaiPei", "1010": "BanQiao", "1020": "TaoYuan", "1030": "XinZhu", "1035": "MiaoLi",
    "1040": "TaiZhong", "1043": "ZhangHua", "1047": "YunLin", "1050": "JiaYi", "1060": "TaiNan", "1070": "ZuoYing",
}

# 高鐵票價的 CabinClass：1=標準車廂 2=商務車廂 3=自由座(這裡只列跟本地資料表一致的兩種)
THSR_CABIN_LABELS = {1: "標準車廂", 2: "商務車廂"}

# 台鐵時刻表的 TrainTypeCode，跟票價資料的 TrainType 是同一組代碼(用台北-台中票價實際對照過)
TRA_TYPE_LABELS = {
    "1": "太魯閣號", "2": "普悠瑪號", "3": "自強號", "4": "莒光號", "5": "復興號",
    "6": "區間車", "7": "普快車", "10": "區間快車", "11": "自強號(3000)",
}

_memory_cache = {}  # {api_path: (expires_at, data)}
_token = {"value": None, "expires_at": 0}
_thsr_url_cache = {}  # {加密前的查詢條件: 官網時刻表網址}


def is_configured():
    return bool(TDX_CLIENT_ID and TDX_CLIENT_SECRET)


def search_trains(origin_keyword, destination_keyword, travel_date=None, rail=None):
    """回傳指定日期的高鐵＋台鐵車次清單(格式跟本地 trains 資料表一致，可以直接丟給 train_search.html)。
    rail 給 "thsr" 或 "tra" 就只查那個系統，其他值兩個都查。
    兩個系統都對不到站名或都查詢失敗就回傳 None，呼叫端要自己 fallback；只有其中一個失敗就回傳另一個的結果。"""
    if not is_configured() or not origin_keyword or not destination_keyword:
        return None
    travel_date = travel_date or datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")

    searches = {"thsr": (_search_thsr,), "tra": (_search_tra,)}.get(rail, (_search_thsr, _search_tra))
    results = None
    for search in searches:
        try:
            rows = search(origin_keyword, destination_keyword, travel_date)
        except Exception as error:
            print("TDX 車次查詢失敗：", error)
            continue
        if rows is not None:
            results = (results or []) + rows
    if results is not None:
        results.sort(key=lambda row: row["departure_time"])
    return results


def search_stations(keyword, limit=12, rail=None):
    """給車站輸入框自動完成用：回傳 [{"name": "台北", "systems": ["高鐵", "台鐵"]}, ...]，
    完全相同的站名排最前面、開頭相同的其次、包含關鍵字的最後。台鐵車站清單查不到時只回傳高鐵車站。
    rail 給 "thsr" 或 "tra" 就只列那個系統的車站。"""
    keyword = _normalize_station(keyword)
    if not keyword:
        return []
    tra_names = set()
    if rail != "thsr":
        try:
            tra_names = set(_tra_stations()) if is_configured() else set()
        except Exception as error:
            print("TDX 台鐵車站清單查詢失敗：", error)
    thsr_names = set() if rail == "tra" else set(THSR_STATIONS) | set(THSR_ALIASES)
    matches = []
    for name in thsr_names | tra_names:
        if keyword not in name or "-" in name:  # 「台北-環島」這類是環島列車專用的虛擬站名，不給使用者選
            continue
        systems = [label for label, names in (("高鐵", thsr_names & set(THSR_STATIONS)), ("台鐵", tra_names)) if name in names]
        if name in THSR_ALIASES and name in thsr_names:  # 例如搜尋「高雄」，高鐵會查左營站，提示使用者
            systems.insert(0, f"高鐵{THSR_ALIASES[name]}站")
        rank = 0 if name == keyword else 1 if name.startswith(keyword) else 2
        matches.append((rank, len(name), name, systems))
    matches.sort()
    return [{"name": name, "systems": systems} for _, _, name, systems in matches[:limit]]


def _normalize_station(name):
    name = name.strip().replace("臺", "台")
    for prefix in ("高鐵", "台鐵"):
        name = name.removeprefix(prefix)
    for suffix in ("火車站", "車站", "站"):
        name = name.removesuffix(suffix)
    return name


def _search_thsr(origin_keyword, destination_keyword, travel_date):
    origin_name = _normalize_station(origin_keyword)
    destination_name = _normalize_station(destination_keyword)
    origin = THSR_STATIONS.get(THSR_ALIASES.get(origin_name, origin_name))
    destination = THSR_STATIONS.get(THSR_ALIASES.get(destination_name, destination_name))
    if not origin or not destination or origin == destination:
        return None

    timetable = _api_get(f"/v2/Rail/THSR/DailyTimetable/OD/{origin}/to/{destination}/{travel_date}", TIMETABLE_TTL_SECONDS)
    if not timetable:
        return []
    # 高鐵去回程票價相同，固定用站號小的當起點查，來回兩個方向共用同一份快取
    fare_rows = _api_get(f"/v2/Rail/THSR/ODFare/{min(origin, destination)}/to/{max(origin, destination)}", FARE_TTL_SECONDS)
    prices = {}
    for record in fare_rows or []:
        for fare in record.get("Fares", []):
            if fare.get("TicketType") == 1 and fare.get("FareClass") == 1:  # 單程票、全票
                prices[fare.get("CabinClass")] = fare.get("Price")

    rows = []
    for item in timetable:
        try:
            train_no = item["DailyTrainInfo"]["TrainNo"]
            departure = item["OriginStopTime"]["DepartureTime"]
            arrival = item["DestinationStopTime"]["ArrivalTime"]
            # 高鐵官網網址要呼叫官網加密，等使用者按下按鈕才產生，這裡只先記下查詢條件
            official_query = {"from": origin, "to": destination, "date": travel_date, "time": departure}
            for cabin, label in THSR_CABIN_LABELS.items():
                if prices.get(cabin) is None:
                    continue
                rows.append(_row("thsr", train_no, label, item["OriginStopTime"]["StationName"]["Zh_tw"],
                                 item["DestinationStopTime"]["StationName"]["Zh_tw"], departure, arrival,
                                 prices[cabin], None, cabin, official_query))
        except (KeyError, TypeError):
            continue
    return rows


def _search_tra(origin_keyword, destination_keyword, travel_date):
    stations = _tra_stations()
    origin = stations.get(_normalize_station(origin_keyword))
    destination = stations.get(_normalize_station(destination_keyword))
    if not origin or not destination or origin == destination:
        return None

    timetable = _api_get(f"/v3/Rail/TRA/DailyTrainTimetable/OD/{origin}/to/{destination}/{travel_date}", TIMETABLE_TTL_SECONDS)
    trains = (timetable or {}).get("TrainTimetables") or []
    if not trains:
        return []
    prices = _tra_prices(origin, destination)

    rows = []
    for item in trains:
        try:
            info = item["TrainInfo"]
            if info.get("SuspendedFlag"):  # 停駛車次不顯示
                continue
            first_stop, last_stop = item["StopTimes"][0], item["StopTimes"][-1]
            type_code = str(info["TrainTypeCode"])
            # 台鐵同一種車在不同路線(例如台北到台中走西部或繞東部)票價不同，要用車次的行駛方向對票價
            price = prices.get((type_code, info.get("Direction")))
            if price is None:
                price = min((p for (code, _), p in prices.items() if code == type_code), default=None)
            if price is None:
                continue
            label = TRA_TYPE_LABELS.get(type_code) or info["TrainTypeName"]["Zh_tw"].split("(")[0]
            booking_url = tra_timetable_url(first_stop["StationID"], first_stop["StationName"]["Zh_tw"],
                                            last_stop["StationID"], last_stop["StationName"]["Zh_tw"],
                                            travel_date, first_stop["DepartureTime"])
            rows.append(_row("tra", info["TrainNo"], label, first_stop["StationName"]["Zh_tw"],
                             last_stop["StationName"]["Zh_tw"], first_stop["DepartureTime"],
                             last_stop["ArrivalTime"], price, booking_url))
        except (KeyError, IndexError, TypeError):
            continue
    return rows


def _tra_stations():
    """回傳 {正規化站名: 站號}，例如 {"台北": "1000"}。"""
    data = _api_get("/v3/Rail/TRA/Station", STATION_TTL_SECONDS)
    return {_normalize_station(s["StationName"]["Zh_tw"]): s["StationID"] for s in data.get("Stations", [])}


def _tra_prices(origin, destination):
    """回傳 {(車種代碼, 行駛方向): 全票價}。
    台鐵票價也是去回程相同，固定用站號小的當起點查來共用快取；反方向查時，車次的行駛方向
    (0=順行 1=逆行)剛好相反，所以要把票價資料裡的方向對調。"""
    reverse = origin > destination
    low, high = (destination, origin) if reverse else (origin, destination)
    data = _api_get(f"/v3/Rail/TRA/ODFare/{low}/to/{high}", FARE_TTL_SECONDS)
    prices = {}
    for record in data.get("ODFares", []):
        direction = record.get("Direction")
        if reverse and direction in (0, 1):
            direction = 1 - direction
        for fare in record.get("Fares", []):
            if fare.get("TicketType") == 1 and fare.get("FareClass") == 1:
                prices[(str(record.get("TrainType")), direction)] = fare.get("Price")
    return prices


def tra_timetable_url(origin_id, origin_name, destination_id, destination_name, travel_date, start_time="00:00"):
    """台鐵官網時刻查詢結果頁網址，從這班車的出發時間開始列，使用者一打開就看到這班車。"""
    return TRA_TIMETABLE_URL + "?" + urlencode({
        "startStation": f"{origin_id}-{origin_name}",
        "endStation": f"{destination_id}-{destination_name}",
        "transfer": "ONE",
        "rideDate": travel_date.replace("-", "/"),
        "startOrEndTime": "true",
        "startTime": start_time,
        "endTime": "23:59",
        "trainTypeList": "ALL",
        "queryClassification": "NORMAL",
    })


def thsr_timetable_url(origin_id, destination_id, travel_date, start_time):
    """高鐵官網時刻表頁網址(已帶入起訖站、日期、時間)。官網加密失敗時，回傳沒有帶條件的時刻表頁。"""
    origin_code = THSR_WEB_CODES.get(origin_id)
    destination_code = THSR_WEB_CODES.get(destination_id)
    if not origin_code or not destination_code:
        return THSR_TIMETABLE_URL
    # 格式跟高鐵官網首頁搜尋按鈕組出來的字串一模一樣，官網時刻表頁才解得開
    plain_text = (f"?startStation={origin_code}&endStation={destination_code}&typesofticket=tot-1"
                  f"&outWardDate={travel_date.replace('-', '/')}&outWardTime={start_time}&returnDate=&returnTime=&offer=")
    if plain_text in _thsr_url_cache:
        return _thsr_url_cache[plain_text]
    try:
        resp = requests.post(THSR_ENCRYPT_URL, data={"plainText": plain_text}, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success") or not result.get("cipherText"):
            return THSR_TIMETABLE_URL
        # 密文要原封不動接在網址後面(跟高鐵官網首頁一樣)：官網時刻表頁直接拿網址字串去解密、不會先解碼，
        # 把 + / = 編碼成 %2B %2F %3D 的話官網會解密失敗，只顯示預設的南港→左營
        url = THSR_TIMETABLE_URL + "?search=" + result["cipherText"]
    except (requests.RequestException, ValueError) as error:
        print("高鐵官網時刻表網址加密失敗：", error)
        return THSR_TIMETABLE_URL
    _thsr_url_cache[plain_text] = url
    return url


def _row(train_type, train_no, car_class, origin_station, destination_station, departure, arrival, price, booking_url, cabin="", official_query=None):
    depart_at = datetime.strptime(departure, "%H:%M")
    arrive_at = datetime.strptime(arrival, "%H:%M")
    duration = int((arrive_at - depart_at).total_seconds() // 60)
    if duration < 0:  # 跨夜車次
        duration += 24 * 60
    return {
        "train_id": f"tdx-{train_type}-{train_no}-{cabin}",
        "train_type": train_type,
        "train_number": train_no,
        "car_class": car_class,
        "origin_station": origin_station,
        "destination_station": destination_station,
        "departure_time": departure,
        "arrival_time": arrival,
        "duration_minutes": duration,
        "price": Decimal(str(price)),  # 跟本地資料庫的 DECIMAL 價格型別一致，篩選/排序時才不會 float 對 Decimal 出錯
        "seats_available": None,  # TDX 不提供台鐵剩餘座位，不要顯示假數字
        "is_live": True,
        "booking_url": booking_url,
        "official_query": official_query,
    }


def _api_get(path, ttl):
    """先查記憶體快取、再查 tdx_cache/ 檔案快取，都沒有才真的呼叫 TDX API。"""
    now = time.time()
    cached = _memory_cache.get(path)
    if cached and cached[0] > now:
        return cached[1]

    cache_file = os.path.join(CACHE_DIR, hashlib.md5(path.encode("utf-8")).hexdigest() + ".json")
    try:
        with open(cache_file, encoding="utf-8") as fh:
            payload = json.load(fh)
        if payload["expires_at"] > now:
            _memory_cache[path] = (payload["expires_at"], payload["data"])
            return payload["data"]
    except (OSError, ValueError, KeyError):
        pass

    resp = requests.get(API_BASE + path, headers={"Authorization": f"Bearer {_access_token()}"},
                        params={"$format": "JSON"}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    expires_at = now + ttl
    _memory_cache[path] = (expires_at, data)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump({"path": path, "expires_at": expires_at, "data": data}, fh, ensure_ascii=False)
    except OSError:
        pass
    return data


def _access_token():
    if _token["value"] and _token["expires_at"] - 60 > time.time():
        return _token["value"]
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": TDX_CLIENT_ID,
        "client_secret": TDX_CLIENT_SECRET,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    _token["value"] = data["access_token"]
    _token["expires_at"] = time.time() + data.get("expires_in", 3600)
    return _token["value"]
