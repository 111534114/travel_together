import unittest
from unittest.mock import patch

from app import app


class SystemAdminNavigationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 3
            session["role"] = "system_admin"

    def test_comment_reports_link_is_visible_on_admin_pages(self):
        with patch("app.get_db_connection", return_value=None):
            for path in ("/system-admin", "/system-admin/public-trips", "/system-admin/comment-reports"):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('href="/system-admin/comment-reports"', response.get_data(as_text=True))
                    if path.endswith("/comment-reports"):
                        self.assertIn('class="active" href="/system-admin/comment-reports"', response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
