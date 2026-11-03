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
import os

_CSV_PATH = os.path.join(os.path.dirname(__file__), "database", "airports_data.csv")

_airports = []  # [{"iata":..., "city":..., "country":..., "name":..., "name_zh":...}, ...]
_by_iata = {}


def _load():
    if _airports:
        return
    try:
        with open(_CSV_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                _airports.append(row)
                _by_iata[row["iata"]] = row
    except OSError:
        pass  # 資料檔不存在就當作沒有全球機場資料，搜尋回傳空清單，不會讓網站掛掉


_load()


def get_airport(iata_code):
    """用 IATA 代碼查單一機場的完整資料(含中文名稱)，查不到回傳 None。"""
    return _by_iata.get((iata_code or "").strip().upper())


def get_city_airports(english_city_name, country=None, limit=6):
    """同一個城市(依英文城市名，country 有給的話一起比對避免跟同名的其他國家城市混在一起)
    底下的所有機場，international 機場優先排。"""
    name_lower = (english_city_name or "").strip().lower()
    if not name_lower:
        return []
    country_lower = (country or "").strip().lower()
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

    for airport in _airports:
        key = city_key(airport)
        if key in seen_city:
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

    def _rank(group):
        return sorted(group, key=lambda a: "international" not in a["name"].lower())

    representative_cities = _rank(exact_iata) + _rank(city_prefix) + _rank(city_contains) + _rank(name_contains)

    results = []
    seen_iata = set()
    for representative in representative_cities:
        if len(results) >= limit:
            break
        siblings = get_city_airports(representative["city"], representative["country"])
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
