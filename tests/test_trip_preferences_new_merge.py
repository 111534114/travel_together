import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from mysql.connector import Error
from werkzeug.datastructures import MultiDict

import trip_preferences


def row(user_id, **fields):
    result = dict(user_id=user_id, like_activities=None, dislike_activities=None,
                  must_visit=None, avoid_places=None, budget_limit=None, intensity=None)
    result.update(fields)
    return result


class TripPreferenceMergeTests(unittest.TestCase):
    def test_form_validation_and_cleaning(self):
        data, errors = trip_preferences.parse_form(MultiDict([
            ("like_activities", "在地美食"), ("like_activities", "不存在"),
            ("must_visit", " 清水寺 \n清水寺\n嵐山"), ("budget_limit", "15000"),
            ("diet", "invalid"),
        ]))
        self.assertEqual(errors, [])
        self.assertEqual(data["must_visit"], "清水寺\n嵐山")
        self.assertEqual(data["budget_limit"], Decimal("15000"))
        self.assertEqual(data["diet"], "none")

    def test_form_rejects_conflict_and_negative_budget(self):
        _, errors = trip_preferences.parse_form(MultiDict([
            ("like_activities", "購物"), ("dislike_activities", "購物"), ("budget_limit", "-5")]))
        self.assertEqual(len(errors), 2)

    def test_missing_table_does_not_break_page(self):
        cursor = MagicMock()
        cursor.execute.side_effect = Error(errno=1146)
        self.assertIsNone(trip_preferences.load_trip_preferences(cursor, 3))

    def test_uses_existing_trip_preferences_table(self):
        cursor = MagicMock()
        trip_preferences.load_trip_preferences(cursor, 3)
        self.assertIn("FROM trip_preferences", cursor.execute.call_args.args[0])

    def test_profile_prefill_when_no_trip_entry(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"like_activities": "購物,夜生活", "diet": "vegetarian"}
        values, source = trip_preferences.my_form_values(cursor, [], 5)
        self.assertEqual(source, "profile")
        self.assertEqual(values["like_activities"], ["購物", "夜生活"])

    def test_summary_counts_accepted_entries(self):
        summary = trip_preferences.summarize([
            row(1, like_activities="在地美食,購物", must_visit="清水寺", budget_limit=Decimal("10000"), intensity="standard"),
            row(2, like_activities="在地美食", must_visit="清水寺\n嵐山", budget_limit=Decimal("20000"), intensity="standard"),
        ])
        self.assertEqual(summary["activities"][0], ("在地美食", 2, 100))
        self.assertEqual(summary["average_budget"], Decimal("15000"))
        self.assertEqual(summary["must_visit"][0], ("清水寺", 2))
