import unittest
from unittest.mock import MagicMock, patch

from app import app
import flight_links
import tdx_trains


class November4MergeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_region_search_combines_airports_without_duplicates(self):
        airports_by_city = {
            "Sapporo": [{"iata": "CTS", "name": "New Chitose", "city": "Sapporo", "country": "Japan"}],
            "Hakodate": [{"iata": "HKD", "name": "Hakodate", "city": "Hakodate", "country": "Japan"}],
            "Asahikawa": [{"iata": "CTS", "name": "New Chitose", "city": "Sapporo", "country": "Japan"}],
        }
        with patch("app.airports.get_city_airports", side_effect=lambda city, country: airports_by_city.get(city, [])):
            response = self.client.get("/api/city-search?q=北海道")
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        self.assertEqual([row["iata"] for row in rows], ["CTS", "HKD"])
        self.assertTrue(all(row["region"] == "北海道" for row in rows))

    def test_region_selection_expands_to_all_city_codes(self):
        codes = {"Sapporo": "CTS", "Hakodate": "HKD"}
        with patch("flight_links.airports.get_city_airport_codes", side_effect=lambda city, country: codes.get(city)):
            self.assertEqual(flight_links.to_iata("北海道（所有機場）"), "CTS,HKD")

    def test_station_search_has_local_high_speed_fallback(self):
        with patch("tdx_trains.is_configured", return_value=False):
            response = self.client.get("/api/station-search?q=台北")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["name"], "台北")

    def test_hotel_suggestions_use_active_taiwan_accommodations(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchall.return_value = [
            {"name": "台北旅店", "address": "台北市信義區松仁路 1 號"},
        ]
        with patch("app.get_db_connection", return_value=connection):
            response = self.client.get("/api/hotel-place-search?q=台北")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["value"], "台北市 信義區")
        query = connection.cursor.return_value.execute.call_args.args[0]
        self.assertIn("ac.status = 'active'", query)
        self.assertIn("ac.deleted_at IS NULL", query)

    def test_high_speed_timetable_redirect_uses_official_search(self):
        response = MagicMock()
        response.json.return_value = {"success": True, "cipherText": "ab+/="}
        with patch.object(tdx_trains, "_thsr_url_cache", {}), patch("tdx_trains.requests.post", return_value=response) as post:
            result = tdx_trains.thsr_timetable_url("1000", "1040", "2026-12-01", "09:30")
        self.assertIn("search=ab%2B%2F%3D", result)
        self.assertEqual(post.call_args.args[0], tdx_trains.THSR_ENCRYPT_URL)


if __name__ == "__main__":
    unittest.main()
