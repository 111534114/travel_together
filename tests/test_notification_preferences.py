import unittest
from unittest.mock import MagicMock

from mysql.connector import Error

from notification_preferences import NOTIFICATION_CATEGORIES, get_preferences, save_preferences, send_notification


class NotificationPreferenceTests(unittest.TestCase):
    def test_category_uses_preference_filter(self):
        cursor = MagicMock()
        send_notification(cursor, 5, "event", "system", "活動公告更新", "有新公告", "/events/1")
        sql, values = cursor.execute.call_args.args
        self.assertIn("NOT EXISTS", sql)
        self.assertEqual(values[-1], "event")

    def test_system_notification_cannot_be_disabled(self):
        cursor = MagicMock()
        send_notification(cursor, 5, "system", "system", "管理通知", "已處理")
        self.assertNotIn("notification_preferences", cursor.execute.call_args.args[0])

    def test_missing_table_preserves_original_notifications(self):
        cursor = MagicMock()
        cursor.execute.side_effect = [Error(errno=1146), None]
        send_notification(cursor, 5, "trip", "invitation", "旅程邀請", "內容", "/member/", trip_id=3)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertNotIn("notification_preferences", cursor.execute.call_args.args[0])

    def test_defaults_are_enabled(self):
        cursor = MagicMock()
        cursor.execute.side_effect = Error(errno=1146)
        self.assertEqual(get_preferences(cursor, 5), {key: True for key in NOTIFICATION_CATEGORIES})

    def test_save_writes_all_categories(self):
        cursor = MagicMock()
        save_preferences(cursor, 5, {"trip"})
        self.assertEqual(cursor.execute.call_count, len(NOTIFICATION_CATEGORIES))
        self.assertEqual(cursor.execute.call_args.args[1][-1], False)
