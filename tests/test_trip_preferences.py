import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from mysql.connector import Error
from werkzeug.datastructures import MultiDict

from app import app
import trip_preferences


def _row(user_id, **fields):
    row = {"user_id": user_id, "like_activities": None, "dislike_activities": None, "must_visit": None,
           "avoid_places": None, "budget_limit": None, "diet": "none", "transport_pref": "any",
           "walk_tolerance": "medium", "intensity": None, "special_needs": None}
    row.update(fields)
    return row


class TripPreferenceTests(unittest.TestCase):
    def test_parse_form_cleans_values(self):
        data, errors = trip_preferences.parse_form(MultiDict([
            ("like_activities", "在地美食"), ("like_activities", "不存在的活動"),
            ("must_visit", " 清水寺 \n\n清水寺\n嵐山"), ("budget_limit", "15000"),
            ("diet", "hacker"), ("intensity", "packed"),
        ]))
        self.assertEqual(errors, [])
        self.assertEqual(data["like_activities"], "在地美食")
        self.assertEqual(data["must_visit"], "清水寺\n嵐山")
        self.assertEqual(data["budget_limit"], Decimal("15000"))
        self.assertEqual(data["diet"], "none")
        self.assertEqual(data["intensity"], "packed")

    def test_parse_form_rejects_conflicts_and_bad_budget(self):
        _, errors = trip_preferences.parse_form(MultiDict([
            ("like_activities", "購物"), ("dislike_activities", "購物"), ("budget_limit", "-5"),
        ]))
        self.assertEqual(len(errors), 2)

    def test_missing_table_returns_none(self):
        cursor = MagicMock()
        cursor.execute.side_effect = Error(errno=1146)
        self.assertIsNone(trip_preferences.load_trip_preferences(cursor, 3))

    def test_form_prefills_from_questionnaire(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"like_activities": "購物,夜生活", "dislike_activities": None,
                                        "diet": "vegetarian", "transport_pref": "public", "walk_tolerance": "high"}
        values, source = trip_preferences.my_form_values(cursor, [], 5)
        self.assertEqual(source, "profile")
        self.assertEqual(values["like_activities"], ["購物", "夜生活"])
        self.assertEqual(values["diet"], "vegetarian")

    def test_form_uses_saved_trip_preference_first(self):
        cursor = MagicMock()
        values, source = trip_preferences.my_form_values(cursor, [_row(5, intensity="family")], 5)
        self.assertEqual(source, "trip")
        self.assertEqual(values["intensity"], "family")
        cursor.execute.assert_not_called()

    def test_summarize_counts_members(self):
        summary = trip_preferences.summarize([
            _row(1, like_activities="在地美食,購物", must_visit="清水寺", budget_limit=Decimal("10000"), intensity="standard"),
            _row(2, like_activities="在地美食", must_visit="清水寺\n嵐山", budget_limit=Decimal("20000"), intensity="standard"),
        ])
        self.assertEqual(summary["respondents"], 2)
        self.assertEqual(summary["activities"][0], ("在地美食", 2, 100))
        self.assertEqual(summary["average_budget"], Decimal("15000"))
        self.assertEqual(summary["must_visit"][0], ("清水寺", 2))
        self.assertIn(("標準型", 2, 100), summary["intensity"])

    def test_summarize_empty(self):
        summary = trip_preferences.summarize(None)
        self.assertEqual(summary["respondents"], 0)
        self.assertIsNone(summary["average_budget"])

    def test_trip_detail_template_compiles(self):
        self.assertIsNotNone(app.jinja_env.get_template("member/trip_detail.html"))


if __name__ == "__main__":
    unittest.main()
