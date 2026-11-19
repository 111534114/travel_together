"""從一句自然語言的旅行需求，推測目的地、日期、人數與預算。

例如「12 月想跟朋友去東京 5 天，預算每人 3 萬」→ 日本／東京都、12 月的 5 天、2 人、6 萬。
只用規則比對，不呼叫 AI，速度快且結果可預期；推測不到的欄位保持空白，交給使用者補。
"""
import re
from datetime import date, timedelta

DEFAULT_DAYS = 3
MAX_DAYS = 7
DEFAULT_LEAD_DAYS = 14  # 沒寫日期時，預設兩週後出發

CN_DIGITS = {"一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

# 只寫國家時的預設城市（旅客最常去的主要城市）
COUNTRY_DEFAULT_CITY = {
    "日本": "東京都", "南韓": "首爾", "韓國": "首爾特別市", "台灣": "台北市", "泰國": "曼谷",
    "越南": "胡志明市", "香港": "香港", "新加坡": "新加坡", "法國": "法蘭西島大區", "英國": "英格蘭",
}

# 常見的口語地名 → 資料庫裡的城市名稱
CITY_ALIASES = {
    "巴黎": "法蘭西島大區", "倫敦": "英格蘭", "大阪": "大阪市", "沖繩": "沖繩縣", "濟州": "濟州特別自治道",
    "河內": "河內", "峴港": "峴港市", "西貢": "胡志明市", "普吉": "普吉府", "清邁": "清邁府", "九州": "福岡縣",
}

# 國家的口語說法
COUNTRY_ALIASES = {"韓國": "南韓"}

CITY_SUFFIXES = ("特別自治市", "特別自治道", "特別市", "廣域市", "大區", "市", "縣", "都", "府", "省", "道", "區")


def _norm(text):
    return (text or "").replace("臺", "台").strip()


def _number(token):
    """「5」「五」「十二」→ 整數。"""
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token in CN_DIGITS:
        return CN_DIGITS[token]
    if len(token) == 2 and token[0] == "十":
        return 10 + CN_DIGITS.get(token[1], 0)
    if len(token) == 2 and token[1] == "十":
        return CN_DIGITS.get(token[0], 0) * 10
    return None


NUM = r"(\d+|[一二兩三四五六七八九十]{1,2})"


def _city_keys(name):
    """一個城市可被比對的名稱：完整名稱，以及去掉「市／縣／都…」後至少兩個字的簡稱。"""
    name = _norm(name)
    keys = {name}
    for suffix in CITY_SUFFIXES:
        if name.endswith(suffix) and len(name) - len(suffix) >= 2:
            keys.add(name[: -len(suffix)])
            break
    return keys


def match_destination(text, countries, cities, popular_city_ids=()):
    """回傳 (country_id, city_id)，找不到時是 None。"""
    text = _norm(text)
    if not text:
        return None, None
    for alias, real in CITY_ALIASES.items():
        if alias in text:
            text += " " + real

    best = None  # (比對長度, 熱門程度, city)
    rank = {city_id: len(popular_city_ids) - i for i, city_id in enumerate(popular_city_ids)}
    for city in cities:
        for key in _city_keys(city["name"]):
            if key in text:
                score = (len(key), rank.get(city["city_id"], 0))
                if best is None or score > best[0]:
                    best = (score, city)
    if best:
        city = best[1]
        return city["country_id"], city["city_id"]

    country = None
    for alias, real in COUNTRY_ALIASES.items():
        if alias in text:
            text += " " + real
    for item in sorted(countries, key=lambda c: -len(_norm(c["name"]))):
        if _norm(item["name"]) in text:
            country = item
            break
    if not country:
        return None, None
    return country["country_id"], default_city_id(country, cities, popular_city_ids)


def default_city_id(country, cities, popular_city_ids=()):
    """只知道國家時挑一個城市：先用常見主要城市，再用熱門程度，最後用第一個。"""
    in_country = [c for c in cities if c["country_id"] == country["country_id"]]
    if not in_country:
        return None
    preferred = COUNTRY_DEFAULT_CITY.get(_norm(country["name"]))
    for city in in_country:
        if _norm(city["name"]) == preferred:
            return city["city_id"]
    ids = {c["city_id"] for c in in_country}
    for city_id in popular_city_ids:
        if city_id in ids:
            return city_id
    return in_country[0]["city_id"]


def match_days(text):
    match = re.search(NUM + r"\s*天", text) or re.search(NUM + r"\s*日遊", text)
    if match:
        days = _number(match.group(1))
    else:
        match = re.search(NUM + r"\s*(?:晚|夜)", text)
        days = _number(match.group(1)) + 1 if match and _number(match.group(1)) else None
    if not days:
        return None
    return max(1, min(MAX_DAYS, days))


def match_start_date(text, today):
    """「12/5」「12月5日」→ 該日期；只有「12 月」→ 該月份第一個合理日期；過去的日期往明年推。"""
    earliest = today + timedelta(days=1)
    match = re.search(r"(\d{1,2})\s*[/月]\s*(\d{1,2})(?!\s*(?:天|晚|夜|人|位|\d))", text)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        for year in (today.year, today.year + 1):
            try:
                candidate = date(year, month, day)
            except ValueError:
                return None
            if candidate >= earliest:
                return candidate
        return None
    match = re.search(NUM + r"\s*月", text)
    month = _number(match.group(1)) if match else None
    if month and 1 <= month <= 12:
        year = today.year if month >= today.month else today.year + 1
        first = date(year, month, 1)
        return max(first, today + timedelta(days=7)) if (year, month) == (today.year, today.month) else first
    if "下週" in text or "下禮拜" in text or "下星期" in text:
        return today + timedelta(days=7 - today.weekday() + 5)  # 下週六
    if "這週末" in text or "週末" in text:
        return today + timedelta(days=max(1, 5 - today.weekday()))
    return None


def match_people(text):
    match = re.search(NUM + r"\s*(?:個)?(?:人|位)", text)
    if match:
        count = _number(match.group(1))
        if count and not text[match.start() - 2: match.start()].endswith("每"):
            return max(1, min(30, count))
    if re.search(r"自己|一個人|獨旅|單人", text):
        return 1
    if re.search(r"爸媽|父母", text):
        return 3
    if re.search(r"全家|家人", text):
        return 4
    if re.search(r"朋友|情侶|男友|女友|老公|老婆|另一半|兩個人", text):
        return 2
    return None


def match_budget(text, people):
    match = re.search(r"預算\s*(每人|每個人|一人)?\s*(?:大概|約|大約)?\s*(\d+(?:\.\d+)?)\s*(萬|千|k|K)?", text)
    if not match:
        return None
    amount = float(match.group(2)) * {"萬": 10000, "千": 1000, "k": 1000, "K": 1000}.get(match.group(3), 1)
    if match.group(1):
        amount *= people or 1
    return int(amount)


def infer(text, countries, cities, popular_city_ids=(), today=None):
    """推測結果；推不到的欄位不放進 dict。"""
    today = today or date.today()
    text = _norm(text)
    result = {}
    country_id, city_id = match_destination(text, countries, cities, popular_city_ids)
    if country_id:
        result["country_id"] = country_id
        country = next(c for c in countries if c["country_id"] == country_id)
        result["country_name"] = country["name"]
    if city_id:
        result["city_id"] = city_id
    start = match_start_date(text, today)
    days = match_days(text)
    if start or days:
        start = start or today + timedelta(days=DEFAULT_LEAD_DAYS)
        result["start_date"] = start
        result["end_date"] = start + timedelta(days=(days or DEFAULT_DAYS) - 1)
    people = match_people(text)
    if people:
        result["people_count"] = people
    budget = match_budget(text, people)
    if budget:
        result["budget"] = budget
    return result


def complete(text, countries, cities, popular_city_ids=(), today=None):
    """一定給出日期與人數（用預設值補），目的地推不到時才留空。"""
    today = today or date.today()
    result = infer(text, countries, cities, popular_city_ids, today)
    if "start_date" not in result:
        result["start_date"] = today + timedelta(days=DEFAULT_LEAD_DAYS)
        result["end_date"] = result["start_date"] + timedelta(days=DEFAULT_DAYS - 1)
    result.setdefault("people_count", 2)
    result.setdefault("budget", 0)
    return result
