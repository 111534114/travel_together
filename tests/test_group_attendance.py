import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from flask import render_template, session

from app import app
from blueprints.friend_groups import TAIPEI_TIMEZONE, _group_attendance_availability, set_group_member_attendance


class GroupAttendanceTests(unittest.TestCase):
    def _submit(self, group, member, attendance="attended"):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [group, member]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/8/members/9/attendance",
                                      method="POST", data={"attendance": attendance}):
            session.update(user_id=2, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups.send_notification") as notify:
                response = set_group_member_attendance(8, 9)
        return response, connection, cursor, notify

    def test_host_can_mark_and_correct_attendance(self):
        group = {"host_user_id": 2, "title": "宜蘭行", "status": "open",
                 "event_date": date.today() - timedelta(days=2), "end_date": None}
        for value in ("attended", "no_show"):
            with self.subTest(value=value):
                response, connection, cursor, notify = self._submit(group, {"1": 1}, value)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(any(call.args[1] == (f"fg_att_8_9", value, 2)
                                    for call in cursor.execute.call_args_list))
                connection.commit.assert_called_once()
                notify.assert_called_once()

    def test_host_can_mark_attended_on_departure_day_but_not_no_show_yet(self):
        today = datetime.now(TAIPEI_TIMEZONE).date()
        group = {"host_user_id": 2, "title": "宜蘭行", "status": "open",
                 "event_date": today, "end_date": None, "end_time": None}
        _, connection, _, notify = self._submit(group, {"1": 1}, "attended")
        connection.commit.assert_called_once()
        notify.assert_called_once()
        _, connection, _, notify = self._submit(group, {"1": 1}, "no_show")
        connection.commit.assert_not_called()
        notify.assert_not_called()

    def test_no_show_opens_at_end_time_or_next_day(self):
        day = date(2026, 12, 5)
        group = {"event_date": day, "end_date": None, "end_time": timedelta(hours=18), "status": "open"}
        self.assertEqual(_group_attendance_availability(group, datetime(2026, 12, 5, 17, 59)), (True, False))
        self.assertEqual(_group_attendance_availability(group, datetime(2026, 12, 5, 18)), (True, True))
        group["end_date"] = date(2026, 12, 7)
        self.assertEqual(_group_attendance_availability(group, datetime(2026, 12, 6, 20)), (True, False))
        self.assertEqual(_group_attendance_availability(group, datetime(2026, 12, 7, 18)), (True, True))
        group["end_time"] = None
        self.assertEqual(_group_attendance_availability(group, datetime(2026, 12, 7, 23, 59)), (True, False))
        self.assertEqual(_group_attendance_availability(group, datetime(2026, 12, 8, 0)), (True, True))
        group["status"] = "cancelled"
        self.assertEqual(_group_attendance_availability(group, datetime(2026, 12, 8, 0)), (False, False))

    def test_other_member_or_unfinished_group_cannot_mark_attendance(self):
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)
        for group in (
            {"host_user_id": 3, "title": "宜蘭行", "status": "open", "event_date": yesterday, "end_date": None},
            {"host_user_id": 2, "title": "宜蘭行", "status": "open", "event_date": tomorrow, "end_date": None},
            {"host_user_id": 2, "title": "宜蘭行", "status": "cancelled", "event_date": yesterday, "end_date": None},
        ):
            with self.subTest(group=group):
                _, connection, cursor, notify = self._submit(group, {"1": 1})
                self.assertFalse(any("INSERT INTO app_settings" in call.args[0]
                                     for call in cursor.execute.call_args_list))
                connection.commit.assert_not_called()
                notify.assert_not_called()

    def test_unapproved_member_cannot_be_marked(self):
        group = {"host_user_id": 2, "title": "宜蘭行", "status": "open",
                 "event_date": date.today() - timedelta(days=2), "end_date": None}
        _, connection, _, notify = self._submit(group, None)
        connection.commit.assert_not_called()
        notify.assert_not_called()

    def test_manage_page_shows_attended_on_departure_day_and_no_show_after_trip(self):
        today = date.today()
        group = {"group_id": 8, "title": "宜蘭行", "event_date": today,
                 "end_date": None, "location": "宜蘭", "trip_id": None, "status": "open"}
        member = {"user_id": 9, "nickname": "團員", "full_name": "團員", "status": "approved",
                  "application_note": None, "attendance_status": "attended"}
        with app.test_request_context("/member/friend-groups/groups/8/manage"):
            html = render_template("member/friend_groups/group_manage.html", group=group,
                                   members=[member], today=today,
                                   can_mark_attended=True, can_mark_no_show=False)
            self.assertIn("到場：有到", html)
            self.assertIn('value="attended"', html)
            self.assertNotIn('value="no_show"', html)
            ended_html = render_template("member/friend_groups/group_manage.html", group=group,
                                         members=[member], today=today,
                                         can_mark_attended=True, can_mark_no_show=True)
            self.assertIn('value="no_show"', ended_html)
            group["event_date"] = today + timedelta(days=1)
            future_html = render_template("member/friend_groups/group_manage.html", group=group,
                                          members=[member], today=today,
                                          can_mark_attended=False, can_mark_no_show=False)
            self.assertNotIn('value="attended"', future_html)


if __name__ == "__main__":
    unittest.main()
