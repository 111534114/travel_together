import unittest
from decimal import Decimal
from unittest.mock import patch

from app import _live_flight_search, app
from blueprints.member import _load_trip_preferences
from flight_links import skyscanner_search_url


class TripPreferenceCursor:
    def __init__(self, rows=None, table_exists=True):
        self.rows = rows or []
        self.table_exists = table_exists
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return ("trip_preferences",) if self.table_exists else None

    def fetchall(self):
        return self.rows


class October29MergeTests(unittest.TestCase):
    def test_missing_preference_table_keeps_trip_page_available(self):
        cursor = TripPreferenceCursor(table_exists=False)
        result = _load_trip_preferences(cursor, 7, 3)
        self.assertFalse(result["available"])
        self.assertEqual(result["submitted_count"], 0)
        self.assertEqual(len(cursor.queries), 1)

    def test_preference_summary_uses_saved_rows(self):
        cursor = TripPreferenceCursor(rows=[
            {"user_id": 3, "like_activities": "在地美食,觀光景點", "intensity": "relaxed",
             "budget_limit": Decimal("1000"), "must_visit": "台北101", "avoid_places": None},
            {"user_id": 4, "like_activities": "在地美食", "intensity": "standard",
             "budget_limit": Decimal("2000"), "must_visit": None, "avoid_places": "夜市"},
        ])
        result = _load_trip_preferences(cursor, 7, 3)
        self.assertTrue(result["available"])
        self.assertEqual(result["submitted_count"], 2)
        self.assertEqual(result["avg_budget"], Decimal("1500"))
        self.assertEqual(result["must_visit_items"], ["台北101"])
        self.assertEqual(result["avoid_items"], ["夜市"])

    @patch("app.amadeus_client.search_flight_offers", return_value=[{"price": 100}])
    @patch("app.serpapi_flights.search_flight_offers", return_value=[])
    def test_empty_primary_flight_results_try_fallback(self, _serpapi, amadeus):
        rows, is_live = _live_flight_search("台北", "東京", "2026-11-10")
        self.assertTrue(is_live)
        self.assertEqual(rows[0]["price"], 100)
        amadeus.assert_called_once()

    def test_skyscanner_link_uses_airport_codes(self):
        url = skyscanner_search_url("台北", "東京", "2026-11-10", pax=2)
        self.assertIn("/tpe/nrt/261110/", url)
        self.assertIn("adultsv2=2", url)

    @patch("app._search_flights", return_value=[])
    @patch("app._live_flight_search", return_value=(None, False))
    def test_flight_result_templates_render_without_live_api(self, _live, _local):
        client = app.test_client()
        response = client.get("/visitor/flights?from=台北&to=東京&depart=2026-11-10&trip_mode=oneway")
        self.assertEqual(response.status_code, 200)
        self.assertIn("機票搜尋結果".encode(), response.data)
        response = client.get("/visitor/flights/multi-city?from1=台北&to1=東京&date1=2026-11-10")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
