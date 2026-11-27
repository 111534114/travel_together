import unittest
from unittest.mock import MagicMock, patch

from app import app


class LogoutBackButtonTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def login(self, role="member"):
        with self.client.session_transaction() as s:
            s.update(user_id=4, role=role)

    def test_logged_in_pages_are_not_kept_by_browser(self):
        self.login()
        connection = MagicMock()
        connection.cursor.return_value.fetchall.return_value = []
        connection.cursor.return_value.fetchone.return_value = None
        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = self.client.get("/member/weather")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("pageshow", response.get_data(as_text=True))  # 上一頁快取拿出來就重新整理

    def test_back_after_logout_goes_to_login(self):
        self.login()
        self.client.get("/logout")
        response = self.client.get("/member/trips", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_admin_pages_are_not_kept_either(self):
        response = self.client.get("/system-admin/issues")  # 沒登入也一樣不留副本
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))

    def test_guest_pages_and_files_keep_normal_cache(self):
        response = self.client.get("/login")
        self.assertNotIn("no-store", response.headers.get("Cache-Control", ""))
        css = self.client.get("/static/css/style.css")
        self.assertNotIn("no-store", css.headers.get("Cache-Control", ""))
        css.close()


if __name__ == "__main__":
    unittest.main()
