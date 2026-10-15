import unittest
from datetime import date, time
from unittest.mock import patch

from flask import session

import app as app_module
import line_commands
import trip_reminders
from booking_search import filter_prices, validate_search
from content_admin_permissions import content_admin_can


class October12FeatureTests(unittest.TestCase):
    def test_flight_stops_filter_and_validation(self):
        self.assertIn("stops", validate_search("flight", {
            "from": "台北", "to": "東京", "depart": "2099-01-01",
            "trip_mode": "oneway", "pax": "1", "stops": "invalid",
        }))
        rows = [
            {"price": 9000, "duration": 180, "stops": 0},
            {"price": 7000, "duration": 360, "stops": 1},
        ]
        with app_module.app.test_request_context("/?stops=direct"):
            self.assertEqual([rows[0]], filter_prices(rows, "price", "duration", "stops"))
        with app_module.app.test_request_context("/?stops=connecting"):
            self.assertEqual([rows[1]], filter_prices(rows, "price", "duration", "stops"))

    def test_content_admin_action_permission(self):
        with app_module.app.test_request_context("/"):
            session["role"] = "content_admin"
            with patch("content_admin_permissions.denied_modules", return_value={"attractions:delete"}):
                self.assertTrue(content_admin_can("attractions", "view"))
                self.assertFalse(content_admin_can("attractions", "delete"))

    def test_line_commands_and_reminder_message(self):
        self.assertEqual(line_commands.HELP, line_commands.normalize("help"))
        self.assertIsNone(line_commands.normalize("真人客服問題"))
        message = trip_reminders.build_message({
            "trip_id": 5, "trip_name": "東京", "start_date": date(2099, 1, 2),
            "end_date": date(2099, 1, 5), "country": "日本", "city": "東京",
        }, [{"title": "淺草寺", "start_time": time(9, 0), "is_all_day": False}])
        self.assertIn("明天就要出發", message)
        self.assertIn("09:00 淺草寺", message)


if __name__ == "__main__":
    unittest.main()
