import unittest
from datetime import date
from unittest.mock import patch

import currency_rates
from group_ai_planner import normalize_plan

RATES = {"TWD": 1.0, "JPY": 5.0, "USD": 0.03}


class CurrencyCostTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(currency_rates, "rates", return_value=RATES)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_convert_between_currencies(self):
        self.assertEqual(currency_rates.convert(5000, "JPY"), 1000)
        self.assertAlmostEqual(currency_rates.convert(1000, "TWD", "USD"), 30)
        self.assertIsNone(currency_rates.convert(100, "XYZ"))

    def test_plan_costs_are_converted_to_twd(self):
        payload = {"items": [
            {"date": "2026-12-01", "type": "attraction", "title": "晴空塔", "estimated_cost": 6000, "cost_currency": "JPY"},
            {"date": "2026-12-01", "type": "attraction", "title": "淺草寺", "estimated_cost": 0, "cost_currency": "JPY"},
            {"date": "2026-12-01", "type": "restaurant", "title": "老店", "estimated_cost": 800},
            {"date": "2026-12-01", "type": "other", "title": "怪幣別", "estimated_cost": 99, "cost_currency": "XYZ"},
        ]}
        items = normalize_plan(payload, date(2026, 12, 1), date(2026, 12, 3))["items"]
        self.assertEqual([item["estimated_cost"] for item in items], [1200, 0, 800, 0])


if __name__ == "__main__":
    unittest.main()
