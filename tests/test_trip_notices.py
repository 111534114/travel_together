import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import blueprints.member as member
from app import app


class CountTests(unittest.TestCase):
    def test_no_trips_means_no_queries(self):
        cursor = MagicMock()
        self.assertEqual(member._trip_unread_counts(cursor, 4, []), ({}, {}))
        cursor.execute.assert_not_called()

    def test_counts_notices_and_chat_per_trip(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [[{"trip_id": 13, "n": 2}], [{"trip_id": 13, "n": 5}]]
        self.assertEqual(member._trip_unread_counts(cursor, 4, [13, 14]), ({13: 2}, {13: 5}))
        chat_sql, chat_params = cursor.execute.call_args_list[1].args
        self.assertIn("m.user_id <> %s", chat_sql)  # 自己傳的訊息不算未讀
        self.assertEqual(chat_params, (4, 13, 14, 4, member.REMOVED_CHAT_CONTENT))

    def test_chat_table_problem_does_not_break_page(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [[], Exception("no table")]
        self.assertEqual(member._trip_unread_counts(cursor, 4, [13]), ({}, {}))


class PageTests(unittest.TestCase):
    def test_trip_card_shows_alerts_without_notice_list(self):
        trips = [{"trip_id": 13, "trip_name": "台北", "start_date": date(2026, 11, 11), "end_date": date(2099, 12, 31),
                  "country": "台灣", "city": "台北市", "member_role": "owner", "visibility": "public", "cover_image_path": None,
                  "member_count": 4, "itinerary_count": 7}]
        cursor = MagicMock()
        cursor.fetchall.side_effect = [[], trips, [], [], [], []]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as s:
            s.update(user_id=4, role="member", tour_seen=True)
        with patch("blueprints.member._connection_or_home", return_value=connection),              patch("blueprints.member._trip_unread_counts", return_value=({13: 2}, {13: 3})),              patch("blueprints.member._build_trips_timeline", return_value={}):
            html = client.get("/member/trips").get_data(as_text=True)
        self.assertIn("🔔 2 則新通知", html)
        self.assertIn("💬 3 則未讀訊息", html)
        self.assertIn('href="/member/trips/13#chat"', html)
        self.assertNotIn('id="trip-notices"', html)  # 旅程通知清單不要了
        self.assertIn("memberNotificationBell", html)  # 🔔 改成打開右下角鈴鐺


class SideMenuBadgeTests(unittest.TestCase):
    def test_counts_trip_notices_and_chat(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"n": 2}, {"n": 3}]
        self.assertEqual(member._my_trips_unread(cursor, 4), (2, 3))
        notice_sql = cursor.execute.call_args_list[0].args[0]
        self.assertIn("t.deleted_at IS NULL", notice_sql)  # 刪掉的旅程不算
        self.assertIn("join_status = 'accepted'", notice_sql)

    def test_problem_counts_as_zero(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [Exception("x"), Exception("y")]
        self.assertEqual(member._my_trips_unread(cursor, 4), (0, 0))

    def test_bell_feed_carries_my_trips_total(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"total": 1}, {"n": 2}, {"n": 3}]
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as s:
            s.update(user_id=4, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection):
            data = client.get("/member/notifications/unread").get_json()
        self.assertEqual(data["my_trips"], {"notices": 2, "chat": 3, "total": 5})

    def test_menu_has_badge_slot(self):
        html = open("templates/partials/member_nav_links.html", encoding="utf-8").read()
        self.assertIn("我的旅程<b class=\"side-badge\" data-my-trips-badge hidden></b>", html)


class BellTests(unittest.TestCase):
    def test_bell_items_carry_trip_name(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"total": 1}
        cursor.fetchall.return_value = [{"notification_id": 1, "title": "t", "message": "m", "target_url": None,
                                         "created_at": datetime(2026, 11, 27, 14, 39), "is_read": 0, "trip_name": "台北"}]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as s:
            s.update(user_id=4, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection):
            data = client.get("/member/notifications/unread").get_json()
        self.assertEqual(data["notifications"][0]["trip_name"], "台北")
        self.assertIn("LEFT JOIN trips", cursor.execute.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
