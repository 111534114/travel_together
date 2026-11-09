import json
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from flask import session

from app import app
from blueprints.friend_groups import _active_group_access, _album_image_type, _registration_deadline, ai_plan, approve_group_member, leave_group, save_ai_plan
from blueprints.member import chat_feed, chat_remove, chat_send
from group_ai_planner import generate_plan, normalize_plan
from chat_moderation import blocked_term, parse_terms
from content_admin_permissions import _ENDPOINT_ACTIONS


class FakeCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return next(self.rows)


class GroupFeatureTests(unittest.TestCase):
    def test_chat_feed_returns_json_for_trip_owner(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [[], []]
        cursor.fetchone.return_value = {"latest": 0}
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/trips/8/chat?after=1"):
            session.update(user_id=2, role="member")
            with patch("blueprints.member.get_db_connection", return_value=connection), \
                 patch("blueprints.member._member_access", return_value={"member_role": "owner"}), \
                 patch("blueprints.member._chat_members", return_value=[]), \
                 patch("blueprints.member._open_vote_progress", return_value=[]):
                response = chat_feed(8)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["can_moderate"])

    def test_album_image_type_supports_allowed_headers(self):
        self.assertEqual(_album_image_type(b"\xff\xd8\xff\xe0data"), "jpeg")
        self.assertEqual(_album_image_type(b"\x89PNG\r\n\x1a\ndata"), "png")
        self.assertEqual(_album_image_type(b"GIF89adata"), "gif")
        self.assertEqual(_album_image_type(b"RIFF\x04\x00\x00\x00WEBPdata"), "webp")
        self.assertIsNone(_album_image_type(b"RIFF\x04\x00\x00\x00WAVEdata"))
        self.assertIsNone(_album_image_type(b"not an image"))

    def test_report_handling_requires_admin_edit_permission(self):
        self.assertEqual(_ENDPOINT_ACTIONS["friend_groups_admin"]["handle_group_report"], "edit")

    def test_removed_member_cannot_access_group_private_content(self):
        cursor = FakeCursor([{"group_id": 3, "host_user_id": 1, "trip_id": 9}, None])
        self.assertIsNone(_active_group_access(cursor, 3, 2))
        self.assertIn("m.status='approved'", cursor.queries[-1][0])
        self.assertIn("tm.join_status='accepted'", cursor.queries[-1][0])

    def test_host_can_access_group_private_content(self):
        cursor = FakeCursor([{"group_id": 3, "host_user_id": 1, "trip_id": 9}])
        self.assertEqual(_active_group_access(cursor, 3, 1)["group_id"], 3)
        self.assertEqual(len(cursor.queries), 1)

    def test_ai_plan_drops_dates_outside_trip_and_invalid_items(self):
        plan = normalize_plan({"summary": "台北行", "items": [
            {"date": "2026-12-01", "type": "transport", "title": "搭乘交通", "estimated_cost": 500},
            {"date": "2026-12-10", "type": "attraction", "title": "不在行程內"},
            {"date": "2026-12-02", "type": "unknown", "title": "不支援"},
        ]}, date(2026, 12, 1), date(2026, 12, 3))
        self.assertEqual(len(plan["items"]), 1)
        self.assertEqual(plan["items"][0]["type"], "transport")

    def test_ai_plan_requires_a_valid_item(self):
        with self.assertRaises(ValueError):
            normalize_plan({"items": [{"date": "2026-12-10", "type": "other", "title": "X"}]},
                           date(2026, 12, 1), date(2026, 12, 3))

    def test_ai_plan_shows_missing_key_beside_disabled_button(self):
        connection = MagicMock()
        with app.test_request_context("/member/friend-groups/ai-plan"):
            session.update(user_id=2, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups.get_countries", return_value=[]), \
                 patch("blueprints.friend_groups.get_cities", return_value=[]), \
                 patch("blueprints.friend_groups.ANTHROPIC_API_KEY", ""), \
                 patch("blueprints.friend_groups.GEMINI_API_KEY", ""):
                html = ai_plan()
        self.assertIn("智慧規劃尚未啟用", html)
        self.assertIn("伺服器尚未設定智慧規劃服務金鑰", html)
        self.assertIn('disabled aria-describedby="aiPlanStatus"', html)

    def test_ai_plan_checks_draft_table_before_calling_external_ai(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"name": "日本"}, {"name": "東京"}, {"table_count": 0}]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        form = {"country_id": "1", "city_id": "2", "start_date": "2099-01-01",
                "end_date": "2099-01-02", "people_count": "2", "budget": "1000",
                "user_request": "景點與美食"}
        with app.test_request_context("/member/friend-groups/ai-plan", method="POST", data=form):
            session.update(user_id=2, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups.get_countries", return_value=[{"country_id": 1, "name": "日本"}]), \
                 patch("blueprints.friend_groups.get_cities", return_value=[{"city_id": 2, "country_id": 1, "name": "東京"}]), \
                 patch("blueprints.friend_groups._city_matches_country", return_value=True), \
                 patch("blueprints.friend_groups.ANTHROPIC_API_KEY", "test-key"), \
                 patch("blueprints.friend_groups.generate_plan") as generate:
                response, status = ai_plan()
        self.assertEqual(status, 400)
        self.assertIn("AI 草稿資料表尚未建立", response)
        self.assertIn("景點與美食", response)
        generate.assert_not_called()

    def test_gemini_plan_uses_key_header_and_normalizes_response(self):
        item = {"date": "2026-12-01", "type": "attraction", "title": "台北101"}
        response = MagicMock()
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": '{"items": ['},
                                                                       {"text": json.dumps(item) + "]}"}]}}]}
        with patch("group_ai_planner.GEMINI_API_KEY", "test-gemini"), \
             patch("group_ai_planner.ANTHROPIC_API_KEY", "test-anthropic"), \
             patch("group_ai_planner.requests.post", return_value=response) as post:
            plan = generate_plan("景點", "台灣", "台北", date(2026, 12, 1), date(2026, 12, 2), 2, 1000)
        self.assertEqual(plan["items"][0]["title"], "台北101")
        self.assertIn("/models/gemini-3.5-flash-lite:generateContent", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "test-gemini")
        self.assertNotIn("test-gemini", post.call_args.args[0])

    def test_saving_ai_draft_is_private_even_if_public_is_submitted(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "draft_json": json.dumps({"items": [{"date": "2026-12-01", "type": "attraction", "title": "台北101"}]}),
            "start_date": date(2026, 12, 1), "end_date": date(2026, 12, 2),
            "country_id": 1, "city_id": 2, "people_count": 2, "budget": 1000,
            "user_request": "景點",
        }
        cursor.lastrowid = 17
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/ai-plan/3/save", method="POST", data={"title": "台北兩日遊", "visibility": "public"}):
            session.update(user_id=2, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection):
                response = save_ai_plan(3)
        self.assertEqual(response.status_code, 302)
        inserts = [call.args[0] for call in cursor.execute.call_args_list if "INSERT INTO trips" in call.args[0]]
        self.assertEqual(len(inserts), 1)
        self.assertIn("'private','planning'", inserts[0])
        connection.commit.assert_called_once()

    def test_approval_adds_viewer_to_linked_trip(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"host_user_id": 1, "title": "測試團", "capacity": 5, "trip_id": 8, "status": "open"},
            {"status": "pending"}, {"c": 0},
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/3/members/2/approve", method="POST"):
            session.update(user_id=1, role="member")
            with patch("blueprints.friend_groups.get_db_connection", return_value=connection), \
                 patch("blueprints.friend_groups.send_notification"):
                approve_group_member(3, 2)
        connection.commit.assert_called_once()
        statements = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertIn("member_role='viewer'", statements)
        self.assertIn("join_status='accepted'", statements)

    def test_chat_terms_normalize_spacing_and_fullwidth(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"setting_value": "保證獲利,色情服務"}
        self.assertEqual(blocked_term(cursor, "保 證 獲 利"), "保證獲利")
        self.assertEqual(blocked_term(cursor, "色情 服務"), "色情服務")
        self.assertIsNone(blocked_term(cursor, "集合時間是早上九點"))
        self.assertEqual(parse_terms("詐騙，匯款\n詐騙"), ["詐騙", "匯款"])

    def test_group_registration_deadline_uses_selected_lead_days(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"setting_value": "3"}
        group = {"group_id": 9, "event_date": date(2026, 12, 10)}
        self.assertEqual(_registration_deadline(cursor, group), date(2026, 12, 7))
        self.assertEqual(group["registration_lead_days"], 3)

    def test_trip_chat_rejects_blocked_content_before_insert(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"setting_value": "保證獲利"}
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/trips/8/chat", method="POST", json={"content": "保證獲利，請匯款"}):
            session.update(user_id=2, role="member")
            with patch("blueprints.member.get_db_connection", return_value=connection), \
                 patch("blueprints.member._member_access", return_value={"member_role": "viewer"}):
                response, status = chat_send(8)
        self.assertEqual(status, 400)
        self.assertIn("禁止內容", response.get_json()["error"])
        connection.commit.assert_not_called()

    def test_trip_owner_can_remove_chat_message_with_audit_log(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"content": "不當訊息"}
        cursor.rowcount = 1
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/trips/8/chat/4/remove", method="POST"):
            session.update(user_id=2, role="member")
            with patch("blueprints.member.get_db_connection", return_value=connection), \
                 patch("blueprints.member._member_access", return_value={"member_role": "owner"}):
                response = chat_remove(8, 4)
        self.assertTrue(response.get_json()["ok"])
        statements = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertIn("INSERT INTO edit_logs", statements)
        self.assertIn("UPDATE trip_chat_messages", statements)
        connection.commit.assert_called_once()

    def test_leaving_group_revokes_trip_membership(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"group_id": 3, "trip_id": 8, "host_user_id": 1, "title": "測試團"},
            {"status": "approved"},
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/3/leave", method="POST"):
            session.update(user_id=2, role="member")
            with patch("blueprints.friend_groups.get_db_connection", return_value=connection), \
                 patch("blueprints.friend_groups.send_notification"):
                leave_group(3)
        connection.commit.assert_called_once()
        statements = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertIn("UPDATE trip_members SET join_status='left'", statements)


if __name__ == "__main__":
    unittest.main()
