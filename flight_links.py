"""城市中文關鍵字 <-> IATA 機場代碼對照表，給 Amadeus 查詢、Skyscanner 比價連結共用。"""
import re
from urllib.parse import urlencode

import airports

CITY_IATA = {
    # 台灣
    "台北": "TPE", "台北市": "TPE", "桃園": "TPE",
    # 日本
    "東京": "NRT", "東京都": "NRT", "大阪": "KIX", "大阪市": "KIX", "名古屋": "NGO",
    "福岡": "FUK", "札幌": "CTS", "沖繩": "OKA", "京都": "KIX",
    # 韓國
    "首爾": "ICN", "首爾特別市": "ICN", "釜山": "PUS",
    # 中國/港澳
    "香港": "HKG", "澳門": "MFM", "上海": "PVG", "北京": "PEK", "廣州": "CAN", "深圳": "SZX",
    # 東南亞
    "曼谷": "BKK", "新加坡": "SIN", "吉隆坡": "KUL", "雅加達": "CGK", "馬尼拉": "MNL",
    "胡志明市": "SGN", "河內": "HAN", "峇里島": "DPS", "清邁": "CNX",
    # 南亞
    "新德里": "DEL", "孟買": "BOM",
    # 大洋洲
    "雪梨": "SYD", "墨爾本": "MEL", "奧克蘭": "AKL", "布里斯本": "BNE",
    # 北美
    "紐約": "JFK", "洛杉磯": "LAX", "舊金山": "SFO", "芝加哥": "ORD", "西雅圖": "SEA",
    "溫哥華": "YVR", "多倫多": "YYZ", "拉斯維加斯": "LAS", "檀香山": "HNL", "夏威夷": "HNL",
    # 歐洲
    "倫敦": "LHR", "巴黎": "CDG", "法蘭克福": "FRA", "羅馬": "FCO", "阿姆斯特丹": "AMS",
    "蘇黎世": "ZRH", "維也納": "VIE", "馬德里": "MAD", "伊斯坦堡": "IST", "莫斯科": "SVO",
    # 中東
    "杜拜": "DXB", "多哈": "DOH",
}


# 中文城市名稱 -> 英文城市名稱，給自動完成打中文時查全球機場資料庫(airports.py，英文資料)用。
# 很多城市不只一個機場(例如東京有羽田/成田、紐約有 JFK/LGA/EWR)，CITY_IATA 只能對應一個固定代碼，
# 查這個對照表轉成英文城市名之後，才能從全球機場資料庫裡找出「這個城市底下所有機場」給使用者挑。
CITY_NAME_EN = {
    "台北": "Taipei", "台北市": "Taipei", "桃園": "Taipei",
    "東京": "Tokyo", "東京都": "Tokyo", "大阪": "Osaka", "大阪市": "Osaka", "名古屋": "Nagoya",
    "福岡": "Fukuoka", "札幌": "Sapporo", "沖繩": "Okinawa", "京都": "Kyoto",
    "首爾": "Seoul", "首爾特別市": "Seoul", "釜山": "Busan",
    "香港": "Hong Kong", "澳門": "Macau", "上海": "Shanghai", "北京": "Beijing", "廣州": "Guangzhou", "深圳": "Shenzhen",
    "曼谷": "Bangkok", "新加坡": "Singapore", "吉隆坡": "Kuala Lumpur", "雅加達": "Jakarta", "馬尼拉": "Manila",
    "胡志明市": "Ho Chi Minh City", "河內": "Hanoi", "峇里島": "Denpasar", "清邁": "Chiang Mai",
    "新德里": "Delhi", "孟買": "Mumbai",
    "雪梨": "Sydney", "墨爾本": "Melbourne", "奧克蘭": "Auckland", "布里斯本": "Brisbane",
    "紐約": "New York", "洛杉磯": "Los Angeles", "舊金山": "San Francisco", "芝加哥": "Chicago", "西雅圖": "Seattle",
    "溫哥華": "Vancouver", "多倫多": "Toronto", "拉斯維加斯": "Las Vegas", "檀香山": "Honolulu", "夏威夷": "Honolulu",
    "倫敦": "London", "巴黎": "Paris", "法蘭克福": "Frankfurt", "羅馬": "Rome", "阿姆斯特丹": "Amsterdam",
    "蘇黎世": "Zurich", "維也納": "Vienna", "馬德里": "Madrid", "伊斯坦堡": "Istanbul", "莫斯科": "Moscow",
    "杜拜": "Dubai", "多哈": "Doha",
}


# 主要機場的正式中文名稱(IATA 代碼 -> 中文機場名稱)，只整理使用者實際搜尋得到的 ~50 個城市底下的機場，
# 沒有列在這裡的機場(全球機場資料庫裡其他幾千個)就顯示原始的英文名稱，不會亂翻譯成不正確的中文。
AIRPORT_NAME_ZH = {
    "TPE": "桃園國際機場", "TSA": "台北松山機場",
    "NRT": "東京成田機場", "HND": "東京羽田機場",
    "KIX": "大阪關西機場", "ITM": "大阪伊丹機場",
    "NGO": "名古屋中部國際機場", "FUK": "福岡機場", "CTS": "札幌新千歲機場", "OKA": "沖繩那霸機場",
    "ICN": "首爾仁川機場", "GMP": "首爾金浦機場", "PUS": "釜山金海機場",
    "HKG": "香港國際機場", "MFM": "澳門國際機場",
    "PVG": "上海浦東機場", "SHA": "上海虹橋機場",
    "PEK": "北京首都機場", "PKX": "北京大興機場",
    "CAN": "廣州白雲機場", "SZX": "深圳寶安機場",
    "BKK": "曼谷素萬那普機場", "DMK": "曼谷廊曼機場",
    "SIN": "新加坡樟宜機場", "KUL": "吉隆坡國際機場", "CGK": "雅加達蘇卡諾哈達機場", "MNL": "馬尼拉尼諾伊艾奎諾機場",
    "SGN": "胡志明市新山一機場", "HAN": "河內內排機場", "DPS": "峇里島伍拉賴機場", "CNX": "清邁機場",
    "DEL": "德里英迪拉甘地機場", "BOM": "孟買賈特拉帕蒂希瓦吉機場",
    "SYD": "雪梨金斯福史密斯機場", "MEL": "墨爾本機場", "AKL": "奧克蘭機場", "BNE": "布里斯本機場",
    "JFK": "紐約甘迺迪機場", "LGA": "紐約拉瓜地亞機場", "EWR": "紐約紐華克機場",
    "LAX": "洛杉磯國際機場", "SFO": "舊金山國際機場",
    "ORD": "芝加哥歐海爾機場", "MDW": "芝加哥中途機場",
    "SEA": "西雅圖塔科馬機場", "YVR": "溫哥華國際機場", "YYZ": "多倫多皮爾森機場",
    "LAS": "拉斯維加斯哈瑞瑞德機場", "HNL": "檀香山國際機場",
    "LHR": "倫敦希斯洛機場", "LGW": "倫敦蓋威克機場", "STN": "倫敦史坦斯特機場",
    "LTN": "倫敦盧頓機場", "LCY": "倫敦城市機場",
    "CDG": "巴黎戴高樂機場", "ORY": "巴黎奧利機場",
    "FRA": "法蘭克福機場", "FCO": "羅馬菲烏米奇諾機場", "AMS": "阿姆斯特丹史基浦機場",
    "ZRH": "蘇黎世機場", "VIE": "維也納機場", "MAD": "馬德里機場",
    "IST": "伊斯坦堡機場", "SVO": "莫斯科謝列梅捷沃機場",
    "DXB": "杜拜國際機場", "DOH": "多哈哈馬德機場",
}


# CITY_NAME_EN 很多中文別名對應同一個英文城市(例如「台北」「台北市」「桃園」都是 Taipei)，
# 不能直接反過來查，不然會查到不適合拿來顯示的別名(例如顯示「桃園・所有機場」而不是「台北・所有機場」)，
# 所以另外整理一份「英文城市名 -> 最適合顯示的中文城市名稱」，給「所有機場」選項顯示用。
CITY_NAME_ZH_DISPLAY = {en: zh for zh, en in CITY_NAME_EN.items()}
CITY_NAME_ZH_DISPLAY.update({
    "Taipei": "台北", "Tokyo": "東京", "Osaka": "大阪", "Seoul": "首爾",
    "New York": "紐約", "London": "倫敦", "Paris": "巴黎", "Bangkok": "曼谷",
})


def to_chinese_city_name(english_city_name):
    """英文城市名 -> 中文城市名(給「所有機場」選項顯示用)，查不到(不是我們整理過的常見城市)
    就回傳 None，呼叫端自己 fallback 顯示英文城市名，不要亂翻譯。"""
    return CITY_NAME_ZH_DISPLAY.get((english_city_name or "").strip())


def to_english_city_name(keyword):
    """把中文城市關鍵字轉成英文城市名稱，查不到(可能本來就是英文，或根本不是我們認得的城市)就原樣回傳。"""
    keyword = (keyword or "").strip()
    if keyword in CITY_NAME_EN:
        return CITY_NAME_EN[keyword]
    for name, en_name in CITY_NAME_EN.items():
        if name in keyword or keyword in name:
            return en_name
    return keyword


# 本地示範資料庫裡固定會出現的航空公司中文名稱 -> 官方 IATA 兩碼代號，
# 用來組出 Google Flights 自己在用的航空公司 logo 圖檔網址(是真的官方 logo，不是我們自己做的圖)。
AIRLINE_IATA = {
    "中華航空": "CI", "星宇航空": "JX", "日本航空": "JL", "長榮航空": "BR",
    "大韓航空": "KE", "泰國航空": "TG", "新加坡航空": "SQ", "國泰航空": "CX",
    "全日空航空": "NH", "台灣虎航": "IT", "樂桃航空": "MM", "酷航": "TR",
    "泰國微笑航空": "WE", "德威航空": "TW", "真航空": "LJ", "香港快運航空": "UO",
}


def airline_logo_url(airline_name):
    code = AIRLINE_IATA.get((airline_name or "").strip())
    if not code:
        return None
    return f"https://www.gstatic.com/flights/airline_logos/70px/{code}.png"


ALL_AIRPORTS_SUFFIX = "（所有機場）"  # 跟「City (IATA)」那種半形括號的單一機場格式故意用不同樣式，一眼就看得出差異


def to_iata(city_keyword):
    """把中文城市關鍵字、使用者直接輸入的三碼機場代碼、「City (IATA)」這種自動完成選單選出來的
    單一機場格式，或是「城市（所有機場）」這種選了「所有機場」的格式，轉成 IATA 代碼；
    「所有機場」的情況會回傳用逗號接起來的好幾個代碼(SerpApi 的 departure_id/arrival_id 支援這樣傳，
    會把這個城市底下所有機場的航班混在一起回傳)。查不到就回傳 None。
    常見中文城市名先查 CITY_IATA(約 80 個)，查不到再查 airports.py 的全球機場資料庫
    (約 6000 筆真實機場資料，含英文城市名/機場名)，這樣全世界的城市/機場都搜得到，
    不是只有手動整理的那 80 個。"""
    city_keyword = (city_keyword or "").strip()
    if not city_keyword:
        return None
    if city_keyword.endswith(ALL_AIRPORTS_SUFFIX):
        city_name = city_keyword[: -len(ALL_AIRPORTS_SUFFIX)].strip()
        codes = airports.get_city_airport_codes(to_english_city_name(city_name))
        if codes:
            return codes
        city_keyword = city_name  # 全球機場資料庫查不到這個城市，退回當一般城市名字查(用 CITY_IATA)
    bracket_match = re.search(r"\(([A-Za-z]{3})\)\s*$", city_keyword)
    if bracket_match:
        return bracket_match.group(1).upper()
    # 要限制只比對 ASCII 英文字母，不能只檢查長度是不是 3：Python 的 str.isalpha() 連中文字也算「字母」，
    # 像「新加坡」「洛杉磯」剛好都是 3 個中文字，之前這裡會誤判成「使用者直接輸入了機場代碼」，
    # 原樣大寫回傳中文字(根本不是合法代碼)，導致這些城市的查詢全部失敗，要繞過下面 CITY_IATA 對照表。
    if re.fullmatch(r"[A-Za-z]{3}", city_keyword):
        return city_keyword.upper()
    if city_keyword in CITY_IATA:
        return CITY_IATA[city_keyword]
    for name, code in CITY_IATA.items():
        if name in city_keyword or city_keyword in name:
            return code
    return airports.find_iata_by_keyword(city_keyword)


def skyscanner_search_url(origin_keyword, destination_keyword, depart_date, return_date=None, pax=1):
    """組出 Skyscanner 的機票比價搜尋結果網址（純粹組網址，不是在呼叫 API 或爬蟲，
    使用者點了只是被導去 Skyscanner 自己的頁面，等同於自己手動在上面搜尋同一條航線），
    讓使用者在 Skyscanner 上比價、完成真正的訂票，我們就不用自己寫金流／結帳流程。
    查不到城市代碼或沒填日期就回傳 None，呼叫端就不要顯示這顆按鈕。"""
    origin = to_iata(origin_keyword)
    destination = to_iata(destination_keyword)
    if not origin or not destination or not depart_date:
        return None
    # 選了「所有機場」時 to_iata() 會回傳逗號接起來的好幾個代碼(例如 "NRT,HND")，
    # Skyscanner 的網址格式一次只能放一個機場代碼，這裡退而求其次只用第一個(通常是比較大的那個機場)。
    origin = origin.split(",")[0]
    destination = destination.split(",")[0]

    def to_yymmdd(iso_date):
        year, month, day = iso_date.split("-")
        return year[2:] + month + day

    try:
        parts = [origin.lower(), destination.lower(), to_yymmdd(depart_date)]
        if return_date:
            parts.append(to_yymmdd(return_date))
    except (ValueError, AttributeError):
        return None

    params = {"adultsv2": pax, "cabinclass": "economy", "rtn": "1" if return_date else "0"}
    return "https://www.skyscanner.com.tw/transport/flights/" + "/".join(parts) + "/?" + urlencode(params)

