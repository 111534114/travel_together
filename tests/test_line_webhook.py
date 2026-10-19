import base64
import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

from app import app
from line_commands import NEXT_TRIP, normalize


def signature(secret, body):
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


class LineWebhookTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_invalid_signature_is_rejected(self):
        with patch("line_messaging.LINE_BOT_CHANNEL_SECRET", "test-secret"):
            response = self.client.post(
                "/line/webhook",
                data=b"{}",
                content_type="application/json",
                headers={"X-Line-Signature": "invalid"},
            )
        self.assertEqual(response.status_code, 400)

    def test_follow_event_updates_friend_status_and_replies_when_unlinked(self):
        secret = "test-secret"
        payload = {
            "events": [{
                "type": "follow",
                "replyToken": "reply-token",
                "source": {"type": "user", "userId": "U123"},
            }]
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        with patch("line_messaging.LINE_BOT_CHANNEL_SECRET", secret), \
             patch("blueprints.line_webhook.line_messaging.set_friend_status", return_value=False) as set_status, \
             patch("blueprints.line_webhook.line_messaging.reply_text") as reply:
            response = self.client.post(
                "/line/webhook",
                data=body,
                content_type="application/json",
                headers={"X-Line-Signature": signature(secret, body)},
            )

        self.assertEqual(response.status_code, 200)
        set_status.assert_called_once_with("U123", True)
        reply.assert_called_once()

    def test_unknown_message_replies_with_help(self):
        secret = "test-secret"
        payload = {"events": [{
            "type": "message",
            "replyToken": "reply-token",
            "source": {"type": "user", "userId": "U123"},
            "message": {"type": "image"},
        }]}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        with patch("line_messaging.LINE_BOT_CHANNEL_SECRET", secret), \
             patch("blueprints.line_webhook.line_messaging.reply_message") as reply:
            response = self.client.post(
                "/line/webhook", data=body, content_type="application/json",
                headers={"X-Line-Signature": signature(secret, body)},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("看不懂", reply.call_args.args[1])

    def test_command_keyword_inside_sentence(self):
        self.assertEqual(normalize("我想看" + NEXT_TRIP), NEXT_TRIP)


if __name__ == "__main__":
    unittest.main()
