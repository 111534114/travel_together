import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from flask import session

from app import app
from blueprints.friend_groups import group_detail, group_reviews, index


class CompletedFriendGroupTests(unittest.TestCase):
    def test_joined_completed_group_stays_in_companion_list(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [[], [{
            "group_id": 8, "title": "宜蘭一日遊", "event_date": date.today() - timedelta(days=2),
            "end_date": None, "city": "宜蘭縣", "location": "宜蘭", "nickname": "團長",
            "full_name": "團長",
        }]]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/"):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._feature_enabled", return_value=True), \
                 patch("blueprints.friend_groups._has_line_bound", return_value=False):
                html = index()
        self.assertIn("我參加過的揪團", html)
        self.assertIn("宜蘭一日遊", html)
        self.assertIn('/member/friend-groups/groups/8', html)
        query = cursor.execute.call_args_list[-1].args[0]
        self.assertIn("m.status='approved'", query)
        self.assertIn("COALESCE(g.end_date,g.event_date) < CURDATE()", query)

    def _detail(self, reviewed):
        group = {
            "group_id": 8, "host_user_id": 9, "title": "宜蘭一日遊",
            "nickname": "團長", "full_name": "團長", "status": "closed",
            "event_date": date.today() - timedelta(days=2), "end_date": None,
            "start_time": None, "location": "宜蘭", "capacity": 6,
            "description": None, "trip_id": None, "show_member_list": False,
            "meeting_info": None, "registration_lead_days": 2,
        }
        cursor = MagicMock()
        cursor.fetchone.side_effect = [group, {"status": "approved", "show_profile": False},
                                       {"1": 1} if reviewed else None]
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/8"):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._registration_deadline", return_value=date.today() - timedelta(days=4)), \
                 patch("blueprints.friend_groups._host_tier", return_value={"level": 1, "label": "新手團長", "avg_rating": None}):
                return group_detail(8)

    def test_unreviewed_member_gets_rating_dialog(self):
        html = self._detail(reviewed=False)
        self.assertIn('id="groupReviewDialog"', html)
        self.assertIn('name="reviewee_id" value="9"', html)
        self.assertIn('name="rating"', html)

    def test_reviewed_member_does_not_get_rating_dialog(self):
        html = self._detail(reviewed=True)
        self.assertNotIn('id="groupReviewDialog"', html)

    def test_group_itinerary_shows_linked_place_and_plain_stop(self):
        group = {
            "group_id": 8, "host_user_id": 7, "title": "宜蘭一日遊",
            "nickname": "團長", "full_name": "團長", "status": "open",
            "event_date": date.today() + timedelta(days=5), "end_date": None,
            "start_time": None, "location": "宜蘭", "capacity": 6,
            "description": None, "trip_id": 12, "show_member_list": False,
            "meeting_info": None, "registration_lead_days": 2,
        }
        place = {
            "itinerary_date": group["event_date"], "start_time": None, "end_time": None,
            "title": "景點甲", "address": "宜蘭市", "notes": None,
            "linked_attraction_id": 42, "linked_restaurant_id": None,
            "linked_accommodation_id": None, "place_image": "images/spot.jpg",
            "place_description": "適合散步的海岸。",
        }
        meeting = {**place, "title": "車站集合", "linked_attraction_id": None,
                   "place_image": None, "place_description": None}
        cursor = MagicMock()
        cursor.fetchone.side_effect = [group, None]
        cursor.fetchall.side_effect = [[], [meeting, place]]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with app.test_request_context("/member/friend-groups/groups/8"):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._registration_deadline", return_value=date.today() + timedelta(days=3)), \
                 patch("blueprints.friend_groups._host_tier", return_value={"level": 1, "label": "新手團長", "avg_rating": None}):
                html = group_detail(8)
        self.assertIn('images/spot.jpg', html)
        self.assertIn('member/attractions/42', html)
        self.assertIn('適合散步的海岸', html)
        self.assertIn('車站集合', html)

    def test_popup_review_returns_to_detail_after_saving(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"group_id": 8, "host_user_id": 9, "event_date": date.today() - timedelta(days=2),
             "end_date": None, "trip_id": None, "title": "宜蘭一日遊"},
            {"status": "approved"}, None,
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        form = {"reviewee_id": "9", "rating": "5", "return_to_detail": "1"}
        with app.test_request_context("/member/friend-groups/groups/8/reviews", method="POST", data=form):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._review_targets", return_value=[{"user_id": 9}]):
                response = group_reviews(8)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/member/friend-groups/groups/8"))
        connection.commit.assert_called_once()

    def test_regular_review_stays_on_review_page(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"group_id": 8, "host_user_id": 9, "event_date": date.today() - timedelta(days=2),
             "end_date": None, "trip_id": None, "title": "宜蘭一日遊"},
            {"status": "approved"}, None,
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        form = {"reviewee_id": "9", "rating": "5"}
        with app.test_request_context("/member/friend-groups/groups/8/reviews", method="POST", data=form):
            session.update(user_id=7, role="member")
            with patch("blueprints.friend_groups._connection_or_home", return_value=connection), \
                 patch("blueprints.friend_groups._review_targets", return_value=[{"user_id": 9}]):
                response = group_reviews(8)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/member/friend-groups/groups/8/reviews"))


if __name__ == "__main__":
    unittest.main()
