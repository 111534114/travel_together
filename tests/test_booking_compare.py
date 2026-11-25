import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import booking_compare as bc
from app import app

TRIP = {"trip_id": 48, "start_date": date(2026, 12, 1), "end_date": date(2026, 12, 3), "city": "東京都", "country": "日本",
        "total_budget": Decimal("30000"), "currency": "TWD", "member_role": "owner", "join_status": "accepted", "people_count": 2}


def tools_with_results(people=2, trip=TRIP):
    tools = bc.CompareTools(trip, "台北", people)
    tools.flights = {"F1": {"price": Decimal("12000"), "airline_name": "長榮航空", "flight_number": "BR198",
                            "departure_time": "08:50", "arrival_time": "13:05", "stops": 0}}
    tools.flight_query = ("台北", "東京", "2026-12-01", "2026-12-03")
    tools.hotels = {"H1": {"name": "東京飯店", "price": Decimal("3000"), "total_price": Decimal("6200"), "rating": 4.3,
                           "star": 3, "website_url": "https://hotel.example", "detail": {"address": "東京都台東區"}}}
    tools.trains = {"T1": {"price": Decimal("700"), "train_type": "thsr", "train_number": "0803", "car_class": "標準車廂",
                           "origin_station": "台北", "destination_station": "台中", "departure_time": "06:26",
                           "arrival_time": "07:30", "direction": "go", "date": "2026-12-01", "rail": "thsr", "booking_url": "https://thsr"}}
    return tools


class BuildOptionsTests(unittest.TestCase):
    def test_server_computes_prices(self):
        options, rejected = bc.build_options(tools_with_results(), TRIP,
                                             [{"kind": "cheapest", "transport_ids": ["F1"], "hotel_id": "H1", "reason": "便宜"}])
        option = options[0]
        flight, hotel = option["lines"]
        self.assertEqual(flight["price"], 24000)  # 每人 12,000 × 2 人
        self.assertEqual(hotel["price"], 6200)  # 1 間房：用 Google 給的整趟住宿總價
        self.assertEqual(option["total"], 30200)
        self.assertEqual(option["over_budget"], 200)
        self.assertTrue(option["estimated"])  # 機票是估計價
        self.assertEqual(rejected, [])

    def test_more_people_needs_more_rooms(self):
        options, _ = bc.build_options(tools_with_results(people=3), TRIP, [{"kind": "balanced", "hotel_id": "H1"}])
        hotel = options[0]["lines"][0]
        self.assertEqual(hotel["price"], 3000 * 2 * 2)  # 每晚 × 2 晚 × 2 間房(3 人)
        self.assertIn("2 間", hotel["price_note"])

    def test_made_up_result_ids_are_rejected(self):
        # AI 自己編了一個 F9，伺服器查不到 → 整個方案拿掉，不會出現假價錢
        options, rejected = bc.build_options(tools_with_results(), TRIP, [{"kind": "comfort", "transport_ids": ["F9"], "hotel_id": "H1"}])
        self.assertEqual(options, [])
        self.assertTrue(rejected)

    def test_train_price_and_label(self):
        options, _ = bc.build_options(tools_with_results(), dict(TRIP, country="台灣"), [{"kind": "cheapest", "transport_ids": ["T1"]}])
        line = options[0]["lines"][0]
        self.assertEqual(line["price"], 1400)
        self.assertIn("高鐵", line["title"])
        self.assertIn("標準車廂", line["title"])

    def test_duplicate_kind_only_once_and_no_budget(self):
        options, _ = bc.build_options(tools_with_results(), dict(TRIP, total_budget=0),
                                      [{"kind": "cheapest", "hotel_id": "H1"}, {"kind": "cheapest", "hotel_id": "H1"}])
        self.assertEqual(len(options), 1)
        self.assertIsNone(options[0]["budget"])


class SearchLimitTests(unittest.TestCase):
    def test_at_most_three_paid_searches(self):
        tools = bc.CompareTools(TRIP, "台北", 2)
        with patch("booking_compare.serpapi_hotels.is_configured", return_value=True), \
                patch("booking_compare.serpapi_hotels.search_hotels", return_value={"hotels": []}) as search:
            for _ in range(5):
                tools.search_hotels({"area": "東京"})
        self.assertEqual(search.call_count, bc.MAX_PAID_SEARCHES)

    def test_failed_flight_search_does_not_count(self):
        tools = bc.CompareTools(TRIP, "台北", 2)
        with patch("booking_compare.serpapi_flights.is_configured", return_value=True), \
                patch("booking_compare.serpapi_flights.search_flight_offers", return_value=None):
            result = tools.search_flights({"destination": "東京"})
        self.assertIn("額度", result["error"])
        self.assertEqual(tools.paid_calls, 0)

    def test_unknown_airport_costs_nothing(self):
        tools = bc.CompareTools(TRIP, "火星", 2)
        with patch("booking_compare.serpapi_flights.is_configured", return_value=True), \
                patch("booking_compare.serpapi_flights.search_flight_offers") as search:
            result = tools.search_flights({"destination": "東京"})
        search.assert_not_called()
        self.assertIn("找不到", result["error"])
        self.assertEqual(tools.paid_calls, 0)


class ScopeTests(unittest.TestCase):
    def test_only_chosen_tools_are_given_to_ai(self):
        names = lambda scope: [t.name for t in bc.CompareTools(TRIP, "", 2, scope).tools()]
        self.assertEqual(names(["hotel"]), ["search_hotels"])
        self.assertEqual(names(["flight"]), ["search_flights"])
        self.assertEqual(names(["tra", "hotel"]), ["search_hotels", "search_trains"])

    def test_only_tra_chosen_forces_tra(self):
        tools = bc.CompareTools(dict(TRIP, country="台灣"), "台北", 2, ["tra"])
        with patch("booking_compare.tdx_trains.is_configured", return_value=True), \
                patch("booking_compare.tdx_trains.search_trains", return_value=[]) as search:
            tools.search_trains({"direction": "go", "from_station": "台北", "to_station": "宜蘭", "rail": "thsr"})
        self.assertEqual(search.call_args.kwargs["rail"], "tra")

    def test_scope_defaults_and_cleaning(self):
        self.assertEqual(bc.clean_scope([], TRIP), ["flight", "hotel"])
        self.assertEqual(bc.clean_scope([], dict(TRIP, country="台灣")), ["thsr", "hotel"])
        self.assertEqual(bc.clean_scope(["tra", "bogus", "hotel"], TRIP), ["hotel", "tra"])
        self.assertFalse(bc.needs_origin(["hotel"]))
        self.assertTrue(bc.needs_origin(["hotel", "thsr"]))


class FakeCursor:
    def __init__(self):
        self.lastrowid = 7

    def execute(self, *args):
        pass

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConnection:
    def cursor(self, dictionary=False):
        return FakeCursor()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "member"
        bc._table_ready = True

    def call(self, path, trip, used=0, body=None):
        with patch("blueprints.booking_compare.get_db_connection", return_value=FakeConnection()), \
                patch("blueprints.booking_compare._member_access", return_value=trip), \
                patch("blueprints.booking_compare.ai_ready", return_value=True), \
                patch("booking_compare.used_today", return_value=used), \
                patch("booking_compare.launch") as launch:
            response = self.client.post(path, json=body or {})
        return response, launch

    def future_trip(self, **extra):
        trip = dict(TRIP, start_date=date.today() + timedelta(days=10), end_date=date.today() + timedelta(days=12))
        trip.update(extra)
        return trip

    def test_origin_required(self):
        response, launch = self.call("/member/trips/48/compare", self.future_trip(), body={"origin": " "})
        self.assertEqual(response.status_code, 400)
        launch.assert_not_called()

    def test_daily_limit(self):
        response, launch = self.call("/member/trips/48/compare", self.future_trip(), used=bc.DAILY_LIMIT, body={"origin": "台北"})
        self.assertEqual(response.status_code, 429)
        launch.assert_not_called()

    def test_trip_already_started(self):
        response, _ = self.call("/member/trips/48/compare", dict(TRIP, start_date=date.today() - timedelta(days=1)), body={"origin": "台北"})
        self.assertEqual(response.status_code, 400)

    def test_starts_in_background(self):
        response, launch = self.call("/member/trips/48/compare", self.future_trip(), body={"origin": "台北", "request": "住車站附近"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["compare_id"], 7)
        launch.assert_called_once()

    def test_hotel_only_needs_no_origin(self):
        response, launch = self.call("/member/trips/48/compare", self.future_trip(), body={"origin": "", "scope": ["hotel"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(launch.call_args[0][-1], ["hotel"])  # 只比住宿

    def test_transport_scope_needs_origin(self):
        response, launch = self.call("/member/trips/48/compare", self.future_trip(), body={"origin": "", "scope": ["thsr"]})
        self.assertEqual(response.status_code, 400)
        launch.assert_not_called()

    def test_viewer_cannot_add_hotel(self):
        response, _ = self.call("/member/trips/48/compare/7/add-hotel", self.future_trip(member_role="viewer"), body={"kind": "cheapest"})
        self.assertEqual(response.status_code, 403)


class AddHotelNightsTests(unittest.TestCase):
    RESULT = ('{"searched_at": "11/25 19:51", "options": [{"kind": "cheapest", "lines": '
              '[{"type": "hotel", "title": "漫步 1948 旅店", "address": "太原路42號", "per_night": 2125}]}]}')

    class Cursor:
        def __init__(self, result):
            self.one = [{"result_json": result}] + [{"next_order": 1}] * 10
            self.all = [[{"itinerary_date": date.today() + timedelta(days=11)}]]  # 第 2 晚已經有住宿
            self.inserted = []

        def execute(self, query, params=None):
            if query.strip().startswith("INSERT INTO itineraries"):
                self.inserted.append(params[2])

        def fetchone(self):
            return self.one.pop(0)

        def fetchall(self):
            return self.all.pop(0)

        def close(self):
            pass

    def post(self, body):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "member"
        bc._table_ready = True
        start = date.today() + timedelta(days=10)
        trip = dict(TRIP, start_date=start, end_date=start + timedelta(days=3))  # 3 晚
        cursor = self.Cursor(self.RESULT)
        connection = FakeConnection()
        connection.cursor = lambda dictionary=False: cursor
        with patch("blueprints.booking_compare.get_db_connection", return_value=connection), \
                patch("blueprints.booking_compare._member_access", return_value=trip):
            response = client.post("/member/trips/48/compare/7/add-hotel", json=body)
        return response, cursor.inserted, start

    def test_only_chosen_nights_inside_trip(self):
        start = date.today() + timedelta(days=10)
        response, inserted, _ = self.post({"kind": "cheapest", "dates": [
            start.isoformat(), (start + timedelta(days=1)).isoformat(), "2099-01-01"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(inserted, [start, start + timedelta(days=1)])  # 旅程以外的日期被忽略；有住宿的晚上使用者勾了就加

    def test_nothing_chosen(self):
        response, inserted, _ = self.post({"kind": "cheapest", "dates": []})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(inserted, [])

    def test_without_dates_skips_booked_nights(self):
        response, inserted, start = self.post({"kind": "cheapest"})
        self.assertEqual(inserted, [start, start + timedelta(days=2)])


if __name__ == "__main__":
    unittest.main()
