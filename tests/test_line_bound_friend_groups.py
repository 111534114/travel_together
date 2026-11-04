import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from flask import redirect

from app import app


class LineBoundFriendGroupTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=7, role="member")

    def test_unbound_member_sees_bind_prompt_without_public_trips_on_group_page(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"setting_value": "1"}, {"line_sub": None}]
        cursor.fetchall.side_effect = [[], []]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch("blueprints.friend_groups.get_db_connection", return_value=connection), \
             patch("blueprints.friend_groups.render_template", return_value="ok") as render:
            response = self.client.get("/member/friend-groups/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(render.call_args.kwargs["line_bound"])
        self.assertIsNone(render.call_args.kwargs["application"])
        sql = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertIn("SELECT line_sub FROM users", sql)
        self.assertNotIn("WHERE t.visibility = 'public'", sql)

    def test_unbound_member_can_search_and_open_public_group(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"setting_value": "1"}, {"line_sub": None}]
        cursor.fetchall.return_value = [{
            "group_id": 12, "title": "花蓮賞鯨揪團", "description": "一起賞鯨", "event_date": date(2099, 6, 1),
            "end_date": date(2099, 6, 1), "location": "花蓮", "city": None, "country": None,
            "total_budget": None, "capacity": 4, "member_count": 1, "my_status": None,
            "nickname": "Leo", "full_name": "Leo",
        }]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch("blueprints.friend_groups.get_db_connection", return_value=connection):
            response = self.client.get("/member/friend-groups/?region=花蓮")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("花蓮賞鯨揪團", html)
        self.assertIn('href="/member/friend-groups/groups/12"', html)

    def test_group_detail_can_be_read_before_qualification_but_join_requires_it(self):
        group = {
            "group_id": 12, "host_user_id": 9, "title": "花蓮賞鯨揪團", "status": "open",
            "event_date": date(2099, 6, 1), "end_date": date(2099, 6, 1),
            "start_time": None, "location": "花蓮", "description": "一起賞鯨",
            "capacity": 4, "trip_id": None, "show_member_list": False,
            "meeting_info": None, "nickname": "Leo", "full_name": "Leo",
        }

        def render_detail(line_bound):
            cursor = MagicMock()
            cursor.fetchone.side_effect = [{"setting_value": "1"}, group, None]
            cursor.fetchall.return_value = []
            connection = MagicMock()
            connection.cursor.return_value = cursor
            with patch("blueprints.friend_groups.get_db_connection", return_value=connection), \
                 patch("blueprints.friend_groups._has_line_bound", return_value=line_bound), \
                 patch("blueprints.friend_groups._can_use_groups", return_value=line_bound), \
                 patch("blueprints.friend_groups._host_tier", return_value={"level": 1, "label": "新手團長", "avg_rating": None}):
                return self.client.get("/member/friend-groups/groups/12")

        unqualified = render_detail(False)
        self.assertEqual(unqualified.status_code, 200)
        self.assertIn("花蓮賞鯨揪團", unqualified.get_data(as_text=True))
        self.assertNotIn('action="/member/friend-groups/groups/12/apply"', unqualified.get_data(as_text=True))
        qualified = render_detail(True)
        self.assertEqual(qualified.status_code, 200)
        self.assertIn('action="/member/friend-groups/groups/12/apply"', qualified.get_data(as_text=True))

    def test_unqualified_member_cannot_submit_group_application(self):
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        with patch("blueprints.friend_groups.get_db_connection", return_value=connection), \
             patch("blueprints.friend_groups._feature_enabled", return_value=True), \
             patch("blueprints.friend_groups._has_line_bound", return_value=True), \
             patch("blueprints.friend_groups._can_use_groups", return_value=False):
            response = self.client.post("/member/friend-groups/groups/12/apply", data={"note": "想參加"})

        self.assertEqual(response.status_code, 302)
        connection.commit.assert_not_called()

    def test_unbound_member_cannot_submit_group_application(self):
        connection = MagicMock()
        connection.cursor.return_value = MagicMock()
        with patch("blueprints.friend_groups.get_db_connection", return_value=connection), \
             patch("blueprints.friend_groups._feature_enabled", return_value=True), \
             patch("blueprints.friend_groups._has_line_bound", return_value=False):
            response = self.client.post("/member/friend-groups/apply", data={})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/member/friend-groups/#friend-groups"))
        connection.commit.assert_not_called()

    def test_line_binding_remembers_safe_return_page(self):
        with patch("app.LINE_CHANNEL_ID", "test-id"), \
             patch("app.LINE_CHANNEL_SECRET", "test-secret"), \
             patch("app.line_oauth.authorize_redirect", return_value=redirect("/mock-line")):
            response = self.client.get("/auth/line/bind", query_string={
                "next": "/member/friend-groups/#friend-groups",
            })
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session["line_bind_next"], "/member/friend-groups/#friend-groups")

    def test_line_binding_rejects_external_return_page(self):
        with patch("app.LINE_CHANNEL_ID", "test-id"), \
             patch("app.LINE_CHANNEL_SECRET", "test-secret"), \
             patch("app.line_oauth.authorize_redirect", return_value=redirect("/mock-line")):
            self.client.get("/auth/line/bind", query_string={"next": "//evil.example"})
        with self.client.session_transaction() as session:
            self.assertNotIn("line_bind_next", session)

    def test_successful_binding_returns_to_requested_page(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        with app.test_request_context("/auth/line/callback"):
            from flask import session
            from app import bind_line_to_current_user

            session.update(user_id=7, role="member")
            with patch("app.get_db_connection", return_value=connection):
                response = bind_line_to_current_user(
                    "line-user", True, next_url="/member/friend-groups/#friend-groups"
                )
        self.assertEqual(response.headers["Location"], "/member/friend-groups/#friend-groups")
        connection.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
