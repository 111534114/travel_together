import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from flask import session

import blueprints.member as member
from app import app
from chat_moderation import REMOVED_CHAT_CONTENT


def run_send(cursor, body, reply_ready=True, members=()):
    cursor.lastrowid = 77
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with app.test_request_context("/member/trips/8/chat", method="POST", json=body):
        session.update(user_id=2, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection), \
             patch("blueprints.member._member_access", return_value={"member_role": "editor", "trip_id": 8, "trip_name": "台北"}), \
             patch("blueprints.member._chat_reply_available", return_value=reply_ready), \
             patch("blueprints.member.blocked_term", return_value=None), \
             patch("blueprints.member._load_mention_members", return_value=list(members)), \
             patch("blueprints.member.send_notification") as notify:
            result = member.chat_send(8)
    response, status = result if isinstance(result, tuple) else (result, 200)
    return response, status, connection, notify


class ChatReplySendTests(unittest.TestCase):
    MEMBERS = [{"user_id": 2, "nickname": "喵喵喵", "full_name": "喵"}, {"user_id": 5, "nickname": "安婷", "full_name": "安婷"}]

    def test_reply_is_saved_and_author_is_notified(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"user_id": 5, "content": "白癡"}
        cursor.lastrowid = 77
        response, status, connection, notify = run_send(cursor, {"content": "傻傻的", "reply_to": 40}, members=self.MEMBERS)
        self.assertEqual(status, 200)
        inserts = [c.args for c in cursor.execute.call_args_list if c.args[0].startswith("INSERT INTO trip_chat_messages")]
        self.assertIn("reply_to_message_id", inserts[0][0])
        self.assertEqual(inserts[0][1], (8, 2, "傻傻的", 40))
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[1], 5)  # 通知被回覆的安婷
        self.assertIn("回覆了你", notify.call_args.args[5])
        connection.commit.assert_called_once()

    def test_replying_to_self_does_not_notify(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"user_id": 2, "content": "我自己說的"}
        _, status, _, notify = run_send(cursor, {"content": "補充一下", "reply_to": 40}, members=self.MEMBERS)
        self.assertEqual(status, 200)
        notify.assert_not_called()

    def test_reply_to_removed_or_other_trip_message_is_refused(self):
        for found in (None, {"user_id": 5, "content": REMOVED_CHAT_CONTENT}):
            cursor = MagicMock()
            cursor.fetchone.return_value = found
            response, status, connection, _ = run_send(cursor, {"content": "嗨", "reply_to": 40})
            self.assertEqual(status, 400)
            self.assertIn("不存在或已被移除", response.get_json()["error"])
            connection.commit.assert_not_called()

    def test_reply_before_migration_gives_clear_message(self):
        response, status, connection, _ = run_send(MagicMock(), {"content": "嗨", "reply_to": 40}, reply_ready=False)
        self.assertEqual(status, 400)
        self.assertIn("還沒開通", response.get_json()["error"])
        connection.commit.assert_not_called()

    def test_plain_message_still_works_without_column(self):
        cursor = MagicMock()
        cursor.lastrowid = 9
        _, status, _, _ = run_send(cursor, {"content": "大家好"}, reply_ready=False)
        self.assertEqual(status, 200)
        insert = next(c.args for c in cursor.execute.call_args_list if c.args[0].startswith("INSERT INTO trip_chat_messages"))
        self.assertNotIn("reply_to_message_id", insert[0])

    def test_bad_reply_id_is_ignored(self):
        for bad in ("40", True, -3, 0):
            cursor = MagicMock()
            _, status, _, _ = run_send(cursor, {"content": "大家好", "reply_to": bad})
            self.assertEqual(status, 200)
            insert = next(c.args for c in cursor.execute.call_args_list if c.args[0].startswith("INSERT INTO trip_chat_messages"))
            self.assertNotIn("reply_to_message_id", insert[0])


class ChatReplyFeedTests(unittest.TestCase):
    def row(self, **extra):
        base = {"message_id": 41, "user_id": 2, "content": "傻傻的", "created_at": datetime(2026, 11, 27, 14, 42),
                "full_name": "喵", "nickname": "喵喵喵", "reply_to_message_id": None}
        base.update(extra)
        return base

    def feed(self, rows, reply_ready=True):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [rows, []]
        cursor.fetchone.return_value = {"latest": 41}
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/trips/8/chat"):
            session.update(user_id=2, role="member")
            with patch("blueprints.member.get_db_connection", return_value=connection), \
                 patch("blueprints.member._member_access", return_value={"member_role": "editor"}), \
                 patch("blueprints.member._chat_reply_available", return_value=reply_ready), \
                 patch("blueprints.member._chat_members", return_value=[]), \
                 patch("blueprints.member._open_vote_progress", return_value=[]):
                data = member.chat_feed(8).get_json()
        return data, cursor

    def test_feed_includes_replied_message(self):
        data, cursor = self.feed([self.row(reply_to_message_id=40, reply_content="白癡", reply_user_id=5,
                                           reply_full_name="安婷", reply_nickname=None)])
        self.assertTrue(data["can_reply"])
        self.assertEqual(data["messages"][0]["reply"], {"id": 40, "user_id": 5, "name": "安婷", "content": "白癡"})
        self.assertIn("LEFT JOIN trip_chat_messages p", cursor.execute.call_args_list[0].args[0])

    def test_removed_or_missing_original_is_shown_safely(self):
        data, _ = self.feed([
            self.row(reply_to_message_id=40, reply_content=REMOVED_CHAT_CONTENT, reply_user_id=5, reply_full_name="安婷", reply_nickname=None),
            self.row(message_id=42, reply_to_message_id=39, reply_content=None),
        ])
        self.assertEqual(data["messages"][0]["reply"]["content"], "訊息已由團長移除")
        self.assertEqual(data["messages"][1]["reply"]["content"], "原訊息已不存在")

    def test_feed_without_column_has_no_reply_fields_in_sql(self):
        data, cursor = self.feed([self.row()], reply_ready=False)
        self.assertFalse(data["can_reply"])
        self.assertIsNone(data["messages"][0]["reply"])
        self.assertNotIn("reply_to_message_id", cursor.execute.call_args_list[0].args[0])


class TripDiscussionRemovedTests(unittest.TestCase):
    def post_comment(self, form):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"itinerary_id": 3}
        connection = MagicMock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as s:
            s.update(user_id=2, role="member")
        with patch("blueprints.member._connection_or_home", return_value=connection), \
             patch("blueprints.member._member_access", return_value={"member_role": "editor", "trip_id": 8, "trip_name": "台北"}), \
             patch("blueprints.member._notify_mentions"), patch("blueprints.member._load_mention_members", return_value=[]):
            response = client.post("/member/trips/8/comments", data=form)
        inserted = any(c.args[0].strip().startswith("INSERT INTO comments") for c in cursor.execute.call_args_list)
        return response, inserted

    def test_trip_wide_comment_is_refused_and_goes_to_chat(self):
        response, inserted = self.post_comment({"content": "大家好"})
        self.assertFalse(inserted)
        self.assertTrue(response.headers["Location"].endswith("#chat"))

    def test_itinerary_item_comment_is_refused(self):
        response, inserted = self.post_comment({"content": "這家要訂位", "itinerary_id": "3"})
        self.assertFalse(inserted)  # 行程項目底下的留言也拿掉了
        self.assertTrue(response.headers["Location"].endswith("#chat"))

    def test_proposal_comment_still_works(self):
        response, inserted = self.post_comment({"content": "我覺得不錯", "proposal_id": "3"})
        self.assertTrue(inserted)
        self.assertTrue(response.headers["Location"].endswith("#proposals"))

    def test_trip_page_code_no_longer_loads_discussion(self):
        source = open("blueprints/member.py", encoding="utf-8").read()
        self.assertNotIn("_load_comments(", source)
        self.assertNotIn("#discussion", source)


class TripPageTests(unittest.TestCase):
    def test_discussion_tab_is_gone_and_chat_has_reply_bar(self):
        html = open("templates/member/trip_detail.html", encoding="utf-8").read()
        self.assertNotIn('data-tab-target="discussion"', html)
        self.assertNotIn('id="discussion"', html)
        self.assertIn('id="chatReplyBar"', html)
        self.assertIn('id="chatToast"', html)
        self.assertIn("if (initial === 'discussion') initial = 'chat'", html)  # 舊通知連結改開聊天室


if __name__ == "__main__":
    unittest.main()
