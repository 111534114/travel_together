import unittest
from unittest.mock import MagicMock, patch

from app import app


class October24MergeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "member"

    def test_old_companion_url_redirects_to_merged_page(self):
        response = self.client.get("/member/companions")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/member/friend-groups/#companions"))

    def test_companion_list_only_queries_public_trips_even_when_group_feature_is_off(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"setting_value": "0"}
        cursor.fetchall.side_effect = [[], []]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch("blueprints.friend_groups.get_db_connection", return_value=connection), \
             patch("blueprints.friend_groups.render_template", return_value="ok"):
            response = self.client.get("/member/friend-groups/")

        self.assertEqual(response.status_code, 200)
        sql = "\n".join(str(call.args[0]) for call in cursor.execute.call_args_list)
        self.assertIn("WHERE t.visibility = 'public'", sql)
        self.assertNotIn("OR t.people_count > 1", sql)

    def test_new_templates_compile(self):
        for name in (
            "member/friend_groups/index.html",
            "member/friend_groups/browse_groups.html",
            "member/friend_groups/companion_trip.html",
            "member/friend_groups/event_detail.html",
            "member/friend_groups/group_new.html",
            "member/trip_detail.html",
            "content_admin/friend_groups/event_participants.html",
        ):
            with self.subTest(name=name):
                self.assertIsNotNone(app.jinja_env.get_template(name))


if __name__ == "__main__":
    unittest.main()
