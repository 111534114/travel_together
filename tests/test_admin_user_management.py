import unittest
from unittest.mock import patch

from app import app


class FakeCursor:
    def __init__(self, results):
        self.results = iter(results)
        self.queries = []
        self.rowcount = 1

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return next(self.results)

    def fetchall(self):
        return next(self.results)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, results):
        self.fake_cursor = FakeCursor(results)
        self.committed = False
        self.rolled_back = False

    def cursor(self, dictionary=False):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class AdminUserManagementTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 3
            session["role"] = "system_admin"

    def test_status_change_requires_reason_before_database_access(self):
        with patch("app.get_db_connection") as database:
            response = self.client.post(
                "/system-admin/users/4/status",
                data={"new_status": "disabled", "reason": ""},
            )

        self.assertEqual(response.status_code, 302)
        database.assert_not_called()

    def test_soft_delete_records_reason_and_history(self):
        connection = FakeConnection([{
            "user_id": 4, "username": "member4", "role": "member", "status": "active",
        }])

        with patch("app.get_db_connection", return_value=connection), patch("app.log_action") as log_action:
            response = self.client.post(
                "/system-admin/users/4/status",
                data={"new_status": "deleted", "reason": "多次違反使用規範"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        queries = connection.fake_cursor.queries
        update_params = next(params for query, params in queries if "UPDATE users SET status" in query)
        self.assertEqual(update_params, ("deleted", 4))
        history_params = next(params for query, params in queries if "INSERT INTO user_moderation_history" in query)
        self.assertEqual(history_params, (4, 3, "delete_user", "active", "deleted", "多次違反使用規範"))
        log_action.assert_called_once()

    def test_detail_page_contains_counts_issues_and_moderation_history(self):
        connection = FakeConnection([
            {
                "user_id": 4, "username": "member4", "full_name": "測試會員",
                "nickname": "小旅人", "email": "member4@example.com", "phone": None,
                "avatar_path": None, "role": "member", "status": "under_review",
                "last_login_at": None, "created_at": "2026-10-01", "updated_at": "2026-10-11",
            },
            {"trip_count": 2, "public_trip_count": 1},
            {"issue_count": 1},
            [{
                "trip_id": 8, "trip_name": "東京行", "visibility": "public",
                "status": "planning", "start_date": "2026-10-20", "end_date": "2026-10-25",
                "created_at": "2026-10-01", "country_name": "日本", "city_name": "東京",
            }],
            [{
                "report_id": 2, "trip_id": 8, "reason": "問題回報：資訊有誤",
                "description": "景點時間錯誤", "status": "processing",
                "handling_result": None, "created_at": "2026-10-10", "handled_at": None,
                "trip_name": "東京行", "handler_username": None,
            }],
            [{
                "moderation_id": 1, "action": "review_user", "from_status": "active",
                "to_status": "under_review", "reason": "確認問題回報內容",
                "created_at": "2026-10-11", "admin_username": "admin", "admin_name": "管理員",
            }],
        ])

        with patch("app.get_db_connection", return_value=connection):
            response = self.client.get("/system-admin/users/4")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("測試會員", body)
        self.assertIn("東京行", body)
        self.assertIn("資訊有誤", body)
        self.assertIn("確認問題回報內容", body)


if __name__ == "__main__":
    unittest.main()
