import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from flask import render_template, session

from app import app
from blueprints.friend_groups import confirm_group_formation


class GroupFormationTests(unittest.TestCase):
    def test_manage_page_opens_formation_controls_only_after_deadline(self):
        group = {
            "group_id": 8, "trip_id": 9, "title": "宜蘭行", "status": "open",
            "event_date": date.today() + timedelta(days=1), "location": "宜蘭",
            "formation_status": None,
        }
        with app.test_request_context("/member/friend-groups/groups/8/manage"):
            context = dict(group=group, members=[], today=date.today(),
                           can_mark_attended=False, can_mark_no_show=False,
                           approved_count=1, pending_count=0)
            before = render_template("member/friend_groups/group_manage.html",
                                     registration_deadline=date.today(), **context)
            after = render_template("member/friend_groups/group_manage.html",
                                    registration_deadline=date.today() - timedelta(days=1), **context)
        self.assertNotIn('name="decision" value="formed"', before)
        self.assertIn('name="decision" value="formed"', after)
        self.assertIn('name="decision" value="not_formed"', after)

    def _run(self, decision, deadline, counts, members=None):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"host_user_id": 1, "title": "宜蘭行", "trip_id": 9,
             "status": "open", "event_date": date.today() + timedelta(days=1)},
            None,  # No existing formation decision.
        ]
        cursor.fetchall.side_effect = [counts, members or []]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/8/formation", method="POST", data={"decision": decision}):
            session.update(user_id=1, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._registration_deadline", return_value=deadline), \
                 patch("blueprints.friend_groups.send_notification") as notify:
                response = confirm_group_formation(8)
        return response, cursor, connection, notify

    def test_cannot_confirm_before_registration_deadline(self):
        response, cursor, connection, notify = self._run(
            "formed", date.today(), [{"status": "approved", "total": 1}]
        )
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_not_called()
        notify.assert_not_called()
        self.assertFalse(any("UPDATE friend_groups" in call.args[0] for call in cursor.execute.call_args_list))

    def test_host_must_review_pending_applications_before_confirming(self):
        response, cursor, connection, notify = self._run(
            "formed", date.today() - timedelta(days=1),
            [{"status": "approved", "total": 1}, {"status": "pending", "total": 1}],
        )
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_not_called()
        notify.assert_not_called()

    def test_repeated_confirmation_does_not_send_duplicate_notifications(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"host_user_id": 1, "title": "宜蘭行", "trip_id": 9,
             "status": "closed", "event_date": date.today() + timedelta(days=1)},
            {"setting_value": "formed"},
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/8/formation", method="POST", data={"decision": "formed"}):
            session.update(user_id=1, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._registration_deadline", return_value=date.today() - timedelta(days=1)), \
                 patch("blueprints.friend_groups.send_notification") as notify:
                response = confirm_group_formation(8)
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_not_called()
        notify.assert_not_called()

    def test_confirmed_group_closes_registration_and_notifies_members(self):
        response, cursor, connection, notify = self._run(
            "formed", date.today() - timedelta(days=1),
            [{"status": "approved", "total": 1}], [{"user_id": 2}],
        )
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_called_once()
        queries = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("SET status='closed'" in query for query in queries))
        self.assertTrue(any("INSERT INTO app_settings" in query for query in queries))
        self.assertEqual(notify.call_args.args[1], 2)
        self.assertEqual(notify.call_args.args[4], "揪團已成團")

    def test_not_formed_revokes_access_and_notifies_pending_and_approved(self):
        response, cursor, connection, notify = self._run(
            "not_formed", date.today() - timedelta(days=1),
            [{"status": "approved", "total": 1}, {"status": "pending", "total": 1}],
            [{"user_id": 2, "status": "approved"}, {"user_id": 3, "status": "pending"}],
        )
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_called_once()
        queries = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("SET status='cancelled'" in query for query in queries))
        self.assertTrue(any("UPDATE trip_members SET join_status='removed'" in query for query in queries))
        self.assertEqual([call.args[1] for call in notify.call_args_list], [2, 3])
        self.assertTrue(all(call.args[4] == "揪團未成團" for call in notify.call_args_list))


if __name__ == "__main__":
    unittest.main()
