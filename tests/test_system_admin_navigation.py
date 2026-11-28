import unittest
from unittest.mock import patch

from app import app


class SystemAdminNavigationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 3
            session["role"] = "system_admin"

    def test_comment_reports_page_is_removed(self):
        with patch("app.get_db_connection", return_value=None):
            for path in ("/system-admin", "/system-admin/public-trips"):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertNotIn("comment-reports", html)
                    self.assertNotIn("留言檢舉", html)
            self.assertEqual(self.client.get("/system-admin/comment-reports").status_code, 404)

    def test_member_comment_report_route_is_removed(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 4
            session["role"] = "member"
        self.assertEqual(self.client.post("/member/trips/1/comments/1/report").status_code, 404)


if __name__ == "__main__":
    unittest.main()
