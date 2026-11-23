"""全球機場資料（來源：OpenFlights/OurAirports 公開機場資料庫，database/airports_data.csv，
約 6000 筆有 IATA 代碼的真實機場資料：機場名稱、城市、國家、IATA 代碼），不是我們自己編的假清單。

每筆機場資料另外補了 name_zh 欄位：真正的中文機場名稱，來源是維基數據(Wikidata)上每個機場
條目本身就有的中文/繁體中文名稱(不是機器翻譯，是維基百科真的有這篇條目才會有)，用 OpenCC
統一轉成繁體中文。大約 68%(4000+ 筆)的機場有真正的中文名稱，沒有的(通常是很小的地方機場，
中文維基百科根本沒有條目)就是空字串，呼叫端要自己 fallback 顯示英文名稱，不要顯示空白。

用來讓機票搜尋的出發地/目的地支援全世界的城市/機場（不只是 flight_links.py 裡手動整理的
~80 個常見中文城市），中文「城市」名稱還是靠 flight_links.py 的 CITY_IATA/CITY_NAME_EN 對照表處理，
這裡的 name_zh 是「機場」本身的中文名稱(同一個城市常常不只一個機場)。
"""
import csv
import math
import re
import os

_CSV_PATH = os.path.join(os.path.dirname(__file__), "database", "airports_data.csv")
_ROUTES_CSV_PATH = os.path.join(os.path.dirname(__file__), "database", "airports_routes.csv")
# 完整機場清單(所有有定期航班的機場，含只飛國內線的)：只用在「列出某個城市底下的所有機場」，
# 要不要出現這個城市仍然以「有國際機場」為準，所以不會出現沒有國際機場的小城市。
_ALL_CSV_PATH = os.path.join(os.path.dirname(__file__), "database", "airports_all.csv")

# 只飛國內線的台灣小機場：可以搜尋、可以選，但沒有國際航班，查詢時由 flight_links.transfer_hub() 自動改用
# 對應的國際機場(轉運站)出發/抵達，國內段請旅客另外購買。{小機場: 轉運站}
# 有國內線可以接到國際機場的小機場：{小機場: [轉運站，依序嘗試]}，有找到國內航班才會組合成完整行程
DOMESTIC_FEEDERS = {"HUN": ["KHH", "TSA"], "TTT": ["KHH", "TSA"], "KNH": ["TSA", "KHH", "TPE"], "MZG": ["TSA", "KHH"], "LZN": ["TSA"], "MFK": ["TSA"]}
# 小機場在選單裡以「縣市名」顯示(像 Agoda 的「台南市 (TNN)」)，機場名稱放第二行
CITY_LABEL_ZH = {"HUN": "花蓮縣", "TTT": "台東縣", "TNN": "台南市", "KNH": "金門縣", "MZG": "澎湖縣"}
TRANSFER_HUBS = {"HUN": "TPE", "TTT": "KHH", "KNH": "TPE", "MZG": "KHH"}  # 台南(TNN)沒有國內線可接國際機場，不轉運，像 Agoda 一樣直接顯示查無結果

NAME_ZH_OVERRIDES = {}  # 由 flight_links 填入(機場慣用簡稱)，中文搜尋也要比對這些名稱
_airports = []  # [{"iata":..., "city":..., "country":..., "name":..., "name_zh":...}, ...]
_by_iata = {}
_all_by_city = {}  # {(英文城市名小寫, 國家小寫): [airport, ...]}，航線多的排前面


def _load():
    if _airports:
        return
    try:
        with open(_ALL_CSV_PATH if os.path.exists(_ALL_CSV_PATH) else _CSV_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                _fix_name(row)
                if _is_airfield(row):
                    continue
                _airports.append(row)
                _by_iata[row["iata"]] = row
    except OSError:
        pass  # 資料檔不存在就當作沒有全球機場資料，搜尋回傳空清單，不會讓網站掛掉
    try:
        with open(_ROUTES_CSV_PATH, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                airport = _by_iata.get(row["iata"])
                if airport is not None:
                    airport["routes"] = row["routes"]
    except OSError:
        pass  # 航線數只用於國家搜尋；缺少此檔仍可搜尋原有的全球機場


# 維基數據的中文名稱寫成「飛行場」、但其實有國際航班的機場：改用正式名稱收進來，不當作小型飛行場排除
AIRFIELD_RENAMES = {"KMQ": "小松機場", "IBR": "茨城機場", "YGJ": "米子鬼太郎機場"}


def _fix_name(row):
    if row.get("iata") in AIRFIELD_RENAMES:
        row["name_zh"] = AIRFIELD_RENAMES[row["iata"]]
    return row


# 已經停用、沒有民航定期航班的機場(資料來源沒更新)：水湳(TXG，2004 年停用)、屏東北(PIF，軍用)、恆春(HCN)、
# 柏林舊機場(泰格爾 TXL、滕珀爾霍夫 THF、舍訥費爾德 SXF，2020 年起由新的 BER 取代)
NOT_OPERATING = {"TXG", "PIF", "HCN", "TXL", "THF", "SXF"}
_MILITARY = re.compile(r"Air ?Base|Air Force|\bAFB\b|Army|Naval|Navy|Military|Marine Corps|\bNAS\b|\bMCAS\b|RAAF|RAF ", re.I)


def _is_airfield(row):
    """不列出的機場：名稱是「飛行場」的小型飛行場(例如札幌飛行場)、停用的機場，
    以及名稱是軍用基地、而且沒有任何民航定期航班的(有定期航班的軍民合用機場，例如查爾斯頓，照常收)。"""
    if row.get("iata") in NOT_OPERATING:
        return True
    if "飛行場" in (row.get("name_zh") or ""):
        return True
    return bool(_MILITARY.search(row.get("name") or "")) and str(row.get("routes") or "0") == "0"


def _load_all():
    """完整機場清單(所有有定期航班的機場，含只飛國內線的小機場)：國內小機場也要搜得到、選得到，
    只有名稱是「飛行場」的不收。"""
    try:
        with open(_ALL_CSV_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                _fix_name(row)
                if _is_airfield(row):
                    continue
                if row["iata"] not in _by_iata:
                    _airports.append(row)
                    _by_iata[row["iata"]] = row
                _all_by_city.setdefault((row["city"].lower(), row["country"].lower()), []).append(row)
    except OSError:
        pass  # 沒有完整清單就退回只列國際機場
    # 原本的國際機場檔裡若有「飛行場」(例如百里、小松、美保)，一併拿掉
    _airports[:] = [row for row in _airports if not _is_airfield(row)]
    for code in [code for code, row in _by_iata.items() if _is_airfield(row)]:
        del _by_iata[code]
    for group in _all_by_city.values():
        group.sort(key=lambda a: -int(a.get("routes") or 0))


_load()
_load_all()


def _distance_km(a, b):
    """兩個機場之間的直線距離(公里)；任何一個沒有座標就回傳 None。"""
    try:
        lat1, lon1, lat2, lon2 = (math.radians(float(x)) for x in (a["latitude"], a["longitude"], b["latitude"], b["longitude"]))
    except (KeyError, TypeError, ValueError):
        return None
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def has_service(iata_code):
    """這個機場在航線資料裡有沒有任何定期航班。"""
    airport = _by_iata.get((iata_code or "").strip().upper())
    return bool(airport) and int(airport.get("routes") or 0) > 0


def nearest_service_airport(iata_code, min_routes=30, max_km=500):
    """離這個機場最近、而且航線夠多(有足夠航班可以查)的機場。同一個國家優先；沒有才找其他國家(最遠 max_km 公里)。
    回傳 (機場, 距離公里)；找不到回傳 None。"""
    origin = _by_iata.get((iata_code or "").strip().upper())
    if not origin:
        return None
    best_same, best_other = None, None
    for airport in _airports:
        if airport["iata"] == origin["iata"] or int(airport.get("routes") or 0) < min_routes:
            continue
        km = _distance_km(origin, airport)
        if km is None or km > max_km:
            continue
        if airport["country"] == origin["country"]:
            if best_same is None or km < best_same[1]:
                best_same = (airport, km)
        elif best_other is None or km < best_other[1]:
            best_other = (airport, km)
    return best_same or best_other


def get_airport(iata_code):
    """用 IATA 代碼查單一機場的完整資料(含中文名稱)，查不到回傳 None。"""
    return _by_iata.get((iata_code or "").strip().upper())


def get_city_airports(english_city_name, country=None, limit=6, include_domestic=False):
    """同一個城市(依英文城市名，country 有給的話一起比對避免跟同名的其他國家城市混在一起)
    底下的所有機場，international 機場優先排。"""
    name_lower = (english_city_name or "").strip().lower()
    if not name_lower:
        return []
    country_lower = (country or "").strip().lower()
    if include_domestic and country_lower and _all_by_city.get((name_lower, country_lower)):
        return _all_by_city[(name_lower, country_lower)][:limit]  # 像 Google 一樣列出這個城市所有機場
    matches = [
        a for a in _airports
        if a["city"].lower() == name_lower and (not country_lower or a["country"].lower() == country_lower)
    ]
    matches.sort(key=lambda a: "international" not in a["name"].lower())
    return matches[:limit]


def get_city_airport_codes(english_city_name, country=None):
    """回傳某個城市底下所有機場的 IATA 代碼，用逗號接起來(SerpApi 的 departure_id/arrival_id
    支援一次傳好幾個用逗號分開的代碼，查詢結果會把這幾個機場的航班混在一起回傳)。查不到就回傳 None。"""
    matches = get_city_airports(english_city_name, country)
    return ",".join(a["iata"] for a in matches) if matches else None


# 機場資料裡同一個國家有兩種寫法(緬甸一部分是 Burma、一部分是 Myanmar)，查國家時視為同一個
_COUNTRY_ALIASES = {"myanmar": "burma"}


def country_key(name):
    key = (name or "").strip().lower()
    return _COUNTRY_ALIASES.get(key, key)


def match_country_name(keyword):
    """使用者打的英文字剛好是某個國家名稱(例如 Japan、japan)就回傳資料庫裡的國名，不是就回傳 None。"""
    key = (keyword or "").strip().lower()
    if not key:
        return None
    for a in _airports:
        if a["country"].lower() == key:
            return a["country"]
    key = _COUNTRY_ALIASES.get(key, key)
    return next((a["country"] for a in _airports if a["country"].lower() == key), None)


def get_country_airports(english_country_name, limit=None):
    """查詢附有航線統計的主要機場，保留完整機場清單供城市搜尋使用。"""
    name_lower = country_key(english_country_name)
    if not name_lower:
        return []
    matches = [a for a in _airports if country_key(a["country"]) == name_lower and a.get("routes") is not None]
    matches.sort(key=lambda a: -int(a.get("routes") or 0))
    return matches[:limit] if limit else matches


def _norm_zh(text):
    return text.replace("臺", "台")


def search_airports(keyword, limit=10):
    """依關鍵字(城市名/機場名/IATA 代碼，英文、不分大小寫)找出符合的城市，
    每個符合的城市會展開成「這個城市底下的所有機場」一起列出(例如打 tpe 或 Taipei，
    會把桃園機場(TPE)、松山機場(TSA)都列出來，不是只有代碼剛好對到的那一個)。
    排序：IATA 代碼完全相符的城市優先 > 城市名開頭相符 > 城市名包含關鍵字 > 機場名稱包含關鍵字。"""
    keyword = (keyword or "").strip()
    if not keyword or not _airports:
        return []
    keyword_lower = keyword.lower()
    keyword_upper = keyword.upper()

    exact_iata = []
    city_prefix = []
    city_contains = []
    name_contains = []
    seen_city = set()

    def city_key(airport):
        return (airport["city"].lower(), airport["country"].lower())

    has_cjk = any("一" <= ch <= "鿿" for ch in keyword)
    zh_keyword = _norm_zh(keyword) if has_cjk else ""
    zh_prefix = []
    zh_contains = []

    for airport in _airports:
        key = city_key(airport)
        if key in seen_city:
            continue
        if zh_keyword:
            # 中文關鍵字(高雄、台中⋯)：比對中文機場名稱，臺/台視為相同
            # 資料裡的原名稱，加上慣用簡稱(NAME_ZH_OVERRIDES，例如「波士頓洛根機場」)都要能搜到
            names = [_norm_zh(airport.get("name_zh") or ""), _norm_zh(NAME_ZH_OVERRIDES.get(airport["iata"], ""))]
            if any(n.startswith(zh_keyword) for n in names):
                zh_prefix.append(airport)
                seen_city.add(key)
            elif any(zh_keyword in n for n in names):
                zh_contains.append(airport)
                seen_city.add(key)
            continue
        city_lower = airport["city"].lower()
        if airport["iata"] == keyword_upper:
            exact_iata.append(airport)
            seen_city.add(key)
        elif city_lower.startswith(keyword_lower):
            city_prefix.append(airport)
            seen_city.add(key)
        elif keyword_lower in city_lower:
            city_contains.append(airport)
            seen_city.add(key)
        elif keyword_lower in airport["name"].lower():
            name_contains.append(airport)
            seen_city.add(key)

    def _city_routes(airport):
        """整個城市的航線數(取城市裡最大的機場)：代表機場不一定是航線最多的那個(例如墨爾本的代表可能是小機場)。"""
        group = _all_by_city.get((airport["city"].lower(), airport["country"].lower())) or [airport]
        return max(int(a.get("routes") or 0) for a in group)

    def _rank(group):
        return sorted(group, key=lambda a: (-_city_routes(a), "international" not in a["name"].lower()))  # 航線多的大城市優先(倫敦排英國的，不是加拿大的)

    representative_cities = _rank(zh_prefix) + _rank(zh_contains) + _rank(exact_iata) + _rank(city_prefix) + _rank(city_contains) + _rank(name_contains)

    results = []
    seen_iata = set()
    for representative in representative_cities:
        if len(results) >= limit:
            break
        siblings = get_city_airports(representative["city"], representative["country"], include_domestic=True)
        for sibling in siblings:
            if sibling["iata"] in seen_iata:
                continue
            seen_iata.add(sibling["iata"])
            results.append(sibling)

    return results[:limit]


def find_iata_by_keyword(keyword):
    """給 flight_links.to_iata() 當最後一層 fallback：查不到中文對照表時，
    改查全球機場資料庫(英文城市名/機場名)，找到最相關的那筆就回傳它的 IATA 代碼。"""
    matches = search_airports(keyword, limit=1)
    return matches[0]["iata"] if matches else None
