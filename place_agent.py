"""資料補齊 Agent：替景點／餐廳／住宿找出缺漏的地址、座標、營業時間、介紹與圖片。

流程（每筆資料）：
1. 用「名稱 + 城市 + 國家」查 Google 地點，只填入目前是空的欄位（不覆蓋人工資料）。
2. Google 沒有提供介紹時，請 AI 依名稱與地點寫一段簡短介紹（標註需人工確認）。
3. 有代表照就下載存檔當圖片。
任何一步失敗都只略過該欄位，不會讓整批中斷。
"""

import google_places
from ai_client import AIUnavailable, ai_ready, ask_json
from utils import save_image_from_url

# 各類型可以補的欄位（資料表欄位名稱）
FILLABLE = {
    "attraction": ("address", "latitude", "longitude", "opening_hours", "description", "website_url", "image_path"),
    "restaurant": ("address", "latitude", "longitude", "opening_hours", "description", "website_url", "image_path", "price_level"),
    "accommodation": ("address", "latitude", "longitude", "description", "website_url", "image_path"),
}
FIELD_LABELS = {"address": "地址", "latitude": "座標", "opening_hours": "營業時間", "description": "介紹",
                "website_url": "網站", "image_path": "圖片", "price_level": "價位"}
IMAGE_FOLDERS = {"attraction": "attractions", "restaurant": "restaurants", "accommodation": "accommodations"}
TYPE_LABELS = {"attraction": "景點", "restaurant": "餐廳", "accommodation": "住宿"}


def _empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def autofill(item_type, row):
    """回傳 (要更新的欄位 dict, 說明訊息 list)。row 需含 name、city_name、country_name 與可補欄位的目前值。"""
    fields = FILLABLE[item_type]
    missing = [f for f in fields if _empty(row.get(f))]
    if "longitude" in missing and "latitude" not in missing:
        missing.remove("longitude")
    if not missing:
        return {}, []
    updates, notes = {}, []
    query = " ".join(part for part in (row.get("name"), row.get("city_name"), row.get("country_name")) if part)
    place = None
    if google_places.is_configured():
        try:
            raw = google_places.search_place(query)
            place = google_places.extract_place_fields(raw) if raw else None
            if not place:
                notes.append("Google 地點查無資料")
        except Exception as error:  # Google 查詢失敗就改靠 AI 補介紹
            notes.append(f"Google 地點查詢失敗：{error}")
    if place:
        for field in ("address", "opening_hours", "description", "website_url", "price_level"):
            if field in missing and place.get(field):
                updates[field] = place[field]
        if "latitude" in missing and place.get("latitude") is not None and place.get("longitude") is not None:
            updates["latitude"], updates["longitude"] = place["latitude"], place["longitude"]
        if "image_path" in missing and place.get("photo_name"):
            try:
                path = save_image_from_url(google_places.build_photo_url(place["photo_name"]), IMAGE_FOLDERS[item_type])
                if path:
                    updates["image_path"] = path
            except Exception as error:
                notes.append(f"圖片下載失敗：{error}")
    if "description" in missing and "description" not in updates and ai_ready():
        try:
            payload = ask_json(
                "你是旅遊網站的資料編輯，請用繁體中文為下列地點寫一段 60 到 120 字的介紹，"
                "內容要客觀，不確定的資訊（價格、營業時間、活動）不要寫。只回傳 JSON：{\"description\":\"...\"}。"
                f"類型：{TYPE_LABELS[item_type]}。名稱：{row.get('name')}。地點：{row.get('city_name')}，{row.get('country_name')}。"
                + (f"地址：{updates.get('address') or row.get('address')}。" if (updates.get("address") or row.get("address")) else "")
            )
            text = str(payload.get("description") or "").strip()
            if text:
                updates["description"] = text[:1000] + "（AI 產生，請人工確認）"
        except AIUnavailable as error:
            notes.append(f"AI 介紹產生失敗：{error}")
    return updates, notes


def describe(updates):
    labels = []
    for field in updates:
        label = FIELD_LABELS.get(field)
        if label and label not in labels:
            labels.append(label)
    return "、".join(labels)
