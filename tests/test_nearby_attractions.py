import unittest
from datetime import date
from unittest.mock import Mock, patch

from app import app
from nearby_attractions import find_nearby_attractions


class NearbyAttractionTests(unittest.TestCase):
    def test_uses_real_distance_and_excludes_already_added_sites(self):
        source = dict(attraction_id=1, country_id=1, latitude=25.033, longitude=121.565)
        near = dict(attraction_id=2, name="附近景點", latitude=25.036, longitude=121.565)
        far = dict(attraction_id=3, name="較遠景點", latitude=25.075, longitude=121.610)
        cursor = Mock()
        cursor.fetchall.return_value = [far, near]

        result = find_nearby_attractions(cursor, source, 7, date(2026, 10, 27))

        self.assertEqual([item["name"] for item in result], ["附近景點"])
        self.assertIn("公尺", result[0]["distance_label"])
        sql, params = cursor.execute.call_args.args
        self.assertIn("a.status = 'active'", sql)
        self.assertIn("a.deleted_at IS NULL", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertEqual(params[-2:], (7, date(2026, 10, 27)))

    def test_missing_coordinates_does_not_guess_by_city(self):
        cursor = Mock()
        result = find_nearby_attractions(
            cursor, dict(attraction_id=1, country_id=1, latitude=None, longitude=None),
            7, date(2026, 10, 27),
        )
        self.assertEqual(result, [])
        cursor.execute.assert_not_called()

    def test_successful_add_returns_to_detail_with_recommendations(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [
            dict(name="台北101", address="台北市", ticket_price=0),
            dict(next_order=2),
        ]
        cursor.lastrowid = 42
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection), \
             patch("blueprints.member._member_access", return_value=dict(
                 trip_id=7, trip_name="台北", start_date=date(2026, 10, 27),
                 end_date=date(2026, 10, 28), member_role="owner",
             )):
            response = client.post("/member/attractions/1/add-to-trip", data={
                "next": "/member/attractions/1", "trip_id": "7",
                "itinerary_date": "2026-10-27", "time_mode": "all_day",
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/member/attractions/1?added_to=42#nearby")
        connection.commit.assert_called_once()

    def test_recommendations_only_show_for_own_editable_trip(self):
        attraction = dict(
            attraction_id=1, country_id=1, city_id=1, name="台北101", country="台灣",
            city="台北市", category_name="景點", image_path=None, is_favorited=False,
            ticket_price=0, opening_hours=None, suggested_duration_minutes=None,
            address=None, latitude=25.033, longitude=121.565, description=None,
            website_url=None,
        )
        cursor = Mock()
        cursor.fetchone.side_effect = [attraction, None]
        cursor.fetchall.return_value = []
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection), \
             patch("blueprints.member._addable_trips", return_value=[]), \
             patch.dict(app.jinja_env.globals, {"friend_group_feature_enabled": lambda: False}):
            response = client.get("/member/attractions/1?added_to=999")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("附近景點推薦", response.get_data(as_text=True))

    def test_authorized_detail_shows_nearby_place_on_same_day(self):
        attraction = dict(
            attraction_id=1, country_id=1, city_id=1, name="台北101", country="台灣",
            city="台北市", category_name="景點", image_path=None, is_favorited=False,
            ticket_price=0, opening_hours=None, suggested_duration_minutes=None,
            address=None, latitude=25.033, longitude=121.565, description=None,
            website_url=None,
        )
        trip = dict(trip_id=7, itinerary_date=date(2026, 10, 27), trip_name="台北")
        nearby = dict(
            attraction_id=2, name="附近景點", address="信義區", image_path=None,
            latitude=25.036, longitude=121.565, city="台北市",
        )
        cursor = Mock()
        cursor.fetchone.side_effect = [attraction, trip]
        cursor.fetchall.side_effect = [[nearby], []]
        connection = Mock()
        connection.cursor.return_value = cursor
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="member")
        with patch("blueprints.member.get_db_connection", return_value=connection), \
             patch("blueprints.member._addable_trips", return_value=[]), \
             patch.dict(app.jinja_env.globals, {"friend_group_feature_enabled": lambda: False}):
            response = client.get("/member/attractions/1?added_to=42")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("附近景點推薦", html)
        self.assertIn("附近景點", html)
        self.assertIn('name="trip_id" value="7"', html)
        self.assertIn('name="itinerary_date" value="2026-10-27"', html)
        self.assertIn("＋加入同一天", html)


if __name__ == "__main__":
    unittest.main()
