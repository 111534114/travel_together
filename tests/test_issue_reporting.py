import unittest
from unittest.mock import patch

from app import app
from blueprints.member import ISSUE_PREFIX, ISSUE_REASONS


class FakeCursor:
    def __init__(self, results):
        self.results = iter(results)
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return next(self.results)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, results):
        self.fake_cursor = FakeCursor(results)
        self.committed = False

    def cursor(self, dictionary=False):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class IssueReportingTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def login(self, user_id, role):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def test_member_submission_does_not_notify_trip_owner(self):
        self.login(4, "member")
        connection = FakeConnection([{"trip_id": 1, "owner_id": 1}, None])
        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = self.client.post(
                "/member/public-trips/1/issues",
                data={"reason": ISSUE_REASONS[1], "description": "地點資訊有誤"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        queries = connection.fake_cursor.queries
        self.assertTrue(any("INSERT INTO reports" in query for query, _ in queries))
        self.assertFalse(any("notifications" in query for query, _ in queries))
        insert_params = next(params for query, params in queries if "INSERT INTO reports" in query)
        self.assertEqual(insert_params[2], ISSUE_PREFIX + ISSUE_REASONS[1])

    def test_invalid_reason_is_rejected_before_database_access(self):
        self.login(4, "member")
        with patch("blueprints.member.get_db_connection") as database:
            response = self.client.post("/member/public-trips/1/issues", data={"reason": "invalid"})
        self.assertEqual(response.status_code, 302)
        database.assert_not_called()

    def test_system_admin_can_handle_only_issue_reports(self):
        self.login(3, "system_admin")
        connection = FakeConnection([(1,)])
        with patch("app.get_db_connection", return_value=connection), patch("app.log_action"):
            response = self.client.post(
                "/system-admin/issues/1/handle",
                data={"status": "resolved", "handling_result": "已確認並處理"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        select_params = connection.fake_cursor.queries[0][1]
        self.assertEqual(select_params, (1, ISSUE_PREFIX + "%"))


if __name__ == "__main__":
    unittest.main()
