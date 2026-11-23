import unittest
from unittest.mock import MagicMock, patch

from flask import session

from app import app
from blueprints.friend_groups import _can_use_groups, index
from blueprints.friend_groups_admin import early_access, set_early_access


class GroupEarlyAccessTests(unittest.TestCase):
    def test_approved_application_with_completed_event_keeps_normal_access(self):
        cursor = MagicMock()
        with patch("blueprints.friend_groups._latest_application", return_value={"status": "approved"}), \
             patch("blueprints.friend_groups._has_attended_event", return_value=True):
            self.assertTrue(_can_use_groups(cursor, 7))
        cursor.execute.assert_not_called()

    def test_early_access_requires_approved_application_and_today_checkin(self):
        for application, setting, checked_in, expected in [
            ({"status": "pending"}, None, None, False),
            ({"status": "approved"}, None, None, False),
            ({"status": "approved"}, {"setting_value": "1"}, None, False),
            ({"status": "approved"}, {"setting_value": "1"}, {"ok": 1}, True),
        ]:
            cursor = MagicMock()
            cursor.fetchone.side_effect = [setting, checked_in]
            with self.subTest(application=application, setting=setting, checked_in=checked_in), \
                 patch("blueprints.friend_groups._latest_application", return_value=application), \
                 patch("blueprints.friend_groups._has_attended_event", return_value=False):
                self.assertEqual(_can_use_groups(cursor, 7), expected)

    def test_system_admin_can_grant_today_checked_in_member(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"ok": 1}
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/content-admin/friend-groups/early-access/7", method="POST",
                                      data={"enabled": "1", "reason": "報告展示"}):
            session.update(user_id=2, role="system_admin")
            with patch("blueprints.friend_groups_admin.get_db_connection", return_value=connection), \
                 patch("blueprints.friend_groups_admin._latest_application", return_value={"status": "approved"}), \
                 patch("blueprints.friend_groups_admin.send_notification"), \
                 patch("blueprints.friend_groups_admin.log_action") as log:
                response = set_early_access(7)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(call.args[1] == ("friend_group_early_access_7", "1", 2)
                            for call in cursor.execute.call_args_list))
        self.assertIn("報告展示", log.call_args.args[-1])
        connection.commit.assert_called_once()

    def test_admin_page_renders(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/content-admin/friend-groups/early-access"):
            session.update(user_id=2, role="system_admin")
            with patch("blueprints.friend_groups_admin.get_db_connection", return_value=connection):
                html = early_access()
        self.assertIn("揪團提早開放", html)

    def test_unchecked_member_cannot_be_granted_early_access(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/content-admin/friend-groups/early-access/7", method="POST",
                                      data={"enabled": "1", "reason": "報告展示"}):
            session.update(user_id=2, role="system_admin")
            with patch("blueprints.friend_groups_admin.get_db_connection", return_value=connection), \
                 patch("blueprints.friend_groups_admin._latest_application", return_value={"status": "approved"}):
                response = set_early_access(7)
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_not_called()
        self.assertFalse(any("INSERT INTO app_settings" in call.args[0]
                             for call in cursor.execute.call_args_list))

    def test_member_page_shows_early_approved_access(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/"):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._feature_enabled", return_value=True), \
                 patch("blueprints.friend_groups._has_line_bound", return_value=True), \
                 patch("blueprints.friend_groups._latest_application", return_value={"status": "approved"}), \
                 patch("blueprints.friend_groups._can_use_groups", return_value=True), \
                 patch("blueprints.friend_groups._traveler_profile", return_value=None), \
                 patch("blueprints.friend_groups._host_tier", return_value={"level": 1}), \
                 patch("blueprints.friend_groups._has_completed_onboarding", return_value=True), \
                 patch("blueprints.friend_groups.render_template", return_value="ok") as render:
                self.assertEqual(index(), "ok")
        self.assertTrue(render.call_args.kwargs["unlocked"])


if __name__ == "__main__":
    unittest.main()
