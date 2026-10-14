"""LINE 官方帳號（Messaging API）共用工具：驗證 webhook 簽章、回覆與推播訊息。

注意：push / multicast 會計入官方帳號每月的免費訊息額度（依收訊人數計算），
reply（回覆使用者傳來的訊息）則不計費，能用 reply 的地方盡量用 reply。
"""
import base64  # 匯入 base64，用來編碼簽章
import hashlib  # 匯入 hashlib，提供 SHA256 演算法
import hmac  # 匯入 hmac，用來計算與比對 webhook 簽章

import requests  # 匯入 requests，用來呼叫 LINE Messaging API
from mysql.connector import Error  # 匯入 MySQL 錯誤類別

from config import LINE_BOT_ACCESS_TOKEN, LINE_BOT_BASIC_ID, LINE_BOT_CHANNEL_SECRET  # 匯入官方帳號設定
from db import get_db_connection  # 匯入資料庫連線函式

API_BASE = "https://api.line.me/v2/bot"
MULTICAST_LIMIT = 500  # LINE 規定 multicast 一次最多 500 位收訊者


def is_configured():  # 檢查官方帳號金鑰是否已設定
    return bool(LINE_BOT_ACCESS_TOKEN and LINE_BOT_CHANNEL_SECRET)


def add_friend_url():  # 加好友連結：手機點開會直接打開 LINE 的加好友畫面
    return f"https://line.me/R/ti/p/{LINE_BOT_BASIC_ID}" if LINE_BOT_BASIC_ID else ""


def qr_code_url():  # LINE 官方提供的加好友 QR Code 圖片（給用電腦瀏覽的人用手機掃）
    return f"https://qr-official.line.me/sid/L/{LINE_BOT_BASIC_ID.lstrip('@')}.png" if LINE_BOT_BASIC_ID else ""


def verify_signature(body, signature):  # 驗證 webhook 請求確實來自 LINE（body 為原始位元組）
    if not LINE_BOT_CHANNEL_SECRET or not signature:
        return False
    digest = hmac.new(LINE_BOT_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode("utf-8"), signature)


def _post(path, payload):  # 呼叫 Messaging API，成功回傳 True
    if not is_configured():
        print("LINE 官方帳號尚未設定，略過發送訊息")
        return False
    try:
        response = requests.post(
            API_BASE + path,
            json=payload,
            headers={"Authorization": "Bearer " + LINE_BOT_ACCESS_TOKEN},
            timeout=10,
        )
    except requests.RequestException as error:
        print("LINE 訊息發送失敗：", error)
        return False
    if response.status_code != 200:
        print("LINE 訊息發送失敗：", response.status_code, response.text)
        return False
    return True


def _text_messages(text):  # 把文字包成 LINE 訊息物件（單則上限 5000 字）
    return [{"type": "text", "text": text[:5000]}]


def reply_text(reply_token, text, quick_replies=None):  # 回覆使用者的訊息（不計費，replyToken 只能用一次且有時效）
    messages = _text_messages(text)
    if quick_replies:
        messages[0]["quickReply"] = {"items": [
            {"type": "action", "action": {"type": "message", "label": label[:20], "text": label}}
            for label in quick_replies[:13]
        ]}
    return _post("/message/reply", {"replyToken": reply_token, "messages": messages})


def _line_targets(user_ids):  # 依網站 user_id 查出已加好友的 LINE userId
    if not user_ids:
        return []
    connection = get_db_connection()
    if connection is None:
        return []
    cursor = connection.cursor()
    try:
        placeholders = ", ".join(["%s"] * len(user_ids))
        cursor.execute(
            f"""
            SELECT line_sub FROM users
            WHERE user_id IN ({placeholders})
              AND line_sub IS NOT NULL AND line_friend = 1 AND status = 'active'
            """,
            tuple(user_ids),
        )
        return [row[0] for row in cursor.fetchall()]
    except Error as error:
        print("查詢 LINE 推播對象失敗：", error)
        return []
    finally:
        cursor.close()
        connection.close()


def push_to_users(user_ids, text):  # 推播文字給多位網站會員，回傳實際送出的人數
    """沒有綁定 LINE 或沒加官方帳號好友的會員會自動略過。會計入每月訊息額度。"""
    targets = _line_targets(list(dict.fromkeys(user_ids)))
    sent = 0
    for start in range(0, len(targets), MULTICAST_LIMIT):
        chunk = targets[start:start + MULTICAST_LIMIT]
        if len(chunk) == 1:
            ok = _post("/message/push", {"to": chunk[0], "messages": _text_messages(text)})
        else:
            ok = _post("/message/multicast", {"to": chunk, "messages": _text_messages(text)})
        if ok:
            sent += len(chunk)
    return sent


def push_to_user(user_id, text):  # 推播文字給單一網站會員，成功回傳 True
    return push_to_users([user_id], text) == 1


def set_friend_status(line_sub, is_friend):  # 更新會員是否為官方帳號好友，回傳是否有對應的會員
    connection = get_db_connection()
    if connection is None:
        return False
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE users SET line_friend = %s WHERE line_sub = %s",
            (1 if is_friend else 0, line_sub),
        )
        connection.commit()
        cursor.execute("SELECT 1 FROM users WHERE line_sub = %s LIMIT 1", (line_sub,))
        return cursor.fetchone() is not None
    except Error as error:
        connection.rollback()
        print("更新 LINE 好友狀態失敗：", error)
        return False
    finally:
        cursor.close()
        connection.close()

