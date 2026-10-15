from flask import Blueprint, abort, request  # 匯入 Flask 藍圖、中止請求、取得請求內容

import line_messaging  # 匯入 LINE 官方帳號共用工具
import line_commands

line_webhook_bp = Blueprint("line_webhook", __name__)  # 建立 LINE 官方帳號 webhook 藍圖

UNLINKED_HINT = (
    "歡迎加入 Travel Together！\n"
    "請到網站個人資料頁按「綁定 LINE」，或使用「LINE 登入」，接收行程通知。"
)


# Webhook URL 請填：https://你的公開網址/line/webhook（本機開發可用 ngrok 產生 HTTPS 網址）
@line_webhook_bp.route("/line/webhook", methods=["POST"])
def webhook():
    body = request.get_data()  # 簽章是對原始內容計算的，必須用未經解析的位元組
    if not line_messaging.verify_signature(body, request.headers.get("X-Line-Signature", "")):
        abort(400)

    payload = request.get_json(silent=True) or {}
    for event in payload.get("events", []):  # LINE Console 按 Verify 時 events 會是空陣列
        try:
            handle_event(event)
        except Exception as error:  # 單一事件失敗不影響其他事件，也避免 LINE 一直重送
            print("處理 LINE 事件失敗：", error)
    return "OK"


def handle_event(event):
    source = event.get("source", {})
    line_sub = source.get("userId")
    if source.get("type") != "user" or not line_sub:  # 只處理一對一聊天，群組事件略過
        return

    event_type = event.get("type")
    if event_type == "follow":  # 加好友或解除封鎖
        linked = line_messaging.set_friend_status(line_sub, True)
        if not linked and event.get("replyToken"):
            line_messaging.reply_text(event["replyToken"], UNLINKED_HINT)
    elif event_type == "unfollow":  # 封鎖官方帳號（此事件沒有 replyToken）
        line_messaging.set_friend_status(line_sub, False)
    elif event_type == "message" and event.get("message", {}).get("type") == "text":
        reply = line_commands.reply_for(line_sub, event["message"].get("text"))
        if reply and event.get("replyToken"):
            line_messaging.reply_text(event["replyToken"], reply, quick_replies=line_commands.COMMANDS)

