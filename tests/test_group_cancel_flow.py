import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from flask import session

from app import app
from blueprints.friend_groups import _active_group_access, cancel_group, group_detail


class GroupCancelFlowTests(unittest.TestCase):
    def test_pending_applicant_can_view_closed_group_and_withdraw(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"group_id": 8, "host_user_id": 1, "status": "closed", "trip_id": None,
             "event_date": date(2099, 1, 5), "end_date": None, "show_member_list": 0,
             "title": "宜蘭行", "nickname": "團長", "full_name": "團長",
             "description": None, "location": "宜蘭", "capacity": 4},
            {"status": "pending", "show_profile": 0},
            None,
        ]
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/8"):
            session.update(user_id=2, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._host_tier", return_value={"level": 1, "label": "新手團長", "avg_rating": None}):
                html = group_detail(8)
        self.assertIn("撤回申請", html)
        self.assertIn("已關閉", html)
        self.assertNotIn("申請參加揪團", html)

    def test_cancellation_notifies_all_applicants_and_revokes_trip_access(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "host_user_id": 1, "title": "宜蘭行", "trip_id": 9, "status": "open",
        }
        cursor.fetchall.return_value = [
            {"user_id": 2, "status": "approved"},
            {"user_id": 3, "status": "pending"},
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/8/cancel", method="POST"):
            session.update(user_id=1, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups.send_notification") as notify:
                response = cancel_group(8)
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_called_once()
        queries = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("UPDATE trip_members SET join_status='removed'" in query for query in queries))
        self.assertTrue(any("SET status='rejected'" in query and "status='pending'" in query for query in queries))
        self.assertEqual([call.args[1] for call in notify.call_args_list], [2, 3])

    def test_cancelled_member_cannot_access_private_group_content(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"group_id": 8, "host_user_id": 1, "status": "cancelled", "trip_id": 9}
        self.assertIsNone(_active_group_access(cursor, 8, 2))
        self.assertEqual(cursor.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
