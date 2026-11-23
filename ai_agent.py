"""共用的 AI Agent 工具迴圈：讓 AI 自己決定要呼叫哪些工具、呼叫幾次，最後回傳一個 JSON 物件。

跟 ai_client.ask_json 的差別：ask_json 只問一次；這裡 AI 可以先「查資料」(呼叫工具)再回答，
適合要看情況決定步驟的工作(例如提案預審：查不到地點就換關鍵字再查)。

- 優先用 Google Gemini 的函式呼叫(GEMINI_API_KEY)，沒設定時改用 Anthropic Claude 的 tool use(ANTHROPIC_API_KEY)。
- 工具一律由呼叫端提供，Agent 只能用這些工具；每一輪最多呼叫的次數由 max_turns 限制，避免費用失控。
- 任何失敗都轉成 ai_client.AIUnavailable，呼叫端可以退回不靠 AI 的規則結果。
"""

import json
import time
from dataclasses import dataclass
from typing import Callable

import requests

from ai_client import CLAUDE_MODEL, GEMINI_MODEL, AIUnavailable, _parse_json
from config import ANTHROPIC_API_KEY, GEMINI_API_KEY


@dataclass
class Tool:
    """一個給 AI 用的工具。handler 收到 AI 給的參數(dict)，回傳要交還給 AI 的結果(dict)。"""
    name: str
    description: str
    parameters: dict  # JSON Schema，例如 {"type": "object", "properties": {...}, "required": [...]}
    handler: Callable[[dict], dict]


def agent_ready():
    return bool(GEMINI_API_KEY or ANTHROPIC_API_KEY)


def model_name():
    return GEMINI_MODEL if GEMINI_API_KEY else CLAUDE_MODEL


def _run_tool(tools_by_name, name, args, trace):
    tool = tools_by_name.get(name)
    if tool is None:
        result = {"error": f"沒有這個工具：{name}"}
    else:
        try:
            result = tool.handler(args if isinstance(args, dict) else {})
        except Exception as error:  # 工具失敗不讓整個 Agent 中斷，把錯誤交給 AI 自己判斷
            result = {"error": f"工具執行失敗：{error}"}
    # 資料庫的 Decimal、日期這類型別不能直接轉成 JSON 送給 AI，一律先轉成字串／數字
    result = json.loads(json.dumps(result, ensure_ascii=False, default=lambda v: float(v) if hasattr(v, "is_finite") else str(v)))
    trace.append({"tool": name, "args": args, "result": result})
    return result


def _raise_for_status(response):
    if response.status_code == 429:
        raise AIUnavailable("AI 使用額度已達上限，請稍後再試。")
    if response.status_code >= 400:
        raise AIUnavailable(f"AI 服務回傳錯誤（HTTP {response.status_code}），請稍後再試。")


def _post(url, headers, body, timeout):
    response = None
    for attempt in range(2):  # 503(暫時忙碌)重試一次
        try:
            response = requests.post(url, headers=headers, json=body, timeout=timeout)
        except requests.Timeout as error:
            raise AIUnavailable("AI 回應逾時，請稍後再試。") from error
        except requests.ConnectionError as error:
            raise AIUnavailable("目前無法連線 AI 服務，請檢查網路後重試。") from error
        if response.status_code == 503 and attempt == 0:
            time.sleep(2)
            continue
        break
    _raise_for_status(response)
    return response.json()


# ---------- Gemini 函式呼叫 ----------

def _gemini_loop(system, user_text, tools, max_turns, timeout, trace):
    tools_by_name = {tool.name: tool for tool in tools}
    declarations = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools]
    contents = [{"role": "user", "parts": [{"text": user_text}]}]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}

    for turn in range(max_turns + 1):
        last_turn = turn == max_turns
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": declarations}],
            # 最後一輪不准再呼叫工具，逼 AI 用目前查到的資料回答
            "toolConfig": {"functionCallingConfig": {"mode": "NONE" if last_turn else "AUTO"}},
            "generationConfig": {"maxOutputTokens": 4096},
        }
        data = _post(url, headers, body, timeout)
        candidates = data.get("candidates") or []
        content = (candidates[0].get("content") if candidates else None) or {}
        parts = content.get("parts") or []
        calls = [part["functionCall"] for part in parts if "functionCall" in part]
        if not calls:
            return "".join(part.get("text", "") for part in parts if not part.get("thought"))
        contents.append({"role": "model", "parts": parts})  # 原樣交回(含 thoughtSignature)，Gemini 3 需要
        responses = []
        for call in calls:
            result = _run_tool(tools_by_name, call.get("name"), call.get("args") or {}, trace)
            response_part = {"name": call.get("name"), "response": {"result": result}}
            if call.get("id"):
                response_part["id"] = call["id"]
            responses.append({"functionResponse": response_part})
        contents.append({"role": "user", "parts": responses})
    return ""


# ---------- Claude tool use ----------

def _claude_loop(system, user_text, tools, max_turns, timeout, trace):
    tools_by_name = {tool.name: tool for tool in tools}
    declarations = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
    messages = [{"role": "user", "content": user_text}]
    headers = {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}

    for turn in range(max_turns + 1):
        last_turn = turn == max_turns
        body = {"model": CLAUDE_MODEL, "max_tokens": 2048, "system": system, "tools": declarations, "messages": messages}
        if last_turn:
            body["tool_choice"] = {"type": "none"}
        data = _post("https://api.anthropic.com/v1/messages", headers, body, timeout)
        if data.get("stop_reason") == "refusal":
            raise AIUnavailable("AI 無法處理這個內容。")
        blocks = data.get("content") or []
        calls = [block for block in blocks if block.get("type") == "tool_use"]
        if data.get("stop_reason") != "tool_use" or not calls:
            return "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        messages.append({"role": "assistant", "content": blocks})
        results = []
        for call in calls:
            result = _run_tool(tools_by_name, call.get("name"), call.get("input") or {}, trace)
            results.append({"type": "tool_result", "tool_use_id": call["id"],
                            "content": json.dumps(result, ensure_ascii=False, default=str)})
        messages.append({"role": "user", "content": results})
    return ""


def run_agent(system, user_text, tools, max_turns=5, timeout=40):
    """執行 Agent，回傳 (AI 最後回答的 dict, 工具呼叫紀錄 list)。失敗丟出 AIUnavailable。

    system：角色與規則；user_text：這次的任務；tools：Tool 清單；max_turns：最多呼叫工具幾輪。
    """
    trace = []
    if GEMINI_API_KEY:
        text = _gemini_loop(system, user_text, tools, max_turns, timeout, trace)
    elif ANTHROPIC_API_KEY:
        text = _claude_loop(system, user_text, tools, max_turns, timeout, trace)
    else:
        raise AIUnavailable("伺服器尚未設定 AI 服務金鑰（GEMINI_API_KEY 或 ANTHROPIC_API_KEY）。")
    return _parse_json(text), trace
