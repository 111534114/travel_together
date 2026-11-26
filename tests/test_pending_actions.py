import json
import unittest
from unittest.mock import patch

import app as app_module
import pending_actions as pa
from app import app


class FakeCursor:
    def __init__(self, answers=()):
        self.answers = list(answers)
        self.queries = []
        self.lastrowid = 50

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.answers.pop(0) if self.answers else None

    def close(self):
        pass

    def ran(self, prefix):
        return [q for q in self.queries if q[0].startswith(prefix)]


class RememberTests(unittest.TestCase):
    def test_known_actions(self):
        self.assertEqual(pa.remember("/member/attractions/12/favorite", "/member/attractions", {})["data"],
                         {"kind": "attraction", "id": 12})
        self.assertEqual(pa.remember("/member/restaurants/3/add-to-trip", "/member/restaurants/3", {})["type"], "add_to_trip")
        self.assertEqual(pa.remember("/member/attractions/2/posts", "/member/attractions/2", {})["type"], "album_post")
        self.assertEqual(pa.remember("/member/booking-favorites/hotel/5", "/visitor/hotels?destination=x", {})["data"],
                         {"kind": "hotel", "id": 5})

    def test_unknown_or_unsafe_is_refused(self):
        self.assertIsNone(pa.remember("/member/trips/5/delete", "/member/", {}))  # 不在清單裡的動作
        self.assertIsNone(pa.remember("/member/attractions/1/favorite", "//evil.example/x", {}))  # 外部網址
        self.assertIsNone(pa.remember("/member/booking-favorites/live", "/visitor/hotels", {"fav": "not json"}))

    def test_live_favorite_keeps_snapshot(self):
        fav = {"kind": "hotel", "key": "k1", "title": "東京飯店", "price": 3000, "link": "https://x"}
        action = pa.remember("/member/booking-favorites/live", "/visitor/hotels?destination=東京", {"fav": json.dumps(fav)})
        self.assertEqual(action["data"]["title"], "東京飯店")


class RunTests(unittest.TestCase):
    def run_action(self, target, back, form=None, answers=()):
        cursor = FakeCursor(answers)
        message, category, url = pa.run(cursor, 4, pa.remember(target, back, form or {}))
        return cursor, message, category, url

    def test_place_favorite_adds(self):
        cursor, message, _, url = self.run_action("/member/attractions/12/favorite", "/member/attractions?keyword=101")
        self.assertTrue(cursor.ran("INSERT INTO favorites"))
        self.assertEqual(url, "/member/attractions?keyword=101")
        self.assertIn("收藏", message)

    def test_place_favorite_never_removes(self):
        cursor, message, _, _ = self.run_action("/member/restaurants/3/favorite", "/member/restaurants", answers=[{"favorite_id": 1}])
        self.assertFalse(cursor.ran("INSERT") or cursor.ran("DELETE"))
        self.assertIn("已經在你的收藏", message)

    def test_add_to_trip_returns_with_open_flag(self):
        _, _, _, url = self.run_action("/member/attractions/12/add-to-trip", "/member/attractions?page=2")
        self.assertEqual(url, "/member/attractions?page=2&add_to_trip=attraction-12")

    def test_album_returns_to_photos(self):
        _, _, _, url = self.run_action("/member/attractions/2/posts", "/member/attractions/2")
        self.assertEqual(url, "/member/attractions/2#album")

    def test_booking_favorite_checks_item_exists(self):
        cursor, _, category, _ = self.run_action("/member/booking-favorites/hotel/5", "/visitor/hotels", answers=[None])
        self.assertEqual(category, "error")
        self.assertFalse(cursor.ran("INSERT"))
        cursor, _, category, url = self.run_action("/member/booking-favorites/hotel/5", "/visitor/hotels?d=x", answers=[{"accommodation_id": 5}])
        self.assertTrue(cursor.ran("INSERT IGNORE INTO booking_favorites"))
        self.assertEqual(url, "/visitor/hotels?d=x")

    def test_live_train_rechecks_tdx(self):
        form = {"live_id": "tdx-thsr-0803-", "from": "台北", "to": "台中", "date": "2026-12-10", "rail": "thsr"}
        with patch("pending_actions.tdx_trains.search_trains", return_value=[]):
            cursor, _, category, _ = self.run_action("/member/booking-favorites/train/live", "/visitor/trains", form)
        self.assertEqual(category, "error")  # 查不到這班車就不收藏，不相信表單送來的資料
        self.assertFalse(cursor.ran("INSERT"))


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_guest_click_is_remembered(self):
        response = self.client.post("/visitor/remember", data={"target": "/member/attractions/12/favorite", "back": "/member/attractions"})
        self.assertIn("/login", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertEqual(session["pending_action"]["type"], "place_favorite")

    def test_unknown_click_is_not_remembered(self):
        self.client.post("/visitor/remember", data={"target": "/member/trips/5/delete", "back": "/member/"})
        with self.client.session_transaction() as session:
            self.assertNotIn("pending_action", session)

    def test_after_login_goes_to_run(self):
        with app.test_request_context("/"):
            from flask import session
            session["pending_action"] = pa.remember("/member/attractions/12/favorite", "/member/attractions", {})
            location = app_module.redirect_by_role("member").headers["Location"]
        self.assertIn("/member/pending-action", location)

    def test_run_once_and_back_to_page(self):
        cursor = FakeCursor()

        class Connection:
            committed = False

            def cursor(self, dictionary=False):
                return cursor

            def commit(self):
                Connection.committed = True

            def rollback(self):
                pass

            def close(self):
                pass

        with self.client.session_transaction() as session:
            session.update(user_id=4, role="member",
                           pending_action=pa.remember("/member/attractions/12/favorite", "/member/attractions?keyword=101", {}))
        with patch("blueprints.member.get_db_connection", return_value=Connection()):
            response = self.client.get("/member/pending-action")
            again = self.client.get("/member/pending-action")
        self.assertTrue(response.headers["Location"].endswith("/member/attractions?keyword=101"))
        self.assertTrue(Connection.committed)
        self.assertEqual(len(cursor.ran("INSERT INTO favorites")), 1)  # 只做一次
        self.assertTrue(again.headers["Location"].endswith("/member/"))


if __name__ == "__main__":
    unittest.main()
