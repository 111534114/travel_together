"""共用的 AI 呼叫工具：送出提示（可附一張圖片），取回 JSON 物件。

優先使用 Google Gemini（GEMINI_API_KEY）；沒有設定時改用 Anthropic Claude（ANTHROPIC_API_KEY，需安裝 anthropic 套件）。
任何失敗都轉成 AIUnavailable，讓呼叫端可以退回不靠 AI 的規則計算，避免功能卡住。
"""

import base64
import json
import re
import time

import requests

from config import ANTHROPIC_API_KEY, GEMINI_API_KEY

GEMINI_MODEL = "gemini-3.5-flash-lite"
CLAUDE_MODEL = "claude-opus-5-5"


class AIUnavailable(Exception):
    """AI 沒設定、連不上或回傳內容無法解析。訊息可以直接顯示給使用者。"""


def ai_ready():
    return bool(GEMINI_API_KEY or ANTHROPIC_API_KEY)


def _parse_json(content):
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise AIUnavailable("AI 回傳的內容無法讀取，請再試一次。") from error
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as inner:
            raise AIUnavailable("AI 回傳的內容無法讀取，請再試一次。") from inner
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        payload = payload[0]  # 有時模型會把物件包在陣列裡
    if not isinstance(payload, dict):
        raise AIUnavailable("AI 回傳的格式不正確，請再試一次。")
    return payload


def _call_gemini(prompt, image_bytes, image_mime, timeout):
    parts = [{"text": prompt}]
    if image_bytes:
        parts.insert(0, {"inline_data": {"mime_type": image_mime, "data": base64.b64encode(image_bytes).decode("ascii")}})
    response = None
    for attempt in range(2):
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json={"contents": [{"role": "user", "parts": parts}],
                      "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8192}},
                timeout=timeout,
            )
        except requests.Timeout as error:
            raise AIUnavailable("AI 回應逾時，請稍後再試。") from error
        except requests.ConnectionError as error:
            raise AIUnavailable("目前無法連線 AI 服務，請檢查網路後重試。") from error
        if response.status_code == 503 and attempt == 0:
            time.sleep(2)
            continue
        break
    if response.status_code == 429:
        raise AIUnavailable("AI 使用額度已達上限，請稍後再試。")
    if response.status_code >= 400:
        raise AIUnavailable(f"AI 服務回傳錯誤（HTTP {response.status_code}），請稍後再試。")
    candidates = response.json().get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    return "".join(part.get("text", "") for part in parts)


def _call_claude(prompt, image_bytes, image_mime, timeout):
    try:
        import anthropic
    except ImportError as error:
        raise AIUnavailable("伺服器尚未安裝 anthropic 套件，請執行 pip install anthropic。") from error
    content = [{"type": "text", "text": prompt}]
    if image_bytes:
        content.insert(0, {"type": "image", "source": {
            "type": "base64", "media_type": image_mime, "data": base64.standard_b64encode(image_bytes).decode("ascii")}})
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=timeout)
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=16000,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.RateLimitError as error:
        raise AIUnavailable("AI 使用額度已達上限，請稍後再試。") from error
    except anthropic.APIStatusError as error:
        raise AIUnavailable(f"AI 服務回傳錯誤（HTTP {error.status_code}），請稍後再試。") from error
    except anthropic.APIConnectionError as error:
        raise AIUnavailable("目前無法連線 AI 服務，請檢查網路後重試。") from error
    if message.stop_reason == "refusal":
        raise AIUnavailable("AI 無法處理這個內容，請改用手動輸入。")
    return "".join(block.text for block in message.content if block.type == "text")


def ask_json(prompt, image_bytes=None, image_mime="image/jpeg", timeout=40):
    """送出提示並回傳 dict。失敗時丟出 AIUnavailable。"""
    if GEMINI_API_KEY:
        content = _call_gemini(prompt, image_bytes, image_mime, timeout)
    elif ANTHROPIC_API_KEY:
        content = _call_claude(prompt, image_bytes, image_mime, timeout)
    else:
        raise AIUnavailable("伺服器尚未設定 AI 服務金鑰（GEMINI_API_KEY 或 ANTHROPIC_API_KEY）。")
    return _parse_json(content)
