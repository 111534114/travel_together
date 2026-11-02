import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from flask import session

from app import app
from blueprints.friend_groups import _active_group_access, ai_plan, approve_group_member, leave_group
from group_ai_planner import normalize_plan
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
                 patch("blueprints.friend_groups.ANTHROPIC_API_KEY", ""):
                html = ai_plan()
        self.assertIn("AI 尚未啟用", html)
        self.assertIn("伺服器缺少 ANTHROPIC_API_KEY", html)
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
