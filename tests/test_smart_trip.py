import unittest
from datetime import date, time
from unittest.mock import patch

import smart_trip
from ai_client import AIUnavailable, _parse_json


def stop(item_id, lat, lng, item_type="attraction", **extra):
    return {"itinerary_id": item_id, "item_type": item_type, "title": f"站點{item_id}", "lat": lat, "lng": lng, **extra}


class EstimateLegTests(unittest.TestCase):
    def test_short_distance_is_walking_and_free(self):
        leg = smart_trip.estimate_leg(0.5)
        self.assertEqual(leg["method"], "步行")
        self.assertEqual(leg["cost"], 0)
        self.assertIn("公尺", leg["distance_label"])

    def test_city_distance_uses_public_transport(self):
        leg = smart_trip.estimate_leg(5)
        self.assertTrue(leg["method"].startswith("大眾運輸"))
        self.assertGreater(leg["minutes"], 10)

    def test_long_distance_uses_rail(self):
        self.assertTrue(smart_trip.estimate_leg(300)["method"].startswith("長途交通"))


class PlanDayRouteTests(unittest.TestCase):
    def test_orders_stops_by_nearest_neighbour_without_backtracking(self):
        # 四個站點在同一條南北線上，但原本順序是來回跳
        items = [stop(1, 25.00, 121.5), stop(2, 25.30, 121.5), stop(3, 25.10, 121.5), stop(4, 25.20, 121.5)]
        ordered = smart_trip.plan_day_route(items)
        self.assertEqual([it["itinerary_id"] for it in ordered], [1, 3, 4, 2])

    def test_lodging_check_in_goes_last_and_unlocated_stops_are_kept(self):
        items = [stop(1, 25.0, 121.5), stop(2, None, None, title="手動輸入"),
                 stop(3, 25.05, 121.5, item_type="accommodation"), stop(4, 25.01, 121.5)]
        ordered = [it["itinerary_id"] for it in smart_trip.plan_day_route(items)]
        self.assertEqual(ordered[-1], 3)
        self.assertEqual(sorted(ordered), [1, 2, 3, 4])

    def test_restaurant_is_placed_near_lunch_time(self):
        items = [stop(1, 25.00, 121.5, duration=120), stop(2, 25.01, 121.5, duration=120),
                 stop(3, 25.02, 121.5, duration=120), stop(9, 25.015, 121.5, item_type="restaurant")]
        ordered = [it["itinerary_id"] for it in smart_trip.plan_day_route(items)]
        # 9:00 開始，每站 2 小時，午餐應該排在第一、二站之後，而不是一早或最後
        self.assertIn(ordered.index(9), (1, 2))


class ScheduleTests(unittest.TestCase):
    def test_does_not_start_before_opening_or_original_time(self):
        items = [dict(stop(1, 25.0, 121.5), coords=(25.0, 121.5)),
                 dict(stop(2, 25.01, 121.5, opening_hours="17:00-24:00"), coords=(25.01, 121.5)),
                 dict(stop(3, 25.02, 121.5, start_time=time(21, 0)), coords=(25.02, 121.5))]
        rows = smart_trip.schedule(items)
        self.assertEqual(rows[0]["start_minutes"], 9 * 60)
        self.assertEqual(rows[1]["start_minutes"], 17 * 60)
        self.assertEqual(rows[2]["start_minutes"], 21 * 60)
        self.assertIsNone(rows[0]["leg"])
        self.assertIsNotNone(rows[1]["leg"])

    def test_opening_minutes_reads_first_time(self):
        self.assertEqual(smart_trip.opening_minutes("週一至週日 09:30–17:00"), 9 * 60 + 30)
        self.assertIsNone(smart_trip.opening_minutes("全天開放"))


class SmartScheduleDayTests(unittest.TestCase):
    items = [stop(1, 25.0, 121.5), stop(2, 25.3, 121.5), stop(3, 25.1, 121.5)]

    def test_rule_result_when_ai_is_not_configured(self):
        with patch.object(smart_trip, "ai_ready", return_value=False):
            result = smart_trip.smart_schedule_day(self.items, date(2026, 12, 1), "台北")
        self.assertEqual(result["source"], "rule")
        self.assertTrue(result["changed"])
        self.assertEqual([r["itinerary_id"] for r in result["items"]], [1, 3, 2])

    def test_falls_back_to_rules_when_ai_fails(self):
        with patch.object(smart_trip, "ai_ready", return_value=True), \
             patch.object(smart_trip, "ask_json", side_effect=AIUnavailable("逾時")):
            result = smart_trip.smart_schedule_day(self.items, date(2026, 12, 1), "台北")
        self.assertEqual(result["source"], "rule")
        self.assertIn("逾時", result["note"])

    def test_ai_order_must_contain_every_stop(self):
        with patch.object(smart_trip, "ai_ready", return_value=True), \
             patch.object(smart_trip, "ask_json", return_value={"order": [1, 2]}):
            result = smart_trip.smart_schedule_day(self.items, date(2026, 12, 1), "台北")
        self.assertEqual(result["source"], "rule")

    def test_uses_valid_ai_order_and_times(self):
        payload = {"order": [2, 3, 1], "start_times": {"2": "10:00", "3": "13:00", "1": "16:00"},
                   "reason": "由北往南", "tips": ["早點出門"]}
        with patch.object(smart_trip, "ai_ready", return_value=True), \
             patch.object(smart_trip, "ask_json", return_value=payload):
            result = smart_trip.smart_schedule_day(self.items, date(2026, 12, 1), "台北")
        self.assertEqual(result["source"], "ai")
        self.assertEqual([r["itinerary_id"] for r in result["items"]], [2, 3, 1])
        self.assertEqual(result["items"][0]["start_time"], "10:00")
        self.assertEqual(result["reason"], "由北往南")


class EstimateBudgetTests(unittest.TestCase):
    def test_adds_tickets_meals_lodging_and_reference_prices(self):
        itinerary = [
            {"item_type": "attraction", "ticket_price": 300, "itinerary_date": date(2026, 12, 1), "lat": 25.0, "lng": 121.5},
            {"item_type": "restaurant", "price_level": "medium", "itinerary_date": date(2026, 12, 1), "lat": 25.05, "lng": 121.5},
            {"item_type": "attraction", "estimated_cost": 1000, "itinerary_date": date(2026, 12, 2)},
        ]
        budget = smart_trip.estimate_budget(itinerary, people=3, nights=2, lodging_prices=[2000, None], tier="budget")
        lines = {line["key"]: line["amount"] for line in budget["lines"]}
        self.assertEqual(lines["tickets"], 300 * 3 + 1000)
        self.assertEqual(lines["lodging"], (2000 + 1800) * 2)  # 3 人 → 2 間房
        self.assertGreater(lines["meals"], 500 * 3)  # 已排的一餐 + 尚未安排餐廳的估算
        self.assertGreater(lines["transport"], 0)
        self.assertEqual(budget["total"], sum(lines.values()))
        self.assertEqual(budget["rooms"], 2)
        self.assertTrue(any("1 晚沒有房價" in note for note in budget["notes"]))


class ParseJsonTests(unittest.TestCase):
    def test_accepts_code_fence_and_list_wrapper(self):
        self.assertEqual(_parse_json('```json\n[{"a": 1}]\n```'), {"a": 1})

    def test_rejects_non_json(self):
        with self.assertRaises(AIUnavailable):
            _parse_json("抱歉，我無法處理")


if __name__ == "__main__":
    unittest.main()
