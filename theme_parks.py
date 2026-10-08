import time  # 用來記錄快取抓取時間，判斷是否需要重新呼叫 API

import truststore  # 改用作業系統原生憑證庫驗證 SSL，修正 Python 3.13 誤判憑證無效的已知問題
truststore.inject_into_ssl()

import requests  # 匯入 requests，用來呼叫 ThemeParks.wiki 開放資料 API

# ThemeParks.wiki：免費、不需金鑰的樂園開放資料 API，收錄全球主要樂園(含迪士尼全系列)的即時營業時間。
# https://api.themeparks.wiki/docs/v1
SCHEDULE_URL = "https://api.themeparks.wiki/v1/entity/{entity_id}/schedule"

CACHE_TTL_SECONDS = 60 * 60  # 快取存活時間(1小時)：營業時間不會頻繁變動，不用每次都打 API

# 先收錄迪士尼全系列樂園，之後要加其他樂園(環球影城等)只要在這裡加一筆即可。
DISNEY_PARKS = [
    {"id": "tokyo-disneyland", "name": "東京迪士尼樂園", "entity_id": "3cc919f1-d16d-43e0-8c3f-1dd269bd1a42"},
    {"id": "tokyo-disneysea", "name": "東京迪士尼海洋", "entity_id": "67b290d5-3478-4f23-b601-2f8fb71ba803"},
    {"id": "shanghai-disneyland", "name": "上海迪士尼樂園", "entity_id": "ddc4357c-c148-4b36-9888-07894fe75e83"},
    {"id": "hongkong-disneyland", "name": "香港迪士尼樂園", "entity_id": "bd0eb47b-2f02-4d4d-90fa-cb3a68988e3b"},
    {"id": "disneyland-paris", "name": "巴黎迪士尼樂園", "entity_id": "dae968d5-630d-4719-8b06-3d107e944401"},
    {"id": "disneyland-anaheim", "name": "美國加州迪士尼樂園", "entity_id": "7340550b-c14d-4def-80bb-acdb51d49a66"},
    {"id": "disney-california-adventure", "name": "美國加州冒險樂園", "entity_id": "832fcd51-ea19-4e77-85c7-75d5843b127c"},
    {"id": "magic-kingdom", "name": "美國佛州迪士尼：神奇王國", "entity_id": "75ea578a-adc8-4116-a54d-dccb60765ef9"},
    {"id": "epcot", "name": "美國佛州迪士尼：EPCOT", "entity_id": "47f90d2c-e191-4239-a466-5892ef59a88b"},
]

_PARKS_BY_ID = {park["id"]: park for park in DISNEY_PARKS}

_schedule_cache = {}  # {entity_id: (抓取時間, 回傳的 schedule 清單)}


def get_disney_parks():  # 提供給前端下拉選單使用的樂園清單
    return [{"id": park["id"], "name": park["name"]} for park in DISNEY_PARKS]


def get_park_hours(park_id, target_date):  # 查詢指定樂園在指定日期的開園／閉園時間，查不到回傳 None
    park = _PARKS_BY_ID.get(park_id)
    if not park:
        return None

    entity_id = park["entity_id"]
    cached = _schedule_cache.get(entity_id)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        schedule = cached[1]
    else:
        try:
            response = requests.get(SCHEDULE_URL.format(entity_id=entity_id), timeout=8)
            response.raise_for_status()
            schedule = response.json().get("schedule", [])
        except requests.RequestException as error:
            print("查詢樂園開放時間失敗：", error)
            if not cached:
                return None
            schedule = cached[1]  # 仍須篩選指定日期，不能把整份班表直接回傳給前端。
        else:
            _schedule_cache[entity_id] = (time.time(), schedule)

    for day in schedule:
        if day.get("date") == target_date and day.get("type") == "OPERATING":
            opening = day.get("openingTime")
            closing = day.get("closingTime")
            return {
                "park_name": park["name"],
                "date": target_date,
                "opening_time": opening[11:16] if opening else None,  # 只取 HH:MM，不需要時區偏移量
                "closing_time": closing[11:16] if closing else None,
            }
    return None
