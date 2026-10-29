"""城市中文關鍵字 <-> IATA 機場代碼對照表，給 Amadeus 查詢、Skyscanner 比價連結共用。"""
from urllib.parse import urlencode

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


def to_iata(city_keyword):
    """把中文城市關鍵字(或使用者直接輸入的三碼機場代碼)轉成 IATA 代碼；查不到就回傳 None。"""
    city_keyword = (city_keyword or "").strip()
    if not city_keyword:
        return None
    if len(city_keyword) == 3 and city_keyword.isalpha():
        return city_keyword.upper()
    if city_keyword in CITY_IATA:
        return CITY_IATA[city_keyword]
    for name, code in CITY_IATA.items():
        if name in city_keyword or city_keyword in name:
            return code
    return None


def skyscanner_search_url(origin_keyword, destination_keyword, depart_date, return_date=None, pax=1):
    """組出 Skyscanner 的機票比價搜尋結果網址（純粹組網址，不是在呼叫 API 或爬蟲，
    使用者點了只是被導去 Skyscanner 自己的頁面，等同於自己手動在上面搜尋同一條航線），
    讓使用者在 Skyscanner 上比價、完成真正的訂票，我們就不用自己寫金流／結帳流程。
    查不到城市代碼或沒填日期就回傳 None，呼叫端就不要顯示這顆按鈕。"""
    origin = to_iata(origin_keyword)
    destination = to_iata(destination_keyword)
    if not origin or not destination or not depart_date:
        return None

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
