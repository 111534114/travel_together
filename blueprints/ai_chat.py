from flask import Blueprint, flash, redirect, render_template, request, session, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from ai_assistant import ClaudeApiError, call_claude, is_configured  # 匯入 Claude API 相關函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式
from utils import get_or_create_city, get_or_create_country  # 匯入國家/城市的取得(或新增)函式

ai_chat_bp = Blueprint("ai_chat", __name__, url_prefix="/content-admin/ai-assistant")  # 建立 AI 助理藍圖，網址前綴 /content-admin/ai-assistant

MAX_TOOL_ITERATIONS = 6  # 定義單次對話最多允許幾輪「呼叫工具→回傳結果」循環，避免無限迴圈
MAX_HISTORY_ENTRIES = 20  # 定義對話紀錄最多保留幾筆(一問一答算兩筆)，避免 session 越存越大
CONTEXT_TURNS = 10  # 定義要把最近幾筆對話紀錄當作上下文一起送給 Claude，讓它有短期記憶


def _execute_tool(cursor, name, tool_input):  # 定義內部函式：實際執行 Claude 要求的工具動作，回傳文字結果給 Claude 參考
    if name == "add_country":  # 如果 Claude 要新增國家
        country_name = (tool_input.get("name") or "").strip()  # 取得國家名稱並去除空白

        if not country_name:  # 如果名稱是空的
            return "缺少國家名稱，無法新增"  # 回傳錯誤說明

        cursor.execute("SELECT country_id FROM countries WHERE name = %s", (country_name,))  # 查詢是否已存在
        already_existed = cursor.fetchone() is not None  # 記錄新增前是否已經存在

        country_id = get_or_create_country(cursor, country_name)  # 取得(或新增)這個國家

        if already_existed:  # 如果原本就存在
            return f"國家「{country_name}」已經存在，沒有重複新增(ID: {country_id})"  # 回傳說明

        log_action(cursor, "create_country", "country", country_id, f"(AI助理)新增國家：{country_name}")  # 寫入操作紀錄
        return f"已新增國家「{country_name}」(ID: {country_id})"  # 回傳成功說明

    if name == "add_city":  # 如果 Claude 要新增城市
        country_name = (tool_input.get("country_name") or "").strip()  # 取得所屬國家名稱
        city_name = (tool_input.get("city_name") or "").strip()  # 取得城市名稱

        if not country_name or not city_name:  # 如果國家或城市名稱缺少任一項
            return "缺少國家名稱或城市名稱，無法新增"  # 回傳錯誤說明

        country_id = get_or_create_country(cursor, country_name)  # 取得(或新增)所屬國家

        cursor.execute(  # 查詢這個城市是否已經存在
            "SELECT city_id FROM cities WHERE country_id = %s AND name = %s",
            (country_id, city_name)
        )
        already_existed = cursor.fetchone() is not None  # 記錄新增前是否已經存在

        city_id = get_or_create_city(cursor, country_id, city_name)  # 取得(或新增)這個城市

        if already_existed:  # 如果原本就存在
            return f"城市「{city_name}」（屬於{country_name}）已經存在，沒有重複新增(ID: {city_id})"  # 回傳說明

        log_action(  # 寫入操作紀錄
            cursor, "create_city", "city", city_id,
            f"(AI助理)新增城市：{city_name}（屬於{country_name}）"
        )
        return f"已新增城市「{city_name}」，屬於「{country_name}」(ID: {city_id})"  # 回傳成功說明

    if name == "list_countries_and_cities":  # 如果 Claude 要查詢目前的國家與城市清單
        cursor.execute("""
            SELECT co.name, ci.name
            FROM countries co
            LEFT JOIN cities ci ON ci.country_id = co.country_id
            ORDER BY co.name, ci.name
        """)  # 查詢所有國家，並關聯出底下的城市(沒有城市的國家也要列出)
        rows = cursor.fetchall()  # 取得查詢結果(每筆是 (國家名稱, 城市名稱或 None) 的 tuple)

        grouped = {}  # 建立一個字典，把城市依國家分組
        for country_name, city_name in rows:  # 逐筆整理
            grouped.setdefault(country_name, [])  # 確保這個國家有一個對應的城市清單
            if city_name:  # 如果這筆有城市名稱(不是沒有城市的國家)
                grouped[country_name].append(city_name)  # 加進這個國家的城市清單

        if not grouped:  # 如果資料庫裡完全沒有國家
            return "目前資料庫裡還沒有任何國家"  # 回傳說明

        lines = []  # 建立要回傳給 Claude 的文字清單
        for country_name, cities in grouped.items():  # 逐一國家組成一行文字
            city_text = "、".join(cities) if cities else "(尚無城市)"  # 城市名稱用頓號連接，沒有城市就標註
            lines.append(f"{country_name}：{city_text}")  # 加入這一行

        return "\n".join(lines)  # 把所有國家的資訊合併成多行文字回傳

    return f"不支援的操作：{name}"  # 如果是未知的工具名稱(理論上不會發生)，回傳說明


@ai_chat_bp.route("/")  # 設定 AI 助理對話頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def chat_page():  # 定義 AI 助理對話頁函式
    history = session.get("ai_chat_history", [])  # 取得目前 session 裡儲存的對話紀錄(沒有就是空清單)
    return render_template(  # 渲染對話頁面
        "content_admin/ai_assistant.html",
        history=history,  # 對話紀錄
        api_configured=is_configured()  # 是否已設定 API 金鑰
    )


@ai_chat_bp.route("/send", methods=["POST"])  # 設定送出訊息的路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def send_message():  # 定義送出訊息並取得 AI 回應函式
    if not is_configured():  # 如果還沒設定 Claude API 金鑰
        flash("尚未設定 Claude API 金鑰，請先在專案的 .env 檔案設定 ANTHROPIC_API_KEY", "error")  # 顯示錯誤提示
        return redirect(url_for("ai_chat.chat_page"))  # 導回對話頁面

    user_text = request.form.get("message", "").strip()  # 取得使用者輸入的訊息

    if not user_text:  # 如果訊息是空的
        flash("請輸入訊息", "error")  # 顯示錯誤提示
        return redirect(url_for("ai_chat.chat_page"))  # 導回對話頁面

    history = session.get("ai_chat_history", [])  # 取得目前的對話紀錄

    api_messages = []  # 建立要送給 Claude 的對話內容(純文字版本，重建短期記憶用)
    for entry in history[-CONTEXT_TURNS:]:  # 只取最近幾筆當作上下文，避免請求過大
        api_messages.append({"role": entry["role"], "content": entry["text"]})  # 加入這一筆(純文字，不含工具呼叫細節)
    api_messages.append({"role": "user", "content": user_text})  # 加入這次使用者剛輸入的新訊息

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("ai_chat.chat_page"))  # 導回對話頁面

    cursor = connection.cursor()  # 建立一般游標(方便搭配 get_or_create 系列函式)

    try:  # 開始跟 Claude 來回對話，直到它給出最終文字回覆
        final_text_parts = []  # 建立收集 Claude 文字回覆片段的清單

        for _ in range(MAX_TOOL_ITERATIONS):  # 最多循環這麼多次，避免工具呼叫無限迴圈
            data = call_claude(api_messages)  # 呼叫 Claude API，取得這一輪的回應
            content_blocks = data.get("content", [])  # 取得回應內容區塊清單(可能包含文字、工具呼叫)
            api_messages.append({"role": "assistant", "content": content_blocks})  # 把這輪回應加入對話內容，維持上下文完整

            text_blocks = [block["text"] for block in content_blocks if block.get("type") == "text"]  # 取出所有文字區塊
            final_text_parts.extend(text_blocks)  # 加進收集清單

            tool_use_blocks = [block for block in content_blocks if block.get("type") == "tool_use"]  # 取出所有工具呼叫區塊

            if not tool_use_blocks:  # 如果這一輪沒有要求呼叫任何工具(代表對話結束)
                break  # 跳出循環

            tool_results = []  # 建立這一輪所有工具執行結果的清單
            for block in tool_use_blocks:  # 逐一執行 Claude 要求的每個工具
                result_text = _execute_tool(cursor, block["name"], block.get("input", {}))  # 實際執行工具動作
                tool_results.append({  # 組成回傳給 Claude 的工具結果格式
                    "type": "tool_result",
                    "tool_use_id": block["id"],  # 對應是回應哪一次工具呼叫
                    "content": result_text,  # 執行結果的文字說明
                })

            api_messages.append({"role": "user", "content": tool_results})  # 把工具執行結果送回給 Claude，讓它接著回應

            if data.get("stop_reason") != "tool_use":  # 如果這輪停止原因不是「還要呼叫工具」
                break  # 跳出循環(理論上執行到這裡通常代表已經結束)

        connection.commit()  # 提交交易，正式寫入這次對話中所有工具動作造成的資料庫變更

        reply_text = "\n".join(part for part in final_text_parts if part).strip() or "已完成。"  # 組成最終要顯示給使用者的回覆文字

        history.append({"role": "user", "text": user_text})  # 把使用者這次的訊息加入對話紀錄
        history.append({"role": "assistant", "text": reply_text})  # 把 AI 的回覆加入對話紀錄
        session["ai_chat_history"] = history[-MAX_HISTORY_ENTRIES:]  # 只保留最近的紀錄，避免 session 越存越大

    except ClaudeApiError as error:  # 如果呼叫 Claude API 時發生錯誤(例如金鑰無效、額度用完)
        connection.rollback()  # 回復交易
        flash(f"AI 回應失敗：{error}", "error")  # 顯示錯誤提示
    except Exception as error:  # 如果處理過程發生其他例外
        connection.rollback()  # 回復交易
        print("AI 助理處理失敗：", error)  # 在伺服器端印出錯誤內容
        flash("AI 助理處理失敗，請稍後再試", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("ai_chat.chat_page"))  # 導回對話頁面


@ai_chat_bp.route("/clear", methods=["POST"])  # 設定清除對話紀錄的路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def clear_chat():  # 定義清除對話紀錄函式
    session.pop("ai_chat_history", None)  # 從 session 裡移除對話紀錄(沒有的話就不做任何事)
    return redirect(url_for("ai_chat.chat_page"))  # 導回對話頁面
