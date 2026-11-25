import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from flask import render_template, session

from app import app
from blueprints.friend_groups import _can_restore_group, restore_group


class GroupRestoreTests(unittest.TestCase):
    def test_only_cancelled_groups_before_start_are_restorable(self):
        start = date(2099, 1, 5)
        group = {"status": "cancelled", "event_date": start, "start_time": "09:00"}
        self.assertTrue(_can_restore_group(group, datetime(2099, 1, 5, 8, 59)))
        self.assertFalse(_can_restore_group(group, datetime(2099, 1, 5, 9, 0)))
        self.assertFalse(_can_restore_group({**group, "status": "open"}, datetime(2099, 1, 4, 8, 0)))

    def test_cancelled_manage_page_shows_restore_button(self):
        group = {"group_id": 8, "trip_id": 9, "title": "宜蘭行", "status": "cancelled",
                 "event_date": date(2099, 1, 5), "location": "宜蘭", "formation_status": None}
        with app.test_request_context("/member/friend-groups/groups/8/manage"):
            html = render_template("member/friend_groups/group_manage.html", group=group, members=[],
                                   can_restore=True, can_mark_attended=False, can_mark_no_show=False)
        self.assertIn("恢復揪團", html)
        self.assertIn("/member/friend-groups/groups/8/restore", html)

    def _restore(self, deadline, *, host_id=1, restorable=True, other_active_groups=0):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"group_id": 8, "host_user_id": host_id, "title": "宜蘭行",
             "status": "cancelled", "trip_id": 9, "moderation_locked": 0,
             "event_date": date.today() + timedelta(days=7)},
            {"owner_id": 1, "status": "planning", "other_active_groups": other_active_groups},
        ]
        cursor.fetchall.return_value = [{"user_id": 2}]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/8/restore", method="POST"):
            session.update(user_id=1, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._can_restore_group", return_value=restorable), \
                 patch("blueprints.friend_groups._registration_deadline", return_value=deadline), \
                 patch("blueprints.friend_groups.send_notification") as notify:
                response = restore_group(8)
        return response, cursor, connection, notify

    def test_restore_reopens_registration_before_deadline_and_restores_access(self):
        response, cursor, connection, notify = self._restore(date.today() + timedelta(days=1))
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_called_once()
        statements = [call.args for call in cursor.execute.call_args_list]
        self.assertIn(("open", 8), [args[1] for args in statements if "UPDATE friend_groups SET status" in args[0]])
        self.assertTrue(any("UPDATE trip_members SET join_status='accepted'" in args[0] for args in statements))
        self.assertTrue(any("DELETE FROM app_settings" in args[0] for args in statements))
        self.assertEqual(notify.call_args.args[1], 2)
        self.assertEqual(notify.call_args.args[4], "揪團已恢復")

    def test_restore_keeps_registration_closed_after_deadline(self):
        response, cursor, connection, notify = self._restore(date.today() - timedelta(days=1))
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_called_once()
        statuses = [call.args[1][0] for call in cursor.execute.call_args_list
                    if "UPDATE friend_groups SET status" in call.args[0]]
        self.assertEqual(statuses, ["closed"])
        notify.assert_called_once()

    def test_other_member_or_started_group_cannot_restore(self):
        for host_id, restorable in ((2, True), (1, False)):
            with self.subTest(host_id=host_id, restorable=restorable):
                _, cursor, connection, notify = self._restore(date.today(), host_id=host_id,
                                                                restorable=restorable)
                connection.commit.assert_not_called()
                notify.assert_not_called()
                self.assertFalse(any("UPDATE friend_groups" in call.args[0]
                                     for call in cursor.execute.call_args_list))

    def test_cannot_restore_when_trip_is_used_by_another_active_group(self):
        _, cursor, connection, notify = self._restore(date.today(), other_active_groups=1)
        connection.commit.assert_not_called()
        notify.assert_not_called()
        self.assertFalse(any("UPDATE trip_members" in call.args[0]
                             for call in cursor.execute.call_args_list))


if __name__ == "__main__":
    unittest.main()
