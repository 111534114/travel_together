import base64
import hashlib
import hmac
import json
import unittest
from datetime import date
from unittest.mock import patch

from app import app
from blueprints.line_bot import build_public_trips_message, verify_line_signature


SAMPLE_TRIP = {
    "trip_id": 7,
    "trip_name": "台北三天兩夜",
    "country": "台灣",
    "city": "台北市",
    "start_date": date(2026, 10, 1),
    "end_date": date(2026, 10, 3),
    "days_count": 3,
    "total_budget": 15000,
    "currency": "TWD",
    "introduction": "台北美食與近郊旅行",
    "cover_image_path": "images/logo.png",
    "owner_nickname": "旅遊小幫手",
    "owner_name": "測試會員",
}


class LineBotTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_signature_verification(self):
        body = b'{"events":[]}'
        secret = "test-secret"
        signature = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()
        self.assertTrue(verify_line_signature(body, signature, secret))
        self.assertFalse(verify_line_signature(body, "wrong", secret))

    def test_public_trip_flex_message(self):
        message = build_public_trips_message([SAMPLE_TRIP], "https://example.com")
        self.assertEqual(message["type"], "flex")
        bubble = message["contents"]["contents"][0]
        self.assertEqual(bubble["type"], "bubble")
        self.assertIn("台北三天兩夜", json.dumps(message, ensure_ascii=False))
        self.assertEqual(
            bubble["footer"]["contents"][0]["action"]["uri"],
            "https://example.com/visitor?trip=7#public-trips",
        )

    def test_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            "/line/webhook",
            data=b'{"events":[]}',
            headers={"X-Line-Signature": "invalid", "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)

    def test_public_trip_message_event_replies_with_flex(self):
        payload = {
            "events": [
                {
                    "type": "message",
                    "replyToken": "reply-token",
                    "message": {"type": "text", "text": "公開行程"},
                }
            ]
        }
        raw = json.dumps(payload).encode()
        secret = "test-secret"
        signature = base64.b64encode(
            hmac.new(secret.encode(), raw, hashlib.sha256).digest()
        ).decode()
        with patch("blueprints.line_bot.LINE_CHANNEL_SECRET", secret), patch(
            "blueprints.line_bot.fetch_public_trips", return_value=[SAMPLE_TRIP]
        ), patch("blueprints.line_bot.reply_to_line", return_value=True) as reply:
            response = self.client.post(
                "/line/webhook",
                data=raw,
                headers={"X-Line-Signature": signature, "Content-Type": "application/json"},
            )
        self.assertEqual(response.status_code, 200)
        sent_message = reply.call_args.args[1][0]
        self.assertEqual(sent_message["type"], "flex")


if __name__ == "__main__":
    unittest.main()
