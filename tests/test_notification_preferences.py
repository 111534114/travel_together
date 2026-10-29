import unittest
from unittest.mock import MagicMock

from mysql.connector import Error

from app import app
from notification_preferences import NOTIFICATION_CATEGORIES, get_preferences, save_preferences, send_notification


class NotificationPreferenceTests(unittest.TestCase):
    def test_send_skips_when_member_turned_category_off(self):
        cursor = MagicMock()
        send_notification(cursor, 5, "event", "system", "活動公告更新", "有新公告", "/events/1")

        sql, values = cursor.execute.call_args.args
        self.assertIn("INSERT INTO notifications", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("enabled=FALSE", sql)
        self.assertEqual(values, (5, None, "system", "活動公告更新", "有新公告", "/events/1", 5, "event"))

    def test_system_notifications_ignore_preferences(self):
        cursor = MagicMock()
        send_notification(cursor, 5, "system", "system", "公開行程管理通知", "已隱藏")

        sql, _ = cursor.execute.call_args.args
        self.assertNotIn("notification_preferences", sql)

    def test_send_falls_back_when_preference_table_missing(self):
        cursor = MagicMock()
        cursor.execute.side_effect = [Error(errno=1146), None]
        send_notification(cursor, 5, "trip", "invitation", "收到旅程邀請", "你被邀請", "/member/", trip_id=3)

        self.assertEqual(cursor.execute.call_count, 2)
        sql, values = cursor.execute.call_args.args
        self.assertNotIn("notification_preferences", sql)
        self.assertEqual(values, (5, 3, "invitation", "收到旅程邀請", "你被邀請", "/member/"))

    def test_members_without_settings_get_every_category(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        self.assertTrue(all(get_preferences(cursor, 5).values()))

        cursor.fetchall.return_value = [{"category": "album", "enabled": 0}, {"category": "unknown", "enabled": 0}]
        preferences = get_preferences(cursor, 5)
        self.assertFalse(preferences["album"])
        self.assertEqual(set(preferences), set(NOTIFICATION_CATEGORIES))

    def test_save_records_unchecked_categories_as_off(self):
        cursor = MagicMock()
        save_preferences(cursor, 5, {"trip", "mention"})

        saved = {call.args[1][1]: call.args[1][2] for call in cursor.execute.call_args_list}
        self.assertEqual(saved, {key: key in {"trip", "mention"} for key in NOTIFICATION_CATEGORIES})

    def test_profile_template_compiles(self):
        self.assertIsNotNone(app.jinja_env.get_template("member/profile.html"))


if __name__ == "__main__":
    unittest.main()
