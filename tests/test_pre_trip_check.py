import unittest
from datetime import date, timedelta
from unittest.mock import patch

import pre_trip_check as pc
import trip_reminders

TRIP = {"trip_id": 13, "trip_name": "台北", "start_date": date(2026, 11, 30), "end_date": date(2026, 12, 2),
        "city": "台北市", "country": "台灣", "total_budget": 0, "currency": "TWD"}


def item(item_id, day="2026-11-30", start=None, end=None, item_type="attraction", title="景點", **extra):
    row = {"itinerary_id": item_id, "itinerary_date": date.fromisoformat(day), "item_type": item_type, "title": title,
           "start_time": timedelta(hours=start[0], minutes=start[1]) if start else None,
           "end_time": timedelta(hours=end[0], minutes=end[1]) if end else None,
           "is_all_day": 0, "estimated_cost": 0, "sort_order": item_id, "transport_method": None, "transport_minutes": 0,
           "lat": None, "lng": None, "opening_hours": None}
    row.update(extra)
    return row


class OpeningHoursParserTests(unittest.TestCase):
    def test_google_format(self):
        hours = pc.parse_opening_hours("星期一: 休息；星期二: 08:30 – 17:30；星期三: 11:30 – 14:30, 17:00 – 00:00；星期四: 24 小時營業")
        self.assertEqual(hours[0], "closed")
        self.assertEqual(hours[1], [(510, 1050)])
        self.assertEqual(hours[2], [(690, 870), (1020, 1440)])  # 營業到半夜 12 點
        self.assertEqual(hours[3], [(0, 1440)])

    def test_cut_off_text_skips_unreadable_day(self):
        hours = pc.parse_opening_hours("星期一: 11:30 – 14:30, 17:3")  # 資料庫欄位 255 字被截斷
        self.assertEqual(hours, {0: [(690, 870)]})

    def test_same_hours_every_day_and_unknown_text(self):
        self.assertEqual(pc.parse_opening_hours("11:00 – 21:00")[4], [(660, 1260)])
        self.assertEqual(pc.parse_opening_hours("請電話洽詢"), {})


class ChecksTests(unittest.TestCase):
    def test_closed_day_and_outside_hours(self):
        hours = "星期一: 休息；星期二: 09:00 – 17:00"
        items = [item(1, "2026-11-30", title="故宮", opening_hours=hours),  # 11/30 是星期一
                 item(2, "2026-12-01", (16, 0), (18, 0), title="博物館", opening_hours=hours),
                 item(3, "2026-12-01", (10, 0), (12, 0), title="有開的", opening_hours=hours)]
        issues = pc.check_opening_hours(items)
        self.assertEqual([i["level"] for i in issues], ["danger", "warn"])
        self.assertIn("公休", issues[0]["text"])
        self.assertIn("09:00–17:00", issues[1]["text"])
        self.assertTrue(issues[0]["ask"])  # 可以請助理幫忙

    def test_missing_lodging_nights(self):
        items = [item(1, "2026-11-30", item_type="accommodation", title="飯店")]
        issues = pc.check_lodging(TRIP, items)
        self.assertIn("12/1", issues[0]["text"])
        self.assertNotIn("11/30", issues[0]["text"])
        self.assertEqual(pc.check_lodging(dict(TRIP, end_date=TRIP["start_date"]), []), [])  # 一日遊不用住宿

    def test_overlap_and_too_busy(self):
        items = [item(1, start=(9, 0), end=(11, 0), title="A"), item(2, start=(10, 30), end=(12, 0), title="B")]
        self.assertIn("重疊", pc.check_schedule(items)[0]["text"])
        busy = [item(i, start=(8 + i, 0), end=(9 + i, 0), title=f"點{i}", transport_minutes=60) for i in range(7)]
        self.assertTrue(any("太滿" in i["text"] for i in pc.check_schedule(busy)))

    def test_far_apart_without_transport(self):
        items = [item(1, title="台北101", lat=25.03, lng=121.56), item(2, title="九份", lat=25.11, lng=121.84)]
        self.assertIn("公里", pc.check_schedule(items)[0]["text"])

    def test_dates_outside_trip(self):
        issues = pc.check_dates(TRIP, [item(1, "2026-09-28", title="台北101")])
        self.assertEqual(issues[0]["level"], "danger")

    def test_budget_only_for_twd(self):
        items = [item(1, estimated_cost=8000)]
        self.assertTrue(pc.check_budget(dict(TRIP, total_budget=5000), items))
        self.assertEqual(pc.check_budget(dict(TRIP, total_budget=5000, currency="JPY"), items), [])
        self.assertEqual(pc.check_budget(dict(TRIP, total_budget=0), items), [])

    def test_weather_rain_and_merged_cold_days(self):
        forecast = {"rain": 70, "max": 20, "min": 15}
        with patch("pre_trip_check.weather.is_configured", return_value=True), \
                patch("pre_trip_check.weather.get_day_forecast", return_value=forecast), \
                patch("pre_trip_check.weather.get_city_warnings", return_value=[]), \
                patch("pre_trip_check.weather.is_taiwan_city", return_value=False):
            issues = pc.check_weather(TRIP, [item(1)], date(2026, 11, 29))
        rain = [i for i in issues if "降雨" in i["text"]]
        cold = [i for i in issues if "外套" in i["text"]]
        self.assertEqual(len(rain), 3)
        self.assertEqual(len(cold), 1)  # 三天都冷，合併成一句
        self.assertIn("～", cold[0]["text"])


class FakeCursor:
    def __init__(self, fetchall=()):
        self._all = list(fetchall)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def executemany(self, query, rows):
        self.queries.append((" ".join(query.split()), rows))

    def fetchall(self):
        return self._all.pop(0) if self._all else []

    def fetchone(self):
        return None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, dictionary=False):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


ISSUE = pc._issue("lodging", "warn", "12/1（二） 晚上還沒有安排住宿", "幫我找住宿")


class ReminderTests(unittest.TestCase):
    def run_precheck(self, issues, members, opted_out=()):
        cursor = FakeCursor([[dict(TRIP)], members, [{"user_id": u} for u in opted_out],
                             members, [{"user_id": u} for u in opted_out]])
        with patch("trip_reminders.get_db_connection", return_value=FakeConnection(cursor)), \
                patch("trip_reminders.pre_trip_check.run_checks", return_value=issues), \
                patch("trip_reminders.line_messaging.push_to_users", return_value=1) as push, \
                patch("trip_reminders.build_precheck_card", return_value={"type": "flex"}), \
                patch("trip_reminders.send_notification") as notify:
            trip_reminders.send_precheck_reminders(date(2026, 11, 27))
        return push, notify

    def test_three_days_before_without_problems_sends_nothing(self):
        push, notify = self.run_precheck([], [{"user_id": 1, "line_ok": 1}])
        push.assert_not_called()
        notify.assert_not_called()

    def test_three_days_before_with_problems(self):
        members = [{"user_id": 1, "line_ok": 1}, {"user_id": 2, "line_ok": 0}, {"user_id": 3, "line_ok": 1}]
        push, notify = self.run_precheck([ISSUE], members, opted_out=[3])
        self.assertEqual(push.call_args[0][0], [1])  # 2 沒綁 LINE、3 關掉出發前檢查
        self.assertEqual(sorted(call[0][1] for call in notify.call_args_list), [1, 2, 3])  # 網站通知由 send_notification 依設定過濾
        self.assertEqual(notify.call_args_list[0][0][2], "precheck")

    def test_day_before_opted_out_member_gets_plain_card(self):
        members = [{"user_id": 1, "line_ok": 1}, {"user_id": 3, "line_ok": 1}]
        cursor = FakeCursor([[dict(TRIP)], members, [{"user_id": 3}], [], []])
        cards = []
        with patch("trip_reminders.get_db_connection", return_value=FakeConnection(cursor)), \
                patch("trip_reminders.pre_trip_check.run_checks", return_value=[ISSUE]), \
                patch("trip_reminders.line_messaging.push_to_users", side_effect=lambda ids, card: cards.append((ids, card)) or len(ids)), \
                patch("trip_reminders.build_card", side_effect=lambda cursor, trip, checks=None: {"checks": checks}):
            trip_reminders.send_trip_reminders(date(2026, 11, 29))
        self.assertEqual(cards[0], ([1], {"checks": pc.summary_lines([ISSUE])}))
        self.assertEqual(cards[1], ([3], {"checks": None}))


class CardTests(unittest.TestCase):
    def test_card_shows_checks_or_all_clear(self):
        import json
        from unittest.mock import Mock
        cursor = Mock()
        cursor.fetchall.return_value = []
        trip = {"trip_id": 5, "trip_name": "東京", "start_date": date(2099, 1, 2), "end_date": date(2099, 1, 5),
                "country": "日本", "city": "東京"}
        with_issue = json.dumps(trip_reminders.build_card(cursor, trip, ["🏨 1/2 晚上還沒有安排住宿"]), ensure_ascii=False)
        all_clear = json.dumps(trip_reminders.build_card(cursor, trip, []), ensure_ascii=False)
        self.assertIn("還沒有安排住宿", with_issue)
        self.assertIn("沒問題", all_clear)


if __name__ == "__main__":
    unittest.main()
