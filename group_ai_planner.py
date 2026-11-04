"""Member-facing AI itinerary drafts. Suggestions are never bookings or live quotes."""

from datetime import date
import json
import re

import requests

from config import ANTHROPIC_API_KEY, GEMINI_API_KEY


MODEL = "claude-haiku-4-5-20251001"
GEMINI_MODEL = "gemini-3.5-flash-lite"
ITEM_TYPES = {"attraction", "restaurant", "accommodation", "transport", "shopping", "meeting", "free_time", "other"}


def normalize_plan(payload, start_date, end_date):
    """Accept only bounded, schema-shaped suggestions before writing to the database."""
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("AI 未回傳有效的行程草稿，請再試一次。")
    items = []
    for entry in payload["items"][:35]:
        if not isinstance(entry, dict):
            continue
        try:
            item_date = date.fromisoformat(str(entry.get("date", "")))
        except ValueError:
            continue
        if not start_date <= item_date <= end_date:
            continue
        item_type = str(entry.get("type", "other"))
        title = str(entry.get("title", "")).strip()[:150]
        if item_type not in ITEM_TYPES or not title:
            continue
        start_time = str(entry.get("start_time") or "").strip()
        if start_time and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", start_time):
            start_time = ""
        try:
            cost = max(0, min(float(entry.get("estimated_cost") or 0), 10_000_000))
        except (TypeError, ValueError):
            cost = 0
        items.append({
            "date": item_date.isoformat(), "type": item_type, "title": title,
            "start_time": start_time or None,
            "address": str(entry.get("address") or "").strip()[:255] or None,
            "estimated_cost": round(cost, 2),
            "notes": str(entry.get("notes") or "").strip()[:1000] or None,
        })
    if not items:
        raise ValueError("AI 草稿沒有可儲存的每日項目，請調整需求後重試。")
    return {"summary": str(payload.get("summary") or "").strip()[:1000], "items": items}


def generate_plan(user_request, country, city, start_date, end_date, people_count, budget):
    if not (GEMINI_API_KEY or ANTHROPIC_API_KEY):
        raise RuntimeError("尚未設定 GEMINI_API_KEY 或 ANTHROPIC_API_KEY，暫時無法使用 AI 規劃。")
    prompt = (
        "你是旅遊行程草稿助手。所有顯示給旅客的內容請使用繁體中文。只回傳 JSON 物件，不要 Markdown。"
        "格式：{\"summary\":\"...\",\"items\":[{\"date\":\"YYYY-MM-DD\","
        "\"type\":\"attraction|restaurant|accommodation|transport|shopping|meeting|free_time|other\","
        "\"title\":\"...\",\"start_time\":\"HH:MM 或空字串\",\"address\":\"...\","
        "\"estimated_cost\":0,\"notes\":\"...\"}]}。"
        "每一天安排景點、交通與住宿建議（當天往返可不排住宿），最多 35 筆。"
        "不要捏造即時班次、空房、即時價格或宣稱已訂位；不確定的內容在 notes 標示須自行查證。"
        f"目的地：{country} {city}。日期：{start_date} 到 {end_date}。人數：{people_count}。"
        f"總預算參考：{budget} TWD。旅客需求：{user_request}"
    )
    if GEMINI_API_KEY:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8192}},
            timeout=35,
        )
        response.raise_for_status()
        candidates = response.json().get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        content = "".join(part.get("text", "") for part in parts).strip()
    else:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": MODEL, "max_tokens": 3500, "messages": [{"role": "user", "content": prompt}]},
            timeout=35,
        )
        response.raise_for_status()
        body = response.json()
        content = "".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("AI 未回傳可讀取的行程草稿，請再試一次。") from error
    return normalize_plan(payload, start_date, end_date)
