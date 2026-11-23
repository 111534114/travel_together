"""城市中文關鍵字 <-> IATA 機場代碼對照表，給 Amadeus 查詢、Skyscanner 比價連結共用。"""
import json
import os
import re
from urllib.parse import urlencode

import airports

CITY_IATA = {
    # 台灣
    "台北": "TPE", "台北市": "TPE", "桃園": "TPE",
    "雷克雅維克": "KEF", "雷克雅未克": "KEF",
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
    "函館": "Hakodate", "仙台": "Sendai", "廣島": "Hiroshima", "広島": "Hiroshima", "新潟": "Niigata",
    "熊本": "Kumamoto", "鹿兒島": "Kagoshima", "長崎": "Nagasaki", "松山": "Matsuyama", "小松": "Komatsu",
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
    # 機場本身有專屬名稱(不是只有「城市+國際機場」這種泛稱)的，把城市名拿掉，避免跟搜尋目的地重複顯示
    # (例如搜尋「札幌」，航班卡片上的機場名稱不用再顯示一次「札幌」)。
    "TPE": "桃園國際機場", "TSA": "松山機場",
    "KHH": "高雄小港機場", "RMQ": "台中機場",
    "NRT": "成田機場", "HND": "羽田機場",
    "KIX": "關西機場", "ITM": "伊丹機場",
    "NGO": "中部國際機場", "FUK": "福岡機場", "CTS": "新千歲機場", "OKA": "那霸機場",
    "ICN": "仁川機場", "GMP": "金浦機場", "PUS": "金海機場",
    "HKG": "香港國際機場", "MFM": "澳門國際機場",
    "PVG": "浦東機場", "SHA": "虹橋機場",
    "PEK": "首都機場", "PKX": "大興機場",
    "CAN": "白雲機場", "SZX": "寶安機場",
    "BKK": "素萬那普機場", "DMK": "廊曼機場",
    "SIN": "樟宜機場", "KUL": "吉隆坡國際機場", "CGK": "蘇卡諾哈達機場", "MNL": "尼諾伊艾奎諾機場",
    "SGN": "新山一機場", "HAN": "內排機場", "DPS": "伍拉賴機場", "CNX": "清邁機場",
    "DEL": "英迪拉甘地機場", "BOM": "賈特拉帕蒂希瓦吉機場",
    "SYD": "金斯福史密斯機場", "MEL": "墨爾本機場", "AKL": "奧克蘭機場", "BNE": "布里斯本機場",
    "JFK": "甘迺迪機場", "LGA": "拉瓜地亞機場", "EWR": "紐華克機場",
    "LAX": "洛杉磯國際機場", "SFO": "舊金山國際機場",
    "ORD": "歐海爾機場", "MDW": "中途機場",
    "SEA": "塔科馬機場", "YVR": "溫哥華國際機場", "YYZ": "皮爾森機場",
    "LAS": "哈瑞瑞德機場", "HNL": "檀香山國際機場",
    "LHR": "希斯洛機場", "LGW": "蓋威克機場", "STN": "史坦斯特機場",
    "LTN": "盧頓機場", "LCY": "倫敦城市機場",
    "CDG": "戴高樂機場", "ORY": "奧利機場",
    "FRA": "法蘭克福機場", "FCO": "菲烏米奇諾機場", "AMS": "史基浦機場",
    "ZRH": "蘇黎世機場", "VIE": "維也納機場", "MAD": "馬德里機場",
    "IST": "伊斯坦堡機場", "SVO": "謝列梅捷沃機場",
    "DXB": "杜拜國際機場", "DOH": "哈馬德機場",
}


# CITY_NAME_EN 很多中文別名對應同一個英文城市(例如「台北」「台北市」「桃園」都是 Taipei)，
# 不能直接反過來查，不然會查到不適合拿來顯示的別名(例如顯示「桃園・所有機場」而不是「台北・所有機場」)，
# 所以另外整理一份「英文城市名 -> 最適合顯示的中文城市名稱」，給「所有機場」選項顯示用。
CITY_NAME_ZH_DISPLAY = {en: zh for zh, en in CITY_NAME_EN.items()}
CITY_NAME_ZH_DISPLAY.update({
    "Taipei": "台北", "Tokyo": "東京", "Osaka": "大阪", "Seoul": "首爾",
    "New York": "紐約", "London": "倫敦", "Paris": "巴黎", "Bangkok": "曼谷",
    "Kaohsiung": "高雄", "Taichung": "台中", "Tainan": "台南", "Hualien": "花蓮", "Fengnin": "台東",
    "Kinmen": "金門", "Makung": "澎湖", "Sapporo": "札幌", "Fukuoka": "福岡", "Nagoya": "名古屋",
    "Okinawa": "沖繩", "Melbourne": "墨爾本", "Sydney": "雪梨", "Busan": "釜山", "Hong Kong": "香港",
    "Singapore": "新加坡", "Los Angeles": "洛杉磯", "San Francisco": "舊金山", "Vancouver": "溫哥華",
    "Agana": "關島",
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


# 航空公司 -> 真正隸屬的全球航空聯盟(公開的真實資料，不是我們自己分類的)；廉價航空/獨立航空
# (例如星宇航空、酷航、樂桃、台灣虎航這些)本來就沒有加入任何聯盟，查不到就是沒有聯盟可篩，
# 不會因為查不到就亂塞一個聯盟給它。
ALLIANCE_NAMES = {"skyteam": "天合聯盟", "star_alliance": "星空聯盟", "oneworld": "寰宇一家"}
AIRLINE_ALLIANCE = {
    # 天合聯盟 SkyTeam
    "中華航空": "skyteam", "大韓航空": "skyteam",
    # 星空聯盟 Star Alliance
    "長榮航空": "star_alliance", "全日空航空": "star_alliance", "韓亞航空": "star_alliance",
    "新加坡航空": "star_alliance", "泰國航空": "star_alliance",
    # 寰宇一家 Oneworld
    "國泰航空": "oneworld", "日本航空": "oneworld",
}


ALL_AIRPORTS_SUFFIX = "（所有機場）"  # 跟「City (IATA)」那種半形括號的單一機場格式故意用不同樣式，一眼就看得出差異


# 「北海道」「九州」這種是涵蓋好幾個城市的「地區」，不是單一城市的別名——之前把它們當成札幌/福岡的
# 別名處理，搜尋「北海道」卻查不到函館、旭川這些北海道其他城市的航班，就是因為這個誤判。
# 每個地區對應底下主要城市的英文名稱(對照全球機場資料庫真實查過，不是用猜的)，
# 查詢時會把這些城市的機場全部聯集起來一起查。
REGION_CITIES = {
    "北海道": ["Sapporo", "Hakodate", "Asahikawa", "Kushiro", "Obihiro", "Wakkanai", "Memanbetsu"],
    "九州": ["Fukuoka", "Kitakyushu", "Kagoshima", "Kumamoto", "Nagasaki", "Oita", "Miyazaki", "Saga"],
}


_COUNTRIES_ZH_PATH = os.path.join(os.path.dirname(__file__), "database", "countries_zh.json")
try:
    with open(_COUNTRIES_ZH_PATH, encoding="utf-8") as _f:
        COUNTRY_ZH = json.load(_f)  # {機場資料庫的英文國名: 繁體中文國名}，全世界約 235 個國家與地區
except (OSError, ValueError):
    COUNTRY_ZH = {}
# 中文國家名稱 -> 機場資料庫裡的英文國名：所有國家(上面那份)加上常見的別稱
COUNTRY_NAME_EN = {zh: en for en, zh in COUNTRY_ZH.items()}
COUNTRY_NAME_EN.update({'臺灣': 'Taiwan', '南韓': 'South Korea', '印度尼西亞': 'Indonesia', '阿聯': 'United Arab Emirates', '阿聯酋': 'United Arab Emirates', '阿拉伯聯合大公國': 'United Arab Emirates', '寮國': 'Laos', '老撾': 'Laos', '捷克共和國': 'Czech Republic', '美利堅合眾國': 'United States'})
# 各國的正式名稱與其他常見寫法(使用者可能照官方名稱或不同譯名輸入)
COUNTRY_NAME_EN.update({
    '中華人民共和國': 'China', '中國大陸': 'China', '大陸': 'China', '印度尼西亞共和國': 'Indonesia', '印尼': 'Indonesia',
    '朝鮮': 'North Korea', '朝鮮民主主義人民共和國': 'North Korea', '北韓': 'North Korea', '大韓民國': 'South Korea', '韓國': 'South Korea',
    '吉爾吉斯斯坦': 'Kyrgyzstan', '塔吉克斯坦': 'Tajikistan', '土庫曼斯坦': 'Turkmenistan', '烏茲別克斯坦': 'Uzbekistan', '哈薩克斯坦': 'Kazakhstan',
    '亞賽拜然': 'Azerbaijan', '阿塞拜疆': 'Azerbaijan', '文萊': 'Brunei', '馬爾代夫': 'Maldives', '卡塔爾': 'Qatar', '沙特阿拉伯': 'Saudi Arabia',
    '格魯吉亞': 'Georgia', '孟加拉國': 'Bangladesh', '塞普勒斯': 'Cyprus', '塞浦路斯': 'Cyprus', '賽普勒斯': 'Cyprus',
    '巴勒斯坦': 'Palestine', '巴勒斯坦自治區': 'Palestine', '緬甸': 'Myanmar', '東帝汶': 'East Timor', 'Timor-Leste': 'East Timor',
})
# 旅客常用、但機場中文名稱裡沒有這個字的城市/景點別名 -> 代表的機場代碼
# (例如「普吉島」的機場叫「布吉國際機場」，只比對機場名稱會找不到)
TOURIST_ALIAS = {
    '京都': 'KIX', '奈良': 'KIX', '石垣島': 'ISG', '宮古島': 'MMY', '金澤': 'KMQ', '小松': 'KMQ', '濟州島': 'CJU',
    '普吉島': 'HKT', '蘇梅島': 'USM', '蘇美島': 'USM', '芭達雅': 'UTP', '沙巴': 'BKI', '蘭卡威': 'LGK',
    '巴里島': 'DPS', '峇里島': 'DPS', '日惹': 'JOG', '長灘島': 'MPH', '薄荷島': 'TAG', '巴拉望': 'PPS',
    '西貢': 'SGN', '富國島': 'PQC', '吳哥窟': 'REP', '永珍': 'VTE', '龍坡邦': 'LPQ', '加德滿都': 'KTM',
    '馬列': 'MLE', '芽莊': 'CXR', '可倫坡': 'CMB', '佛羅倫斯': 'FLR', '巴塞隆納': 'BCN', '約翰尼斯堡': 'JNB', '奈洛比': 'NBO',
}
# 主要機場的慣用簡稱(資料裡是冗長的紀念人物全名，例如「哈茨菲爾德－傑克遜亞特蘭大國際機場」)，
# 由 database/airport_short_names.json 載入；下面手動指定的優先
try:
    with open(os.path.join(os.path.dirname(__file__), "database", "airport_short_names.json"), encoding="utf-8") as _f:
        AIRPORT_NAME_ZH.update(json.load(_f))
except (OSError, ValueError):
    pass
AIRPORT_NAME_ZH.update({"KIV": "基希涅夫國際機場", "VTZ": "維沙卡帕特南機場", "GUM": "安東尼奧B.汪帕特國際機場"})
airports.NAME_ZH_OVERRIDES = AIRPORT_NAME_ZH  # 讓機場中文搜尋也比對這些名稱
# 非洲各國：大陸用語、台灣用語、簡體字寫法都能搜(英文國名要跟機場資料裡的寫法一致)
COUNTRY_NAME_EN.update({
    '毛里塔尼亞': 'Mauritania', '毛利塔尼亞': 'Mauritania', '茅利塔尼亞': 'Mauritania',
    '埃塞俄比亞': 'Ethiopia', '衣索比亞': 'Ethiopia', '厄立特里亞': 'Eritrea', '厄立垂亞': 'Eritrea', '厄利垂亞': 'Eritrea',
    '肯尼亞': 'Kenya', '肯亞': 'Kenya', '盧旺達': 'Rwanda', '盧安達': 'Rwanda', '布隆迪': 'Burundi', '蒲隆地': 'Burundi',
    '塞舌爾': 'Seychelles', '塞席爾': 'Seychelles', '乍得': 'Chad', '查德': 'Chad', '中非': 'Central African Republic', '中非共和國': 'Central African Republic',
    '剛果共和國': 'Congo (Brazzaville)', '剛果（布）': 'Congo (Brazzaville)', '剛果(布)': 'Congo (Brazzaville)', '剛果布': 'Congo (Brazzaville)', '剛果（布拉薩）': 'Congo (Brazzaville)',
    '剛果民主共和國': 'Congo (Kinshasa)', '剛果（金）': 'Congo (Kinshasa)', '剛果(金)': 'Congo (Kinshasa)', '剛果金': 'Congo (Kinshasa)', '剛果（金夏沙）': 'Congo (Kinshasa)',
    '聖多美和普林西比': 'Sao Tome and Principe', '聖多美普林西比': 'Sao Tome and Principe', '聖多美': 'Sao Tome and Principe',
    '岡比亞': 'Gambia', '甘比亞': 'Gambia', '馬里': 'Mali', '馬利': 'Mali', '布基納法索': 'Burkina Faso', '布吉納法索': 'Burkina Faso',
    '幾內亞比紹': 'Guinea-Bissau', '幾內亞比索': 'Guinea-Bissau', '佛得角': 'Cape Verde', '維德角': 'Cape Verde',
    '塞拉利昂': 'Sierra Leone', '獅子山': 'Sierra Leone', '利比里亞': 'Liberia', '賴比瑞亞': 'Liberia',
    '科特迪瓦': "Cote d'Ivoire", '象牙海岸': "Cote d'Ivoire", '加納': 'Ghana', '迦納': 'Ghana', '貝寧': 'Benin', '貝南': 'Benin',
    '尼日爾': 'Niger', '尼日': 'Niger', '尼日利亞': 'Nigeria', '奈及利亞': 'Nigeria', '贊比亞': 'Zambia', '尚比亞': 'Zambia',
    '馬拉維': 'Malawi', '馬拉威': 'Malawi', '莫桑比克': 'Mozambique', '莫三比克': 'Mozambique', '博茨瓦納': 'Botswana', '波札那': 'Botswana',
    '南非共和國': 'South Africa', '南非': 'South Africa', '斯威士蘭': 'Swaziland', '史瓦濟蘭': 'Swaziland', '史瓦帝尼': 'Swaziland', '埃斯瓦蒂尼': 'Swaziland',
    '馬達加斯加': 'Madagascar', '马达加斯加': 'Madagascar', '科摩羅': 'Comoros', '葛摩': 'Comoros', '毛里求斯': 'Mauritius', '模里西斯': 'Mauritius',
    '吉布提': 'Djibouti', '吉布地': 'Djibouti', '利比亞': 'Libya', '索馬利亞': 'Somalia', '南蘇丹': 'South Sudan',
})
# 北美洲與加勒比海各國：大陸用語、台灣用語、簡體字寫法都能搜
COUNTRY_NAME_EN.update({
    '安提瓜和巴布達': 'Antigua and Barbuda', '安地卡及巴布達': 'Antigua and Barbuda', '安提瓜': 'Antigua and Barbuda', '安提瓜和巴布达': 'Antigua and Barbuda',
    '巴哈馬': 'Bahamas', '巴巴多斯': 'Barbados', '巴貝多': 'Barbados', '伯利茲': 'Belize', '貝里斯': 'Belize',
    '加拿大': 'Canada', '哥斯達黎加': 'Costa Rica', '哥斯大黎加': 'Costa Rica', '古巴': 'Cuba',
    '多米尼克': 'Dominica', '多米尼克國': 'Dominica', '多米尼加共和國': 'Dominican Republic', '多明尼加共和國': 'Dominican Republic',
    '多明尼加': 'Dominican Republic', '多米尼加': 'Dominican Republic', '薩爾瓦多': 'El Salvador',
    '格林達': 'Grenada', '格林納達': 'Grenada', '格瑞那達': 'Grenada', '危地馬拉': 'Guatemala', '瓜地馬拉': 'Guatemala',
    '海地': 'Haiti', '洪都拉斯': 'Honduras', '宏都拉斯': 'Honduras', '牙買加': 'Jamaica', '墨西哥': 'Mexico',
    '尼加拉瓜': 'Nicaragua', '巴拿馬': 'Panama',
    '聖基茨和尼維斯': 'Saint Kitts and Nevis', '聖克里斯多福及尼維斯': 'Saint Kitts and Nevis', '聖基茨': 'Saint Kitts and Nevis', '聖克里斯多福': 'Saint Kitts and Nevis',
    '聖盧西亞': 'Saint Lucia', '聖露西亞': 'Saint Lucia',
    '聖文森特和格林納丁斯': 'Saint Vincent and the Grenadines', '聖文森及格瑞那丁': 'Saint Vincent and the Grenadines', '聖文森': 'Saint Vincent and the Grenadines', '聖文森特': 'Saint Vincent and the Grenadines',
    '特立尼達和多巴哥': 'Trinidad and Tobago', '千里達及托巴哥': 'Trinidad and Tobago', '千里達': 'Trinidad and Tobago', '特立尼達': 'Trinidad and Tobago',
    '美國': 'United States', '美利堅合眾國': 'United States', '美利堅合衆國': 'United States',
})
# 歐洲、南美洲、大洋洲與屬地：大陸用語、台灣用語、簡體字寫法都能搜(英文國名要跟機場資料裡的寫法一致)
COUNTRY_NAME_EN.update({
    '波黑': 'Bosnia and Herzegovina', '波斯尼亞和黑塞哥維那': 'Bosnia and Herzegovina', '波士尼亞': 'Bosnia and Herzegovina', '波士尼亞與赫塞哥維納': 'Bosnia and Herzegovina',
    '克羅地亞': 'Croatia', '克羅埃西亞': 'Croatia', '意大利': 'Italy', '意大利共和國': 'Italy', '義大利': 'Italy',
    '摩多瓦': 'Moldova', '摩爾多瓦': 'Moldova', '黑山': 'Montenegro', '蒙特內哥羅': 'Montenegro', '馬其頓': 'Macedonia', '北馬其頓': 'Macedonia',
    '斯洛文尼亞': 'Slovenia', '斯洛維尼亞': 'Slovenia', '聯合王國': 'United Kingdom', '大不列顛': 'United Kingdom', '英國': 'United Kingdom',
    '厄瓜多爾': 'Ecuador', '厄瓜多': 'Ecuador', '圭亞那': 'Guyana', '蓋亞那': 'Guyana', '祕魯': 'Peru', '秘魯': 'Peru', '蘇里南': 'Suriname', '蘇利南': 'Suriname',
    '澳大利亞': 'Australia', '澳洲': 'Australia', '基里巴斯': 'Kiribati', '吉里巴斯': 'Kiribati', '密克羅尼西亞聯邦': 'Micronesia', '密克羅尼西亞': 'Micronesia',
    '瑙魯': 'Nauru', '諾魯': 'Nauru', '新西蘭': 'New Zealand', '紐西蘭': 'New Zealand', '帕勞': 'Palau', '帛琉': 'Palau',
    '巴布亞新幾內亞': 'Papua New Guinea', '巴布亞新畿內亞': 'Papua New Guinea', '巴布亞紐幾內亞': 'Papua New Guinea',
    '所羅門群島': 'Solomon Islands', '湯加': 'Tonga', '東加': 'Tonga', '圖瓦盧': 'Tuvalu', '吐瓦魯': 'Tuvalu', '瓦努阿圖': 'Vanuatu', '萬那杜': 'Vanuatu',
    '百慕大': 'Bermuda', '百慕達': 'Bermuda', '澳門': 'Macau', '澳门': 'Macau', '中國台灣': 'Taiwan', '台灣': 'Taiwan',
    '法羅': 'Faroe Islands', '法羅群島': 'Faroe Islands', '根西島': 'Guernsey', '根息': 'Guernsey', '澤西島': 'Jersey', '澤西': 'Jersey', '馬恩島': 'Isle of Man', '曼島': 'Isle of Man',
    '法屬波利尼西亞': 'French Polynesia', '法屬玻里尼西亞': 'French Polynesia', '留尼汪': 'Reunion', '留尼旺': 'Reunion', '馬約特': 'Mayotte', '馬約特島': 'Mayotte',
    '馬提尼克': 'Martinique', '馬丁尼克': 'Martinique', '瓜德羅普': 'Guadeloupe', '瓜地洛普': 'Guadeloupe', '阿魯巴': 'Aruba', '阿鲁巴': 'Aruba', '荷屬阿魯巴': 'Aruba',
    '美屬維爾京群島': 'Virgin Islands', '美屬維京群島': 'Virgin Islands', '英屬維爾京群島': 'British Virgin Islands', '英屬維京群島': 'British Virgin Islands',
    '特克斯和凱科斯群島': 'Turks and Caicos Islands', '土克斯及開科斯群島': 'Turks and Caicos Islands', '安圭拉': 'Anguilla', '安奎拉': 'Anguilla',
    '蒙特塞拉特': 'Montserrat', '蒙哲臘': 'Montserrat', '津巴布韋': 'Zimbabwe', '辛巴威': 'Zimbabwe', '津巴布韦': 'Zimbabwe',
    '美屬薩摩亞': 'American Samoa', '聖誕島': 'Christmas Island', '福克蘭群島': 'Falkland Islands', '馬爾維納斯群島': 'Falkland Islands', '法屬圭亞那': 'French Guiana',
    '荷屬安地列斯': 'Netherlands Antilles', '紐埃': 'Niue', '紐埃島': 'Niue', '諾福克島': 'Norfolk Island', '北馬里亞納群島': 'Northern Mariana Islands', '北馬利安納群島': 'Northern Mariana Islands',
    '西撒哈拉': 'Western Sahara', '大溪地': 'French Polynesia',
})
# 沒有自己機場的小國：指到最近的主要機場(摩納哥靠尼斯、梵蒂岡靠羅馬⋯)
TOURIST_ALIAS.update({
    '摩納哥': 'NCE', '聖馬利諾': 'RMI', '聖馬力諾': 'RMI', '列支敦士登': 'ZRH', '列支敦斯登': 'ZRH', '安道爾': 'BCN',
    '梵蒂岡': 'FCO', '科索沃': 'PRN',
    # 沒有機場的屬地：指到最近、有航班的機場(托克勞靠薩摩亞，要搭船；皮特凱恩靠法屬玻里尼西亞的甘比爾群島)
    '托克勞': 'APW', '托克勞群島': 'APW', '皮特凱恩群島': 'GMR', '皮特凱恩': 'GMR',
})
COUNTRY_NAME_EN.update({'馬裡': 'Mali', '塞舌尔': 'Seychelles', '瓦利斯和富圖納群島': 'Wallis and Futuna', '瓦利斯和富圖那群島': 'Wallis and Futuna', '瓦利斯及富圖納': 'Wallis and Futuna', '瓦利斯和富圖納': 'Wallis and Futuna', '瓦利斯群島和富圖那群島': 'Wallis and Futuna', '法屬蓋亞那': 'French Guiana', '法屬圭亞納': 'French Guiana', '德意志': 'Germany', '法蘭西': 'France', '大英': 'United Kingdom'})

# 國家的官方全名後綴(阿根廷共和國、玻利維亞多民族國、委內瑞拉玻利瓦爾共和國⋯)：搜不到整串時，去掉後綴用簡稱再找
_OFFICIAL_SUFFIXES = ('合眾國', '玻利瓦爾共和國', '玻利瓦共和國', '東岸共和國', '合作共和國', '社會主義共和國', '人民共和國', '聯邦共和國',
                      '民主共和國', '多民族國', '共和國', '聯合王國', '王國', '公國', '聯邦', '自治區', '國')


def canonical_country_keyword(keyword):
    """官方全名轉成簡稱：「阿根廷共和國」->「阿根廷」。整串已經認得(例如「剛果民主共和國」)就原樣回傳；
    去掉後綴後還是認不得，也原樣回傳，不影響一般城市/機場名稱的搜尋。"""
    keyword = (keyword or "").strip()
    if not keyword or keyword in COUNTRY_NAME_EN:
        return keyword
    for suffix in _OFFICIAL_SUFFIXES:
        if keyword.endswith(suffix) and len(keyword) > len(suffix) and keyword[:-len(suffix)] in COUNTRY_NAME_EN:
            return keyword[:-len(suffix)]
    return keyword
COUNTRY_AIRPORT_LIMIT = 6  # 國際機場超過這個數量的大國(日本、美國⋯)太籠統，不提供「整個國家」的查法，請使用者選城市



def country_airports(name, top_if_many=False):
    """整個國家的機場(例如「冰島」)；國際機場超過 COUNTRY_AIRPORT_LIMIT 個的大國，預設回傳空清單(請使用者選城市)，
    top_if_many=True 時改回傳航線最多的前 COUNTRY_AIRPORT_LIMIT 個機場(使用者直接打國家名稱就搜尋時用)。
    已經有手動整理成城市的名稱(例如香港)不當成國家處理。"""
    english = COUNTRY_NAME_EN.get((name or "").strip())
    if not english or (name or "").strip() in CITY_IATA:
        return []
    found = airports.get_country_airports(english)
    if len(found) <= COUNTRY_AIRPORT_LIMIT:
        return found
    return found[:COUNTRY_AIRPORT_LIMIT] if top_if_many else []


def region_airport_codes(region_name):
    """地區名稱(例如「北海道」) -> 底下所有城市機場代碼聯集的逗號字串；不是地區名稱就回傳 None。"""
    cities = REGION_CITIES.get((region_name or "").strip())
    if not cities:
        country_found = country_airports(region_name, top_if_many=True)
        return ",".join(a["iata"] for a in country_found) if country_found else None
    codes = []
    for city in cities:
        city_codes = airports.get_city_airport_codes(city, "Japan")
        if city_codes:
            codes.extend(city_codes.split(","))
    return ",".join(codes) if codes else None


def _broaden_to_city_siblings(code):
    """選到單一機場代碼時，自動擴大成「這個機場所在城市的所有機場」一起查(用逗號接起來)，
    這樣搜尋結果頁的「機場」篩選才會有其他機場的真實資料可以切換(例如搜尋「羽田機場」時，
    也會一起把成田機場的航班撈回來，使用者可以在篩選裡選要不要連成田一起看)，不用為了
    「順便看看其他機場」而多花一次查詢額度。只有一個機場的城市(大多數情況)就是原樣回傳。"""
    airport = airports.get_airport(code)
    if not airport:
        return code
    codes = airports.get_city_airport_codes(airport["city"], airport["country"])
    return codes or code


def transfer_hub(keyword):
    """使用者選了沒有國際航班(或根本沒有定期航班)的小機場時，改用最近的國際機場(轉運站)查詢，
    回傳 (新的搜尋關鍵字, 給使用者看的說明)；不是這種小機場就原樣回傳 (keyword, None)。
    - 台灣離島等有固定轉運站的：國內段是另外購買的機票。
    - 其他航線資料裡完全沒有定期航班的機場：找離它最近、航線夠多的機場，中間的地面交通請旅客自行安排。"""
    codes = [c for c in (to_iata(keyword) or "").split(",") if c]
    if not codes:
        return keyword, None
    small = codes[0]

    def label(code):
        info = airports.get_airport(code) or {}
        return AIRPORT_NAME_ZH.get(code) or info.get("name_zh") or info.get("name") or code

    if len(codes) == 1 and small in airports.TRANSFER_HUBS:
        hub = airports.TRANSFER_HUBS[small]
        note = (f"{label(small)}沒有國際航班，已改用 {label(hub)} 查詢。{label(small)}與{label(hub)}之間的國內段"
                "需要另外購買機票，請預留足夠的轉機時間。")
        return f"{label(hub)} ({hub})", note

    # 這個城市所有的機場都沒有定期航班(單一機場會被展開成同城市所有機場，所以要全部都沒有才算)
    if all(airports.get_airport(c) and not airports.has_service(c) for c in codes):
        found = airports.nearest_service_airport(small)
        if found:
            hub, km = found[0]["iata"], found[1]
            note = (f"{label(small)}目前沒有定期航班，已改用最近的 {label(hub)}（約 {km:.0f} 公里）查詢。"
                    f"{label(small)}與{label(hub)}之間請自行安排交通，並預留足夠的時間。")
            return f"{label(hub)} ({hub})", note
    return keyword, None


def to_iata(city_keyword):
    """把中文城市關鍵字、使用者直接輸入的三碼機場代碼、「City (IATA)」這種自動完成選單選出來的
    單一機場格式，或是「城市（所有機場）」這種選了「所有機場」的格式，轉成 IATA 代碼；
    回傳值可能是逗號接起來的好幾個代碼(SerpApi 的 departure_id/arrival_id 支援這樣傳，
    會把這些機場的航班混在一起回傳)——選到單一機場時也會自動擴大成同城市的所有機場，
    詳見 _broaden_to_city_siblings()。查不到就回傳 None。
    常見中文城市名先查 CITY_IATA(約 80 個)，查不到再查 airports.py 的全球機場資料庫
    (約 6000 筆真實機場資料，含英文城市名/機場名)，這樣全世界的城市/機場都搜得到，
    不是只有手動整理的那 80 個。"""
    city_keyword = (city_keyword or "").strip()
    if not city_keyword:
        return None
    if city_keyword.endswith(ALL_AIRPORTS_SUFFIX):
        city_name = city_keyword[: -len(ALL_AIRPORTS_SUFFIX)].strip()
        codes = region_airport_codes(city_name) or airports.get_city_airport_codes(to_english_city_name(city_name))
        if codes:
            return codes
        city_keyword = city_name  # 全球機場資料庫查不到這個城市，退回當一般城市名字查(用 CITY_IATA)
    region_codes = region_airport_codes(city_keyword)
    if region_codes:
        return region_codes
    bracket_match = re.search(r"\(([A-Za-z]{3})\)\s*$", city_keyword)
    if bracket_match:
        return _broaden_to_city_siblings(bracket_match.group(1).upper())
    # 要限制只比對 ASCII 英文字母，不能只檢查長度是不是 3：Python 的 str.isalpha() 連中文字也算「字母」，
    # 像「新加坡」「洛杉磯」剛好都是 3 個中文字，之前這裡會誤判成「使用者直接輸入了機場代碼」，
    # 原樣大寫回傳中文字(根本不是合法代碼)，導致這些城市的查詢全部失敗，要繞過下面 CITY_IATA 對照表。
    if re.fullmatch(r"[A-Za-z]{3}", city_keyword):
        return _broaden_to_city_siblings(city_keyword.upper())
    if city_keyword in TOURIST_ALIAS:
        return _broaden_to_city_siblings(TOURIST_ALIAS[city_keyword])
    if city_keyword in CITY_IATA:
        return _broaden_to_city_siblings(CITY_IATA[city_keyword])
    for name, code in CITY_IATA.items():
        if name in city_keyword or city_keyword in name:
            return _broaden_to_city_siblings(code)
    # 全球機場資料庫是英文資料，中文關鍵字要先查 CITY_NAME_EN 轉成英文城市名才查得到——
    # 不然像「函館」這種沒有手動整理進 CITY_IATA 的城市，就算 CITY_NAME_EN 裡有對照也永遠查不到，
    # 因為直接拿中文字去比對英文資料庫本來就不會比中。
    found = airports.find_iata_by_keyword(to_english_city_name(city_keyword))
    if not found:
        found = airports.find_iata_by_keyword(city_keyword)  # 保險：萬一本來就是英文關鍵字
    return _broaden_to_city_siblings(found) if found else None


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

