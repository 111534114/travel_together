import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import trip_assistant
from app import app

TRIP = {"trip_id": 13, "trip_name": "台北", "city": "台北市", "country": "台灣", "city_id": 1, "country_id": 1,
        "start_date": date(2026, 11, 11), "end_date": date(2026, 11, 13), "member_role": "owner", "join_status": "accepted"}
STAMP = datetime(2026, 11, 1, 10, 0, 0)


def item(item_id, day="2026-11-12", start=None, end=None, title="景點", **extra):
    row = {"itinerary_id": item_id, "itinerary_date": date.fromisoformat(day), "item_type": "attraction", "title": title,
           "start_time": start, "end_time": end, "is_all_day": 0, "address": None, "estimated_cost": 0, "notes": None,
           "sort_order": item_id, "transport_method": None, "transport_minutes": 0, "updated_at": STAMP,
           "lat": None, "lng": None, "opening_hours": None}
    row.update(extra)
    return row


class FakeCursor:
    def __init__(self, fetchone=(), fetchall=()):
        self._one, self._all = list(fetchone), list(fetchall)
        self.queries = []
        self.lastrowid = 500

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return self._one.pop(0) if self._one else None

    def fetchall(self):
        return self._all.pop(0) if self._all else []

    def ran(self, prefix):
        return [q for q in self.queries if q[0].startswith(prefix)]

    def close(self):
        pass


class ValidateChangesTests(unittest.TestCase):
    def setUp(self):
        self.items = [item(1, title="象山步道"), item(2, start=timedelta(hours=10), end=timedelta(hours=12), title="台北101")]
        self.tools = trip_assistant.AssistantTools(FakeCursor(), TRIP, self.items)

    def validate(self, changes, cursor=None):
        return trip_assistant.validate_changes(cursor or FakeCursor(), TRIP, self.items, changes, self.tools)

    def test_remove_and_update_existing_items(self):
        accepted, rejected = self.validate([
            {"action": "remove", "itinerary_id": 1, "reason": "太累"},
            {"action": "update", "itinerary_id": 2, "start_time": "14:00", "end_time": "16:00"},
        ])
        self.assertEqual([c["action"] for c in accepted], ["remove", "update"])
        self.assertEqual(rejected, [])
        self.assertEqual(accepted[1]["start_time"], "14:00")
        self.assertEqual(accepted[0]["stamp"], str(STAMP))  # 套用時用來確認沒被別人改過

    def test_unknown_item_and_dates_outside_trip_are_rejected(self):
        accepted, rejected = self.validate([
            {"action": "remove", "itinerary_id": 999},
            {"action": "update", "itinerary_id": 2, "date": "2026-12-25"},
            {"action": "add", "date": "2027-01-01", "item_type": "free_time", "title": "逛街"},
        ])
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 3)

    def test_end_before_start_is_rejected(self):
        accepted, rejected = self.validate([{"action": "update", "itinerary_id": 2, "start_time": "15:00", "end_time": "13:00"}])
        self.assertEqual(accepted, [])
        self.assertIn("結束時間", rejected[0])

    def test_free_text_allowed_only_for_non_places(self):
        accepted, _ = self.validate([{"action": "add", "date": "2026-11-12", "item_type": "transport", "title": "搭捷運"}])
        self.assertEqual(accepted[0]["title"], "搭捷運")

    def test_made_up_place_is_rejected(self):
        # AI 說要加一間「不存在的拉麵店」，但網站查不到、也不是伺服器自己用 Google 查到的
        accepted, rejected = self.validate([{"action": "add", "date": "2026-11-12", "item_type": "restaurant",
                                             "title": "不存在的拉麵店", "google_result_id": 0}])
        self.assertEqual(accepted, [])
        self.assertIn("找不到", rejected[0])

    def test_google_place_must_come_from_server_search(self):
        self.tools.google_results = [{"name": "一蘭拉麵 台北本店", "address": "台北市信義區"}]
        accepted, _ = self.validate([{"action": "add", "date": "2026-11-12", "item_type": "restaurant",
                                      "title": "隨便寫的名字", "google_result_id": 0, "start_time": "12:00"}])
        self.assertEqual(accepted[0]["title"], "一蘭拉麵 台北本店")  # 名稱以 Google 真的查到的為準
        self.assertEqual(accepted[0]["source"], "google")

    def test_site_place_links_to_catalog(self):
        self.tools.site_results[("restaurant", 7)] = {"id": 7, "name": "鼎泰豐 信義店", "address": "信義路", "cost": 0}
        accepted, _ = self.validate([{"action": "add", "date": "2026-11-12", "item_type": "restaurant",
                                      "title": "鼎泰豐", "site_place_id": 7}])
        self.assertEqual((accepted[0]["link_column"], accepted[0]["link_id"]), ("restaurant_id", 7))
        self.assertEqual(accepted[0]["title"], "鼎泰豐 信義店")

    def test_same_item_twice_only_once(self):
        accepted, _ = self.validate([{"action": "remove", "itinerary_id": 1}, {"action": "update", "itinerary_id": 1, "start_time": "09:00"}])
        self.assertEqual(len(accepted), 1)


class ApplyPlanTests(unittest.TestCase):
    def message(self, changes, status="pending"):
        return {"message_id": 3, "plan_status": status, "plan_json": json.dumps({"changes": changes})}

    def test_conflict_when_item_was_edited_by_someone_else(self):
        change = {"action": "remove", "itinerary_id": 1, "title": "象山步道", "old_date": "2026-11-12", "stamp": str(STAMP)}
        edited = dict(item(1), updated_at=datetime(2026, 11, 2, 9, 0, 0))  # 別人剛剛改過
        cursor = FakeCursor(fetchone=[self.message([change])], fetchall=[[edited]])
        with self.assertRaises(trip_assistant.ConflictError):
            trip_assistant.apply_plan(cursor, TRIP, 1, 3)
        self.assertFalse(cursor.ran("DELETE FROM itineraries"))
        self.assertTrue(any("plan_status='stale'" in q for q, _ in cursor.queries))

    def test_already_handled_plan_cannot_be_applied_again(self):
        cursor = FakeCursor(fetchone=[self.message([], status="applied")])
        with self.assertRaises(trip_assistant.ConflictError):
            trip_assistant.apply_plan(cursor, TRIP, 1, 3)

    def test_apply_records_undo_and_notifies_members(self):
        changes = [{"action": "remove", "itinerary_id": 1, "title": "象山步道", "old_date": "2026-11-12", "stamp": str(STAMP)},
                   {"action": "add", "date": "2026-11-12", "start_time": "12:00", "end_time": "13:00", "item_type": "restaurant",
                    "title": "鼎泰豐 信義店", "address": "信義路", "estimated_cost": 0, "link_column": "restaurant_id", "link_id": 7}]
        cursor = FakeCursor(
            fetchone=[self.message(changes), {"name": "小明"}],
            fetchall=[[item(1)], [], [{"itinerary_id": 500, "updated_at": STAMP}], [{"user_id": 2}]],
        )
        count = trip_assistant.apply_plan(cursor, TRIP, 1, 3)
        self.assertEqual(count, 2)
        self.assertTrue(cursor.ran("DELETE FROM itineraries"))
        insert = cursor.ran("INSERT INTO itineraries")[0]
        self.assertIn("restaurant_id", insert[0])
        saved = next(params for q, params in cursor.queries if "plan_status='applied'" in q)
        undo = json.loads(saved[1])
        self.assertEqual(undo["removed"][0]["title"], "景點")
        self.assertEqual(undo["added"][0]["itinerary_id"], 500)
        self.assertTrue(any("INSERT INTO notifications" in q and 2 in p for q, p in cursor.queries))


class ResortTests(unittest.TestCase):
    def test_new_item_goes_in_time_order_and_untimed_items_keep_order(self):
        rows = [{"itinerary_id": 1, "start_time": timedelta(hours=9), "is_all_day": 0},
                {"itinerary_id": 2, "start_time": None, "is_all_day": 0},
                {"itinerary_id": 3, "start_time": timedelta(hours=15), "is_all_day": 0},
                {"itinerary_id": 9, "start_time": timedelta(hours=12), "is_all_day": 0}]  # 新加的，原本排在最後
        cursor = FakeCursor(fetchall=[rows])
        trip_assistant._resort_days(cursor, 13, {"2026-11-12"}, {9})
        order = [params[1] for q, params in cursor.queries if q.startswith("UPDATE itineraries SET sort_order")]
        self.assertEqual(order, [1, 2, 9, 3])


class UndoTests(unittest.TestCase):
    def test_undo_refused_when_changed_after_apply(self):
        undo = {"added": [{"itinerary_id": 500, "stamp": str(STAMP)}], "removed": [], "updated": []}
        cursor = FakeCursor(
            fetchone=[{"message_id": 3}, {"message_id": 3, "undo_json": json.dumps(undo)}],
            fetchall=[[{"itinerary_id": 500, "updated_at": datetime(2026, 11, 5)}]],
        )
        with self.assertRaises(trip_assistant.ConflictError):
            trip_assistant.undo_plan(cursor, TRIP, 1, 3)
        self.assertFalse(cursor.ran("DELETE FROM itineraries"))

    def test_only_latest_apply_can_be_undone(self):
        cursor = FakeCursor(fetchone=[{"message_id": 8}])
        with self.assertRaises(trip_assistant.ConflictError):
            trip_assistant.undo_plan(cursor, TRIP, 1, 3)


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()

    def cursor(self, dictionary=False):
        return self.cursor_obj

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
        trip_assistant._table_ready = True

    def call(self, path, trip, used=0, body=None):
        with patch("blueprints.trip_assistant.get_db_connection", return_value=FakeConnection()), \
                patch("blueprints.trip_assistant._member_access", return_value=trip), \
                patch("blueprints.trip_assistant.ai_ready", return_value=True), \
                patch("trip_assistant.used_today", return_value=used):
            return self.client.post(path, json=body or {})

    def test_viewer_cannot_apply(self):
        response = self.call("/member/trips/13/assistant/apply", dict(TRIP, member_role="viewer"), body={"message_id": 3})
        self.assertEqual(response.status_code, 403)

    def test_daily_limit(self):
        response = self.call("/member/trips/13/assistant/ask", TRIP, used=trip_assistant.DAILY_LIMIT, body={"message": "排輕鬆一點"})
        self.assertEqual(response.status_code, 429)

    def test_non_member_is_refused(self):
        response = self.call("/member/trips/13/assistant/ask", None, body={"message": "hi"})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
