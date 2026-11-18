import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from flask import session

from app import app
from blueprints.friend_groups import _host_tier, group_reviews, new_group
from blueprints.friend_groups_admin import international_hosts, set_international_host
from content_admin_permissions import _ENDPOINT_ACTIONS


class GroupInternationalTests(unittest.TestCase):
    def test_rating_and_trip_count_do_not_grant_international_host(self):
        for approval, expected in [(None, 1), ({"setting_value": "1"}, 2)]:
            with self.subTest(approval=approval):
                cursor = MagicMock()
                cursor.fetchone.side_effect = [
                    {"c": 8}, {"avg_rating": 5, "review_count": 6}, approval,
                ]
                tier = _host_tier(cursor, 7)
                self.assertEqual(tier["level"], expected)
                self.assertEqual(tier["can_host_international"], expected == 2)

    def test_unapproved_member_cannot_submit_overseas_group(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "trip_id": 8, "trip_name": "東京行", "start_date": date(2099, 1, 5),
            "end_date": date(2099, 1, 5), "country_id": 9, "city_id": 10,
        }
        connection = MagicMock()
        connection.cursor.return_value = cursor
        tier = {"level": 1, "allow_multi_day": False, "can_host_international": False,
                "max_capacity": 6}
        form = {"existing_trip_id": "8", "title": "東京行", "event_date": "2099-01-05",
                "registration_lead_days": "2"}
        with app.test_request_context("/member/friend-groups/groups/new", method="POST", data=form):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._can_use_groups", return_value=True), \
                 patch("blueprints.friend_groups._has_completed_onboarding", return_value=True), \
                 patch("blueprints.friend_groups._host_tier", return_value=tier), \
                 patch("blueprints.friend_groups.get_countries", return_value=[]), \
                 patch("blueprints.friend_groups.get_cities", return_value=[]), \
                 patch("blueprints.friend_groups._city_matches_country", return_value=True), \
                 patch("blueprints.friend_groups._is_domestic_country", return_value=False):
                response = new_group()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(any("INSERT INTO friend_groups" in call.args[0]
                             for call in cursor.execute.call_args_list))
        connection.commit.assert_not_called()

    def test_system_admin_can_approve_qualified_host(self):
        cursor = MagicMock()
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/content-admin/friend-groups/international-hosts/7",
                                      method="POST", data={"approved": "1"}):
            session.update(user_id=2, role="system_admin")
            with patch("blueprints.friend_groups_admin.get_db_connection", return_value=connection), \
                 patch("blueprints.friend_groups_admin._has_attended_event", return_value=True), \
                 patch("blueprints.friend_groups_admin._international_candidate_reviews", return_value=[{"group_id": 8}]), \
                 patch("blueprints.friend_groups_admin.send_notification"), \
                 patch("blueprints.friend_groups_admin.log_action"):
                response = set_international_host(7)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(call.args[1] == ("friend_group_international_7", "1", 2)
                            for call in cursor.execute.call_args_list))
        connection.commit.assert_called_once()

    def test_system_admin_can_open_review_page(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/content-admin/friend-groups/international-hosts"):
            session.update(user_id=2, role="system_admin")
            with patch("blueprints.friend_groups_admin.get_db_connection", return_value=connection), \
                 patch("blueprints.friend_groups_admin._international_candidate_reviews", return_value=[]):
                html = international_hosts()
        self.assertIn("國際揪團資格審核", html)
        self.assertIn("目前沒有完成國內揪團", html)

    def test_first_written_domestic_review_notifies_admin(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"group_id": 8, "host_user_id": 9, "trip_id": 4, "title": "宜蘭行",
             "event_date": date(2020, 1, 1), "end_date": date(2020, 1, 1)},
            {"status": "approved"}, None, {"country_id": 1},
        ]
        cursor.fetchall.return_value = [{"user_id": 2}]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        form = {"reviewee_id": "9", "rating": "5", "comment": "行程安排很周到"}
        with app.test_request_context("/member/friend-groups/groups/8/reviews", method="POST", data=form):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._review_targets", return_value=[{"user_id": 9}]), \
                 patch("blueprints.friend_groups._is_domestic_country", return_value=True), \
                 patch("blueprints.friend_groups.send_notification") as notify:
                response = group_reviews(8)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(notify.call_count, 1)
        self.assertEqual(notify.call_args.args[1], 2)
        connection.commit.assert_called_once()

    def test_content_admin_approval_requires_edit_permission(self):
        self.assertEqual(_ENDPOINT_ACTIONS["friend_groups_admin"]["set_international_host"], "edit")


if __name__ == "__main__":
    unittest.main()
