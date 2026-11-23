"""住宿目的地：輸入國家名稱(例如「英國」)時，列出該國的熱門城市(像 Agoda 的「倫敦, 英國　人氣王」)。
熱門程度用機場資料推算：同一個城市底下所有機場的航線數加總，航線越多代表越大、越多人去的城市。
中文城市名先查手動整理的對照表，查不到再用翻譯(有快取)，翻不出來就退回英文原名。"""
import json
import os
from concurrent.futures import ThreadPoolExecutor

import airports
import flight_links

_zh_cache = {}  # {英文城市名: 中文}
try:  # 預先批次翻好的中文城市名(database/city_names_zh.json)：不用在使用者輸入時才臨時呼叫不穩定的翻譯服務
    with open(os.path.join(os.path.dirname(__file__), "database", "city_names_zh.json"), encoding="utf-8") as _f:
        _FILE_ZH = json.load(_f)
except (OSError, ValueError):
    _FILE_ZH = {}
# 翻譯會翻錯的城市名(例如 Nice 會被翻成「好的」)，還有機場名稱跟旅客熟悉的城市不同的情況(凱夫拉維克機場其實就是雷克雅未克)
_MANUAL_ZH = {
    "Nice": "尼斯", "Keflavik": "雷克雅未克", "Reykjavik": "雷克雅未克", "Split": "斯普利特", "Bologna": "波隆那",
    "Florence": "佛羅倫斯", "Venice": "威尼斯", "Naples": "那不勒斯", "Cologne": "科隆", "Munich": "慕尼黑",
    "Lyon": "里昂", "Porto": "波多", "Seville": "塞維亞", "Valencia": "瓦倫西亞", "Phuket": "普吉島",
}


def _city_zh(city):
    """英文城市名 -> 中文：手動對照 > 機場城市對照 > 預先用維基數據批次查好的檔案。查不到回傳 None
    (不再即時呼叫翻譯服務：它不穩定、常被限流，而且機器翻譯的城市名常常不對)。"""
    return _MANUAL_ZH.get(city) or flight_links.to_chinese_city_name(city) or _FILE_ZH.get(city)


# 手動訂的各國熱門目的地(中文，依受歡迎程度排序)；沒有列在這裡的國家，才用機場資料推算
CURATED = {
    "Australia": ["雪梨", "墨爾本", "布里斯本", "黃金海岸", "凱恩斯", "伯斯", "阿德萊德"],
    "New Zealand": ["奧克蘭", "皇后鎮", "基督城", "威靈頓", "羅托魯瓦", "但尼丁"],
    "Papua New Guinea": ["莫士比港", "萊城", "臘包爾", "馬當"],
    "Fiji": ["楠迪", "蘇瓦", "丹娜鷗島", "珊瑚海岸"],
    "Solomon Islands": ["荷尼阿拉", "吉佐"],
    "Vanuatu": ["維拉港", "聖埃斯皮里圖島"],
    "Samoa": ["阿皮亞"],
    "Kiribati": ["塔拉瓦", "聖誕島"],
    "Tonga": ["努庫阿洛法"],
    "Marshall Islands": ["馬朱羅", "誇賈林"],
    "Palau": ["科羅爾"],
    "Nauru": ["亞倫"],
    "Tuvalu": ["富納富提"],
    # 城市國家與屬地(機場資料推算不出「城市」，改列知名區域)
    "Singapore": ["濱海灣", "烏節路", "聖淘沙", "牛車水", "小印度"], "Hong Kong": ["尖沙咀", "中環", "銅鑼灣", "旺角", "香港仔"],
    "Macau": ["澳門半島", "路氹城", "氹仔"], "Malta": ["瓦萊塔", "斯利馬", "聖朱利安斯", "戈佐島"], "Gibraltar": ["直布羅陀"],
    "Guam": ["杜夢灣", "哈加特尼亞"], "Northern Mariana Islands": ["塞班島", "天寧島"], "Bermuda": ["漢密爾頓", "聖喬治"],
    "British Virgin Islands": ["托爾托拉島", "維京戈達島"], "Falkland Islands": ["史丹利港"], "Isle of Man": ["道格拉斯", "皮爾"],
    "Christmas Island": ["飛魚灣"], "Wallis and Futuna": ["馬塔烏圖"],
    "Bahrain": ["麥納瑪", "穆哈拉格"], "Brunei": ["斯里巴加灣市"], "Kuwait": ["科威特市"], "Syria": ["大馬士革", "阿勒坡"],
    "Palestine": ["伯利恆", "拉姆安拉"], "Moldova": ["基希涅夫"], "Djibouti": ["吉布地市"], "El Salvador": ["聖薩爾瓦多", "聖塔安娜", "蘇奇托托"],
    # 重要旅遊國家：機場資料推算出來的城市太少，手動補
    "Hungary": ["布達佩斯", "德布勒森", "巴拉頓湖", "塞格德"], "Jamaica": ["蒙特哥貝", "尼格瑞爾", "京士頓", "奧丘里奧斯"],
    "Guatemala": ["瓜地馬拉市", "安地瓜", "佛羅瑞斯"], "Belize": ["伯利茲市", "聖佩德羅", "聖伊格納西奧"],
    "Armenia": ["葉里溫", "久姆里"], "Azerbaijan": ["巴庫", "加巴拉"], "Albania": ["地拉那", "薩蘭達", "發羅拉"],
    "Aruba": ["棕櫚灘", "奧拉涅斯塔德"], "Cayman Islands": ["七英里海灘", "喬治城"], "Cook Islands": ["拉羅湯加", "艾圖塔基島"],
    "Bhutan": ["帕羅", "辛布", "普那卡"], "Belarus": ["明斯克", "布列斯特"], "Haiti": ["太子港", "海地角"],
    "Barbados": ["橋鎮", "聖勞倫斯灣"],
    # 亞洲(機場推算會出現行政區或冷門小鎮，例如阿曼會出現「加薩」、孟加拉會出現「賽德普爾烏帕齊拉」)
    "Bangladesh": ["達卡", "吉大港", "科克斯巴扎爾", "錫爾赫特"], "Oman": ["馬斯喀特", "塞拉萊", "尼茲瓦"],
    "Iran": ["德黑蘭", "伊斯法罕", "設拉子", "馬什哈德"], "Iraq": ["巴格達", "艾比爾", "巴斯拉", "納傑夫"],
    "Afghanistan": ["喀布爾", "赫拉特", "馬扎里沙里夫"], "Maldives": ["馬列", "馬富施", "阿杜市"],
    "Kyrgyzstan": ["比什凱克", "奧什", "伊塞克湖"], "Lebanon": ["貝魯特", "朱尼耶", "巴勒貝克"], "Mongolia": ["烏蘭巴托", "哈拉和林"],
    "Tajikistan": ["杜尚貝", "苦盞"], "Yemen": ["沙那", "亞丁", "穆卡拉", "索科特拉島"],
    "Saudi Arabia": ["利雅德", "吉達", "麥地那", "麥加", "達曼"], "Laos": ["永珍", "琅勃拉邦", "巴色", "萬榮"],
    "Pakistan": ["伊斯蘭馬巴德", "喀拉蚩", "拉合爾", "罕薩"], "Kazakhstan": ["阿拉木圖", "阿斯塔納", "希姆肯特", "阿克套"],
    # 非洲(機場推算會出現冷門小鎮，例如模里西斯會變成「馬尼安平原」)
    "Mauritius": ["路易港", "大灣", "貝爾馬爾", "勒莫恩半島"], "Namibia": ["溫荷克", "斯瓦科普蒙德", "華維斯灣", "索蘇斯維萊"],
    "Tanzania": ["三蘭港", "桑給巴爾", "阿魯沙", "莫希"], "Cape Verde": ["普拉亞", "薩爾島", "明德盧", "博阿維斯塔島"],
    "Algeria": ["阿爾及爾", "奧蘭", "君士坦丁", "安納巴"], "Angola": ["魯安達", "本格拉", "洛比托"],
    "Ethiopia": ["阿迪斯阿貝巴", "拉利貝拉", "貢德爾", "巴赫達爾"], "Tunisia": ["突尼斯", "蘇斯", "哈馬馬特", "傑爾巴島", "迦太基"],
    "Libya": ["的黎波里", "班加西"], "Madagascar": ["安塔那那利佛", "諾西貝", "圖阿馬西納", "安齊拉納納"],
    "Mozambique": ["馬布多", "維蘭庫洛", "彭巴", "貝拉"], "Congo (Kinshasa)": ["金夏沙", "盧本巴希", "戈馬"],
    "Cameroon": ["杜阿拉", "雅溫德", "克里比"], "Zimbabwe": ["哈拉雷", "維多利亞瀑布", "布拉瓦約"],
    "Zambia": ["路沙卡", "利文斯敦", "恩多拉"], "Sudan": ["喀土穆", "蘇丹港"], "Somalia": ["摩加迪休", "哈爾格薩"],
    "Seychelles": ["維多利亞", "普拉斯蘭島", "拉迪格島"], "Swaziland": ["姆巴巴內", "曼齊尼"],
    "Botswana": ["嘉柏隆里", "卡薩內", "馬翁", "奧卡萬戈三角洲"], "Mali": ["巴馬科", "廷巴克圖", "莫普提"],
    "Senegal": ["達卡", "聖路易", "濟金紹爾"], "Ghana": ["阿克拉", "庫馬西", "海岸角"],
    "Nigeria": ["拉哥斯", "阿布加", "哈科特港", "卡諾"], "Uganda": ["坎帕拉", "恩德培", "金賈"], "Rwanda": ["吉佳利", "尚古古", "魯亨蓋里"],
    # 南美洲
    "Paraguay": ["亞松森", "東方市", "恩卡納西翁"], "Suriname": ["帕拉馬里博", "阿爾比納"],
    "Venezuela": ["加拉加斯", "馬拉開波", "瓦倫西亞", "瑪格麗塔島", "梅里達"],
    "Bolivia": ["拉巴斯", "烏尤尼", "蘇克雷", "聖克魯斯", "科恰班巴"], "Ecuador": ["基多", "瓜亞基爾", "加拉巴哥群島", "昆卡", "蒙塔尼塔"],
    "Uruguay": ["蒙特維多", "埃斯特角城", "科洛尼亞"], "Guyana": ["喬治城"], "French Guiana": ["開雲"],
    # 北美洲與加勒比海
    "Costa Rica": ["聖荷西", "利比里亞", "拉福爾圖納", "蒙特維爾德", "馬紐爾安東尼奧"],
    "Honduras": ["羅阿坦島", "特古西加爾巴", "聖佩德羅蘇拉", "拉塞瓦"], "Panama": ["巴拿馬城", "博卡斯德爾托羅", "戴維", "科隆"],
    "Nicaragua": ["馬拿瓜", "格拉納達", "里昂"], "Antigua and Barbuda": ["聖約翰", "英國港", "喬利港"],
    "Dominica": ["羅梭", "波茨茅斯"], "Grenada": ["聖喬治", "大安斯海灘"], "Saint Kitts and Nevis": ["巴斯特爾", "尼維斯島"],
    "Saint Lucia": ["卡斯翠", "蘇弗里耶爾", "格羅斯島"], "Saint Vincent and the Grenadines": ["金斯敦", "貝基亞島", "卡努安島"],
    "Trinidad and Tobago": ["西班牙港", "多巴哥島", "斯卡伯勒"],
    # 沒有自己機場、或不被普遍承認的地區(見 EXTRA_COUNTRIES)
    "Andorra": ["安道爾城", "恩坎普", "卡尼略", "奧爾迪諾"], "Monaco": ["蒙地卡羅", "摩納哥城"],
    "San Marino": ["聖馬利諾市", "博爾戈馬焦雷"], "Kosovo": ["普里斯提納", "普里茲倫", "佩奇"],
    "Transnistria": ["蒂拉斯波爾", "本傑里"], "Abkhazia": ["蘇呼米", "加格拉", "皮聰達"], "South Ossetia": ["茨欣瓦利"],
    "Northern Cyprus": ["凱里尼亞", "法馬古斯塔", "北尼科西亞"],
    # 歐洲：機場推算出來的城市太少或有誤(塞爾維亞的機場資料混進了科索沃的普里斯提納)
    "Serbia": ["貝爾格勒", "諾維薩德", "尼什"], "Latvia": ["里加", "尤爾馬拉", "利耶帕亞"], "Macedonia": ["史高比耶", "奧赫里德"],
    "Montenegro": ["波德里查", "科托爾", "布德瓦", "蒂瓦特"], "Slovenia": ["盧比安納", "布萊德", "馬里博爾"],
    "Slovakia": ["布拉提斯拉瓦", "科希策", "高塔特拉山"], "Ukraine": ["基輔", "利維夫", "奧德薩", "哈爾科夫", "第聶伯"],
    "Luxembourg": ["盧森堡市"], "Moldova": ["基希涅夫", "蒂拉斯波爾"],
    # 台灣旅客最常去的國家：手動訂(依機場推算會有錯，例如加拿大會出現「倫敦」「雪梨」、法國會出現「巴塞爾」)
    "Taiwan": ["台北", "台中", "高雄", "台南", "花蓮", "宜蘭", "墾丁"],
    "Japan": ["東京", "大阪", "京都", "福岡", "札幌", "沖繩", "名古屋"],
    "South Korea": ["首爾", "釜山", "濟州島", "大邱", "仁川"],
    "Thailand": ["曼谷", "普吉島", "清邁", "芭達雅", "蘇美島", "喀比", "華欣"],
    "Vietnam": ["河內", "胡志明市", "峴港", "芽莊", "會安", "富國島", "大叻"],
    "Malaysia": ["吉隆坡", "檳城", "亞庇", "蘭卡威", "馬六甲", "新山", "古晉"],
    "Indonesia": ["峇里島", "雅加達", "日惹", "龍目島", "泗水", "萬隆"],
    "Philippines": ["馬尼拉", "宿霧", "長灘島", "薄荷島", "巴拉望", "克拉克"],
    "China": ["上海", "北京", "廣州", "深圳", "成都", "杭州", "西安", "重慶"],
    "India": ["新德里", "孟買", "齋浦爾", "果阿", "班加羅爾", "加爾各答"],
    "Turkey": ["伊斯坦堡", "安塔利亞", "卡帕多奇亞", "安卡拉", "伊茲密爾", "博德魯姆"],
    "United Arab Emirates": ["杜拜", "阿布達比", "沙迦", "拉斯海瑪"],
    "United States": ["紐約", "洛杉磯", "舊金山", "拉斯維加斯", "檀香山", "西雅圖", "芝加哥", "邁阿密", "奧蘭多"],
    "Canada": ["多倫多", "溫哥華", "蒙特婁", "卡加利", "渥太華", "魁北克市", "班夫"],
    "Mexico": ["墨西哥城", "坎昆", "圖盧姆", "卡波聖盧卡", "瓜達拉哈拉", "蒙特雷"],
    "Brazil": ["里約熱內盧", "聖保羅", "薩爾瓦多", "福塔雷薩", "巴西利亞", "伊瓜蘇"],
    "Argentina": ["布宜諾斯艾利斯", "門多薩", "巴里洛切", "烏斯懷亞", "哥多華", "薩爾塔"],
    "Peru": ["利馬", "庫斯科", "阿雷基帕", "馬丘比丘"],
    "Chile": ["聖地牙哥", "瓦爾帕萊索", "蓬塔阿雷納斯", "聖佩德羅德阿塔卡馬"],
    "Colombia": ["波哥大", "麥德林", "卡塔赫納", "卡利"],
    "United Kingdom": ["倫敦", "愛丁堡", "曼徹斯特", "伯明罕", "格拉斯哥", "利物浦", "牛津"],
    "France": ["巴黎", "尼斯", "里昂", "馬賽", "波爾多", "史特拉斯堡", "坎城"],
    "Italy": ["羅馬", "米蘭", "威尼斯", "佛羅倫斯", "那不勒斯", "波隆那", "西西里島"],
    "Spain": ["巴塞隆納", "馬德里", "塞維亞", "瓦倫西亞", "馬拉加", "帕爾馬", "格拉納達"],
    "Germany": ["柏林", "慕尼黑", "法蘭克福", "漢堡", "科隆", "杜塞道夫", "斯圖加特"],
    "Switzerland": ["蘇黎世", "日內瓦", "琉森", "茵特拉肯", "策馬特", "盧加諾", "巴塞爾"],
    "Austria": ["維也納", "薩爾斯堡", "因斯布魯克", "哈斯塔特", "格拉茨"],
    "Greece": ["雅典", "聖托里尼", "米克諾斯", "克里特島", "羅得島", "塞薩洛尼基"],
    "Portugal": ["里斯本", "波多", "法魯", "豐沙爾", "蓬塔德爾加達"],
    "Netherlands": ["阿姆斯特丹", "鹿特丹", "海牙", "烏特勒支", "恩荷芬"],
    "Belgium": ["布魯塞爾", "布魯日", "安特衛普", "根特"],
    "Czech Republic": ["布拉格", "布爾諾", "卡羅維瓦利", "庫特納霍拉"],
    "Poland": ["華沙", "克拉科夫", "格但斯克", "弗羅茨瓦夫"],
    "Russia": ["莫斯科", "聖彼得堡", "索契", "喀山"],
    "Egypt": ["開羅", "沙姆沙伊赫", "赫爾格達", "路克索", "亞斯文", "亞歷山卓"],
    "Morocco": ["馬拉喀什", "卡薩布蘭卡", "菲斯", "舍夫沙萬", "阿加迪爾", "丹吉爾"],
    "South Africa": ["開普敦", "約翰尼斯堡", "德班", "伊莉莎白港"],
    "Kenya": ["奈洛比", "蒙巴薩", "馬賽馬拉"],
    "Sri Lanka": ["可倫坡", "康提", "加勒", "錫吉里亞"],
    "Nepal": ["加德滿都", "博卡拉", "奇旺"],
    "Cambodia": ["暹粒", "金邊", "西哈努克市"],
    "Burma": ["仰光", "曼德勒", "蒲甘", "內比都"], "Myanmar": ["仰光", "曼德勒", "蒲甘", "內比都"],
    "Israel": ["特拉維夫", "耶路撒冷", "海法", "埃拉特"], "Jordan": ["安曼", "佩特拉", "亞喀巴", "死海"],
    "Iceland": ["雷克雅維克", "阿克雷里", "霍芬"], "Norway": ["奧斯陸", "卑爾根", "特羅姆瑟", "斯塔萬格"],
    "Sweden": ["斯德哥爾摩", "哥德堡", "馬爾默", "基律納"], "Denmark": ["哥本哈根", "奧胡斯", "歐登塞"],
    "Finland": ["赫爾辛基", "羅瓦涅米", "坦佩雷", "伊納里"], "Ireland": ["都柏林", "高威", "科克", "基拉尼"],
    "Croatia": ["杜布羅夫尼克", "斯普利特", "札格拉布", "普拉"], "Romania": ["布加勒斯特", "克盧日", "布拉索夫"],
    "Bulgaria": ["索菲亞", "瓦爾納", "布爾加斯"], "Cyprus": ["利馬索爾", "帕福斯", "拉納卡", "尼科西亞", "艾雅納帕"],
    "Uzbekistan": ["塔什干", "撒馬爾罕", "布哈拉"], "Georgia": ["提比里斯", "巴統"], "Mongolia": ["烏蘭巴托"],
}


# 機場資料裡沒有、但使用者會搜的國家與地區(各種寫法 -> 內部名稱，推薦城市用上面 CURATED 的手動名單)
EXTRA_COUNTRIES = {
    "安道爾": "Andorra", "安道爾公國": "Andorra", "摩納哥": "Monaco", "摩納哥公國": "Monaco", "聖馬利諾": "San Marino", "聖馬力諾": "San Marino",
    "科索沃": "Kosovo", "德涅斯特河沿岸": "Transnistria", "德涅斯特河沿岸地區": "Transnistria", "沿第聶伯河": "Transnistria",
    "外聶斯特里亞": "Transnistria", "阿布哈茲": "Abkhazia", "阿布哈茲共和國": "Abkhazia", "南奧塞梯": "South Ossetia", "南奧塞提亞": "South Ossetia",
    "北賽普勒斯": "Northern Cyprus", "北塞浦路斯": "Northern Cyprus", "北賽普勒斯土耳其共和國": "Northern Cyprus",
}


def country_of(keyword):
    """輸入的字剛好是某個國家名稱(中文或英文)就回傳 (英文國名, 中文國名)，否則 None。"""
    keyword = flight_links.canonical_country_keyword((keyword or "").strip())
    if not keyword:
        return None
    if keyword in EXTRA_COUNTRIES:
        return EXTRA_COUNTRIES[keyword], keyword
    country_en = flight_links.COUNTRY_NAME_EN.get(keyword) or airports.match_country_name(keyword)
    if not country_en:
        return None
    country_zh = next((zh for en, zh in flight_links.COUNTRY_ZH.items() if en == country_en), keyword)
    return country_en, country_zh


def popular_cities(country_en, limit=6):
    """熱門城市：手動整理過的熱門旅遊城市(flight_links.CITY_NAME_EN)排前面，其餘照機場航線數由多到少。
    只看航線數的話，美國第一名會變成轉機樞紐亞特蘭大，不是旅客想去的地方。"""
    totals = {}
    for airport in airports._airports:
        if airports.country_key(airport["country"]) == airports.country_key(country_en):
            totals[airport["city"]] = totals.get(airport["city"], 0) + int(airport.get("routes") or 0)
    curated = set(flight_links.CITY_NAME_EN.values())
    ranked = sorted((c for c, total in totals.items() if total > 0), key=lambda c: (c not in curated and c not in _MANUAL_ZH, -totals[c]))
    return ranked[:limit]


def suggestions(keyword, limit=6):
    """回傳給前端的選項清單；不是國家名稱或查不到城市就回傳空清單。"""
    found = country_of(keyword)
    if not found:
        return []
    country_en, country_zh = found
    curated = CURATED.get(country_en)
    if curated:
        names = curated[:limit + 1]
    else:
        # 多取幾個候選：沒有中文名稱的城市直接跳過(不顯示英文)，再往後補
        names = [name for name in (_city_zh(c) for c in popular_cities(country_en, limit * 2)) if name][:limit]
        if not names:
            return []
    items, seen = [], set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        items.append({
            "label": f"{name}, {country_zh}", "city": name, "country": country_zh,
            "sub": "城市", "value": f"{name} {country_zh}", "kind": "popular",
        })
    # 新加坡、香港這種城市國家：只會得到「新加坡, 新加坡」，沒有意義，交給一般的搜尋建議
    if len(items) == 1 and items[0]["city"] == country_zh:
        return []
    return items
