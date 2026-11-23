import unittest
from unittest.mock import patch

from app import app


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.queries = []
        self.lastrowid = 1

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.results.pop(0) if self.results else None

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConnection:
    def __init__(self, results):
        self.fake_cursor = FakeCursor(results)

    def cursor(self, dictionary=False):
        return self.fake_cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


TRIP = {"trip_id": 13, "city_id": 1, "country_id": 1, "member_role": "owner", "join_status": "accepted"}


class ItineraryPlacePickerTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "member"

    def post(self, results, **form):
        data = {"title": "我亂打的景點", "item_type": "attraction", "itinerary_date": "2026-12-01", "time_mode": "all_day"}
        data.update(form)
        connection = FakeConnection(results)
        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = self.client.post("/member/trips/13/itinerary", data=data)
        return response, connection.fake_cursor.queries

    def inserted(self, queries, table):
        return any(q.startswith(f"INSERT INTO {table}") for q, _ in queries)

    def test_unknown_attraction_name_is_rejected(self):
        response, queries = self.post([TRIP, None])  # 網站裡找不到這個名稱
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.inserted(queries, "itineraries"))

    def test_attraction_from_the_list_is_saved(self):
        response, queries = self.post([TRIP, {"id": 5, "name": "台北101"}, {"id": 5, "name": "台北101"}, {"next_order": 1}], title="台北101")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.inserted(queries, "itineraries"))

    def test_unknown_name_allowed_when_sent_for_review_with_address(self):
        with patch("blueprints.member.proposal_review.schedule_new_proposal"):
            response, queries = self.post([TRIP, {"next_order": 1}], submit_for_catalog="on", address="台北市信義區")
        self.assertTrue(self.inserted(queries, "itineraries"))
        self.assertTrue(self.inserted(queries, "proposals"))

    def test_personal_place_can_be_added_without_review(self):
        response, queries = self.post([TRIP, {"next_order": 1}], title="阿嬤家", custom_place="1")
        self.assertTrue(self.inserted(queries, "itineraries"))
        self.assertFalse(self.inserted(queries, "proposals"))  # 不會送去給管理員審核

    def test_review_without_address_is_rejected(self):
        response, queries = self.post([TRIP], submit_for_catalog="on", address=" ")
        self.assertFalse(self.inserted(queries, "itineraries"))

    def test_transport_items_can_use_any_name(self):
        response, queries = self.post([TRIP, {"next_order": 1}], title="搭高鐵", item_type="transport")
        self.assertTrue(self.inserted(queries, "itineraries"))


if __name__ == "__main__":
    unittest.main()
