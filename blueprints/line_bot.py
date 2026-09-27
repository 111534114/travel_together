import base64
import hashlib
import hmac
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import parse_qs

import requests
from flask import Blueprint, current_app, jsonify, request

from config import (
    APP_BASE_URL,
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_CHANNEL_SECRET,
    LINE_DEFAULT_COVER_URL,
)
from db import get_db_connection


line_bot_bp = Blueprint("line_bot", __name__, url_prefix="/line")
LINE_REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
MAX_TRIPS_PER_MESSAGE = 10


def verify_line_signature(body, signature, channel_secret=None):
    """驗證請求確實由 LINE Platform 傳送。"""
    secret = channel_secret if channel_secret is not None else LINE_CHANNEL_SECRET
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)


def _format_date(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y/%m/%d")
    return str(value or "未提供")


def _format_budget(currency, value):
    if value is None:
        return "未提供預算"
    try:
        amount = Decimal(str(value))
        return f"{currency or 'TWD'} {amount:,.0f}"
    except Exception:
        return f"{currency or 'TWD'} {value}"


def _safe_text(value, limit):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _base_url():
    return APP_BASE_URL or request.url_root.rstrip("/")


def _cover_url(trip, base_url):
    path = (trip.get("cover_image_path") or "").strip()
    if path.startswith(("https://", "http://")):
        return path
    if path:
        return f"{base_url}/static/{path.lstrip('/')}"
    if LINE_DEFAULT_COVER_URL:
        return LINE_DEFAULT_COVER_URL
    return f"{base_url}/static/images/logo.png"


def fetch_public_trips(keyword="", limit=MAX_TRIPS_PER_MESSAGE, offset=0):
    """讀取仍可公開顯示的行程；私人、取消與停用會員內容不會出現。"""
    connection = get_db_connection()
    if connection is None:
        raise RuntimeError("資料庫連線失敗")
    cursor = connection.cursor(dictionary=True)
    try:
        conditions = [
            "t.visibility = 'public'",
            "t.status != 'cancelled'",
            "u.status = 'active'",
        ]
        params = []
        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                "(t.trip_name LIKE %s OR co.name LIKE %s OR ci.name LIKE %s "
                "OR c.category_name LIKE %s OR u.nickname LIKE %s)"
            )
            params.extend([like, like, like, like, like])
        params.extend([int(limit), int(offset)])
        cursor.execute(
            f"""
            SELECT t.trip_id, t.trip_name, t.start_date, t.end_date,
                   t.total_budget, t.currency, t.introduction,
                   t.cover_image_path, co.name AS country, ci.name AS city,
                   c.category_name, u.nickname AS owner_nickname,
                   u.full_name AS owner_name,
                   DATEDIFF(t.end_date, t.start_date) + 1 AS days_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            LEFT JOIN categories c ON c.category_id = t.category_id
            WHERE {' AND '.join(conditions)}
            ORDER BY t.created_at DESC, t.trip_id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def build_public_trips_message(trips, base_url):
    """把公開行程轉換為 LINE Flex Message Carousel。"""
    bubbles = []
    for trip in list(trips)[:MAX_TRIPS_PER_MESSAGE]:
        title = _safe_text(trip.get("trip_name"), 40) or "未命名行程"
        destination = " · ".join(
            value for value in (trip.get("country"), trip.get("city")) if value
        ) or "未提供目的地"
        owner = trip.get("owner_nickname") or trip.get("owner_name") or "會員"
        detail_url = f"{base_url}/visitor?trip={trip['trip_id']}#public-trips"
        share_url = f"https://line.me/R/share?text={requests.utils.quote(title + ' ' + detail_url)}"
        body = [
            {"type": "text", "text": title, "weight": "bold", "size": "xl", "wrap": True},
            {"type": "text", "text": destination, "size": "sm", "color": "#6B6280", "wrap": True},
            {
                "type": "box",
                "layout": "vertical",
                "margin": "lg",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": f"日期  {_format_date(trip.get('start_date'))} ～ {_format_date(trip.get('end_date'))}", "size": "sm", "wrap": True},
                    {"type": "text", "text": f"天數  {trip.get('days_count') or '-'} 天", "size": "sm"},
                    {"type": "text", "text": f"預算  {_format_budget(trip.get('currency'), trip.get('total_budget'))}", "size": "sm", "wrap": True},
                    {"type": "text", "text": f"建立者  {_safe_text(owner, 30)}", "size": "sm", "wrap": True},
                ],
            },
        ]
        introduction = _safe_text(trip.get("introduction"), 90)
        if introduction:
            body.append({"type": "text", "text": introduction, "size": "sm", "color": "#777084", "margin": "lg", "wrap": True})
        bubbles.append(
            {
                "type": "bubble",
                "hero": {
                    "type": "image",
                    "url": _cover_url(trip, base_url),
                    "size": "full",
                    "aspectRatio": "20:13",
                    "aspectMode": "cover",
                },
                "body": {"type": "box", "layout": "vertical", "contents": body},
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "color": "#654B91", "action": {"type": "uri", "label": "查看詳情", "uri": detail_url}},
                        {"type": "button", "action": {"type": "uri", "label": "分享行程", "uri": share_url}},
                    ],
                },
            }
        )
    return {
        "type": "flex",
        "altText": f"找到 {len(bubbles)} 筆公開行程",
        "contents": {"type": "carousel", "contents": bubbles},
    }


def _empty_message(keyword=""):
    target = f"與「{keyword}」相關的" if keyword else "可瀏覽的"
    return {"type": "text", "text": f"目前找不到{target}公開行程，請稍後再試。"}


def _welcome_message():
    return {
        "type": "text",
        "text": "歡迎加入走吧揪團！你可以查看公開行程，或輸入「搜尋 台北」尋找目的地。",
        "quickReply": {
            "items": [
                {"type": "action", "action": {"type": "message", "label": "公開行程", "text": "公開行程"}},
                {"type": "action", "action": {"type": "message", "label": "搜尋台北", "text": "搜尋 台北"}},
            ]
        },
    }


def reply_to_line(reply_token, messages):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        current_app.logger.warning("尚未設定 LINE_CHANNEL_ACCESS_TOKEN，略過 LINE 回覆")
        return False
    response = requests.post(
        LINE_REPLY_ENDPOINT,
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"replyToken": reply_token, "messages": messages},
        timeout=10,
    )
    response.raise_for_status()
    return True


def _public_trip_reply(keyword=""):
    trips = fetch_public_trips(keyword=keyword)
    return build_public_trips_message(trips, _base_url()) if trips else _empty_message(keyword)


@line_bot_bp.post("/webhook")
def webhook():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")
    if not verify_line_signature(body, signature):
        return jsonify({"error": "invalid signature"}), 400

    payload = request.get_json(silent=True) or {}
    for event in payload.get("events", []):
        reply_token = event.get("replyToken")
        if not reply_token:
            continue
        try:
            event_type = event.get("type")
            if event_type == "follow":
                message = _welcome_message()
            elif event_type == "postback":
                data = parse_qs(event.get("postback", {}).get("data", ""))
                action = (data.get("action") or [""])[0]
                message = _public_trip_reply() if action == "public_trips" else _welcome_message()
            elif event_type == "message" and event.get("message", {}).get("type") == "text":
                text = event["message"].get("text", "").strip()
                if text == "公開行程":
                    message = _public_trip_reply()
                elif text.startswith("搜尋 "):
                    message = _public_trip_reply(text[3:].strip())
                else:
                    message = _welcome_message()
            else:
                continue
            reply_to_line(reply_token, [message])
        except Exception:
            current_app.logger.exception("處理 LINE Webhook 事件失敗")
    return jsonify({"ok": True})


@line_bot_bp.get("/public-trips/preview")
def public_trips_preview():
    """本機開發預覽：查看將送給 LINE 的 Flex Message JSON。"""
    keyword = request.args.get("keyword", "").strip()
    try:
        trips = fetch_public_trips(keyword=keyword)
    except Exception as error:
        return jsonify({"error": str(error)}), 503
    message = build_public_trips_message(trips, _base_url()) if trips else _empty_message(keyword)
    return jsonify(message)


@line_bot_bp.get("/status")
def status():
    return jsonify(
        {
            "channel_secret_configured": bool(LINE_CHANNEL_SECRET),
            "access_token_configured": bool(LINE_CHANNEL_ACCESS_TOKEN),
            "app_base_url": APP_BASE_URL or request.url_root.rstrip("/"),
            "webhook_url": f"{_base_url()}/line/webhook",
            "preview_url": f"{request.url_root.rstrip('/')}/line/public-trips/preview",
        }
    )
