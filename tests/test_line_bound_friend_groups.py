import unittest
from unittest.mock import MagicMock, patch

from flask import redirect

from app import app


class LineBoundFriendGroupTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=7, role="member")

    def test_unbound_member_sees_bind_prompt_without_losing_companion_page(self):
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
        self.assertEqual(render.call_args.kwargs["companions"], [])
        self.assertIn("SELECT line_sub FROM users", "\n".join(
            call.args[0] for call in cursor.execute.call_args_list
        ))

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
