import unittest
from unittest.mock import patch

import app as app_module
from app import app


class FakeCursor:
    def close(self):
        pass


class FakeConnection:
    committed = False

    def cursor(self, dictionary=False):
        return FakeCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class ApplyAfterLoginTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def login_member(self, **extra):
        with self.client.session_transaction() as session:
            session["user_id"] = 4
            session["role"] = "member"
            session.update(extra)

    def test_guest_click_remembers_trip_and_goes_to_login(self):
        response = self.client.get("/visitor/trips/5/apply")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertEqual(session["pending_apply_trip_id"], 5)

    def test_after_login_member_is_sent_to_apply(self):
        with app.test_request_context("/"):
            from flask import session
            session["pending_apply_trip_id"] = 5
            response = app_module.redirect_by_role("member")
        self.assertIn("/member/trips/5/apply-after-login", response.headers["Location"])

    def test_password_login_keeps_pending_trip(self):
        with self.client.session_transaction() as session:
            session["pending_apply_trip_id"] = 5
        user = {"user_id": 4, "username": "amy", "full_name": "Amy", "nickname": "Amy", "role": "member",
                "status": "active", "password_hash": "x"}

        class LoginCursor(FakeCursor):
            def execute(self, *args):
                pass

            def fetchone(self):
                return user

        connection = FakeConnection()
        connection.cursor = lambda dictionary=False: LoginCursor()
        with patch("app.get_db_connection", return_value=connection), patch("app.check_password_hash", return_value=True):
            response = self.client.post("/login", data={"username": "amy", "password": "pw"})
        self.assertIn("/member/trips/5/apply-after-login", response.headers.get("Location", ""))

    def test_apply_copies_trip_and_opens_new_copy(self):
        self.login_member(pending_apply_trip_id=5)
        connection = FakeConnection()
        with patch("blueprints.member.get_db_connection", return_value=connection), \
                patch("blueprints.member._duplicate_trip_for", return_value=(99, None)) as duplicate:
            response = self.client.get("/member/trips/5/apply-after-login")
        duplicate.assert_called_once()
        self.assertEqual(duplicate.call_args[0][1:], (5, 4))
        self.assertIn("/member/trips/99", response.headers["Location"])
        self.assertTrue(connection.committed)
        with self.client.session_transaction() as session:
            self.assertNotIn("pending_apply_trip_id", session)  # 只套用一次

    def test_link_without_clicking_does_not_copy(self):
        # 別人傳來的連結：session 裡沒有記住這趟行程，不會幫你複製
        self.login_member()
        with patch("blueprints.member._duplicate_trip_for") as duplicate:
            response = self.client.get("/member/trips/5/apply-after-login")
        duplicate.assert_not_called()
        self.assertEqual(response.status_code, 302)

    def test_member_duplicate_button_still_works(self):
        self.login_member()
        connection = FakeConnection()
        with patch("blueprints.member.get_db_connection", return_value=connection), \
                patch("blueprints.member._duplicate_trip_for", return_value=(77, None)):
            response = self.client.post("/member/trips/5/duplicate")
        self.assertIn("/member/trips/77", response.headers["Location"])

    def test_copy_not_allowed_shows_reason(self):
        self.login_member(pending_apply_trip_id=5)
        with patch("blueprints.member.get_db_connection", return_value=FakeConnection()), \
                patch("blueprints.member._duplicate_trip_for", return_value=(None, "行程建立者沒有開放這個行程被複製。")):
            response = self.client.get("/member/trips/5/apply-after-login", follow_redirects=False)
        self.assertIn("/member", response.headers["Location"])


class AiPlanAfterLoginTests(unittest.TestCase):
    QUERY = "12 月想跟朋友去東京 5 天，喜歡逛街和美食"

    def setUp(self):
        self.client = app.test_client()

    def test_guest_request_is_remembered(self):
        response = self.client.post("/visitor/ai-plan", data={"q": self.QUERY})
        self.assertIn("/login", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertEqual(session["pending_ai_query"], self.QUERY)

    def test_empty_request_is_not_remembered(self):
        response = self.client.post("/visitor/ai-plan", data={"q": "  "})
        self.assertIn("/visitor", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertNotIn("pending_ai_query", session)

    def test_after_login_member_goes_to_ai_box(self):
        with app.test_request_context("/"):
            from flask import session
            session["pending_ai_query"] = self.QUERY
            response = app_module.redirect_by_role("member")
        self.assertTrue(response.headers["Location"].endswith("/member/#ai-home"))

    def test_password_login_keeps_request(self):
        with self.client.session_transaction() as session:
            session["pending_ai_query"] = self.QUERY
        user = {"user_id": 4, "username": "amy", "full_name": "Amy", "nickname": "Amy", "role": "member",
                "status": "active", "password_hash": "x"}

        class LoginCursor(FakeCursor):
            def execute(self, *args):
                pass

            def fetchone(self):
                return user

        connection = FakeConnection()
        connection.cursor = lambda dictionary=False: LoginCursor()
        with patch("app.get_db_connection", return_value=connection), patch("app.check_password_hash", return_value=True):
            response = self.client.post("/login", data={"username": "amy", "password": "pw"})
        self.assertIn("#ai-home", response.headers.get("Location", ""))
        with self.client.session_transaction() as session:
            self.assertEqual(session["pending_ai_query"], self.QUERY)

    def test_member_home_fills_in_and_auto_starts_once(self):
        class EmptyCursor(FakeCursor):
            def execute(self, *args):
                pass

            def fetchone(self):
                return None

            def fetchall(self):
                return []

        connection = FakeConnection()
        connection.cursor = lambda dictionary=False: EmptyCursor()
        with self.client.session_transaction() as session:
            session.update(user_id=4, role="member", pending_ai_query=self.QUERY)
        with patch("blueprints.member.get_db_connection", return_value=connection):
            html = self.client.get("/member/").get_data(as_text=True)
            again = self.client.get("/member/").get_data(as_text=True)
        self.assertIn('data-autosubmit="1"', html)
        self.assertIn(self.QUERY, html)
        self.assertNotIn('data-autosubmit="1"', again)  # 只會自動排一次


class FavoriteAfterLoginTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    class Cursor(FakeCursor):
        def __init__(self, already=False):
            self.answers = [{"trip_name": "台北"}, {"favorite_id": 1} if already else None]
            self.queries = []

        def execute(self, query, params=None):
            self.queries.append(" ".join(query.split()))

        def fetchone(self):
            return self.answers.pop(0)

    def favorite(self, cursor, remembered=True):
        connection = FakeConnection()
        connection.cursor = lambda dictionary=False: cursor
        with self.client.session_transaction() as session:
            session.update(user_id=4, role="member")
            if remembered:
                session["pending_favorite_trip_id"] = 5
        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = self.client.get("/member/trips/5/favorite-after-login")
        return response, connection

    def test_guest_click_remembers_trip(self):
        response = self.client.get("/visitor/trips/5/favorite")
        self.assertIn("/login", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertEqual(session["pending_favorite_trip_id"], 5)

    def test_after_login_member_is_sent_to_favorite(self):
        with app.test_request_context("/"):
            from flask import session
            session["pending_favorite_trip_id"] = 5
            response = app_module.redirect_by_role("member")
        self.assertIn("/member/trips/5/favorite-after-login", response.headers["Location"])

    def test_adds_favorite(self):
        cursor = self.Cursor()
        response, connection = self.favorite(cursor)
        self.assertTrue(any(q.startswith("INSERT INTO favorites") for q in cursor.queries))
        self.assertTrue(connection.committed)
        self.assertIn("#featured-trips", response.headers["Location"])

    def test_already_favorited_is_not_removed(self):
        cursor = self.Cursor(already=True)
        self.favorite(cursor)
        self.assertFalse(any(q.startswith("DELETE") or q.startswith("INSERT") for q in cursor.queries))

    def test_link_without_clicking_does_nothing(self):
        cursor = self.Cursor()
        self.favorite(cursor, remembered=False)
        self.assertEqual(cursor.queries, [])


class RememberPageTests(unittest.TestCase):
    HTML = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}

    def setUp(self):
        self.client = app.test_client()

    def remembered(self):
        with self.client.session_transaction() as session:
            return session.get("pending_next")

    def test_guest_page_is_remembered_with_message(self):
        response = self.client.get("/member/friend-groups/", headers=self.HTML)
        self.assertIn("/login", response.headers["Location"])
        self.assertEqual(self.remembered(), "/member/friend-groups/")
        page = self.client.get("/login").get_data(as_text=True)
        self.assertIn("登入後會帶你回到剛剛的頁面", page)

    def test_quick_create_keeps_filled_values(self):
        self.client.get("/member/trips/new?city_id=3&start_date=2026-12-20&end_date=2026-12-22&people_count=4", headers=self.HTML)
        self.assertEqual(self.remembered(), "/member/trips/new?city_id=3&start_date=2026-12-20&end_date=2026-12-22&people_count=4")

    def test_background_requests_and_form_posts_are_not_remembered(self):
        self.client.get("/member/notifications/unread", headers={"Accept": "*/*"})  # 背景 API
        self.assertIsNone(self.remembered())
        self.client.post("/member/trips/5/favorite", headers=self.HTML)  # 表單送出
        self.assertIsNone(self.remembered())

    def test_member_goes_back_after_password_login(self):
        self.client.get("/member/friend-groups/", headers=self.HTML)
        user = {"user_id": 4, "username": "amy", "full_name": "Amy", "nickname": "Amy", "role": "member",
                "status": "active", "password_hash": "x"}

        class LoginCursor(FakeCursor):
            def execute(self, *args):
                pass

            def fetchone(self):
                return user

        connection = FakeConnection()
        connection.cursor = lambda dictionary=False: LoginCursor()
        with patch("app.get_db_connection", return_value=connection), patch("app.check_password_hash", return_value=True):
            response = self.client.post("/login", data={"username": "amy", "password": "pw"})
        self.assertTrue(response.headers["Location"].endswith("/member/friend-groups/"))
        self.assertIsNone(self.remembered())  # 用過就清掉

    def redirect_for(self, role, path):
        with app.test_request_context("/"):
            from flask import session
            session["pending_next"] = path
            return app_module.redirect_by_role(role).headers["Location"]

    def test_only_pages_in_own_area(self):
        self.assertTrue(self.redirect_for("content_admin", "/content-admin/proposals/5").endswith("/content-admin/proposals/5"))
        self.assertTrue(self.redirect_for("system_admin", "/system-admin/issues").endswith("/system-admin/issues"))
        self.assertNotIn("/content-admin", self.redirect_for("member", "/content-admin/proposals/5"))  # 會員不會被帶去後台
        self.assertNotIn("evil", self.redirect_for("member", "//evil.example/member"))  # 不會跳到外部網站

    def test_specific_actions_win_over_page(self):
        with app.test_request_context("/"):
            from flask import session
            session["pending_next"] = "/member/friend-groups/"
            session["pending_apply_trip_id"] = 5
            location = app_module.redirect_by_role("member").headers["Location"]
        self.assertIn("/member/trips/5/apply-after-login", location)

    def test_system_admin_pages_are_remembered(self):
        self.client.get("/system-admin/issues", headers=self.HTML)
        self.assertEqual(self.remembered(), "/system-admin/issues")


if __name__ == "__main__":
    unittest.main()
