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

    def test_public_trips_have_a_separate_page_when_group_feature_is_off(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [[], []]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = self.client.get("/member/public-trips")

        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/member/public-trips"', response.get_data(as_text=True))
        sql = "\n".join(str(call.args[0]) for call in cursor.execute.call_args_list)
        self.assertIn("WHERE t.visibility = 'public'", sql)
        self.assertNotIn("OR t.people_count > 1", sql)

    def test_public_trip_card_opens_detail_and_keeps_favorite_action(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [[{
            "trip_id": 23, "trip_name": "日本七日遊", "country": "日本", "city": "北海道",
            "owner_nickname": "Leo", "owner_name": "Leo", "introduction": "賞景與美食",
            "start_date": "2026-11-11", "end_date": "2026-11-17", "people_count": 5,
            "joined_count": 2, "currency": "TWD", "total_budget": 50000,
        }], [{"trip_id": 23}]]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = self.client.get("/member/public-trips")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("日本七日遊", html)
        self.assertIn('href="/member/friend-groups/companions/23"', html)
        self.assertIn('action="/member/trips/23/favorite"', html)
        self.assertIn("取消收藏", html)

    def test_public_trip_detail_is_browse_only(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {
                "trip_id": 23, "owner_id": 9, "trip_name": "台北三天兩夜",
                "country": "台灣", "city": "台北市", "owner_nickname": "Leo",
                "owner_name": "Leo", "start_date": "2026-11-11",
                "end_date": "2026-11-13", "days_count": 3, "people_count": 3,
                "currency": "TWD", "total_budget": 15000,
                "introduction": "測試行程", "allow_copy": True,
            },
            None, {"c": 1}, None, None,
        ]
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch("blueprints.friend_groups.get_db_connection", return_value=connection):
            response = self.client.get("/member/friend-groups/companions/23")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("台北三天兩夜", html)
        self.assertIn("行程明細", html)
        self.assertIn('action="/member/trips/23/favorite"', html)
        self.assertNotIn("申請加入", html)
        self.assertNotIn("/companions/23/apply", html)

    def test_public_trip_application_endpoint_does_not_join(self):
        with patch("blueprints.friend_groups.get_db_connection") as connect:
            response = self.client.post(
                "/member/friend-groups/companions/23/apply",
                data={"note": "想參加"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/member/friend-groups/companions/23"))
        connect.assert_not_called()

    def test_new_templates_compile(self):
        for name in (
            "member/friend_groups/index.html",
            "member/public_trips.html",
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
