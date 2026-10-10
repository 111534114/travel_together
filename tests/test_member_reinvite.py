import unittest
from unittest.mock import patch

from app import app


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


class MemberReinviteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = "member"

    def test_owner_can_invite_a_removed_member_again(self):
        self.login(1)
        connection = FakeConnection([
            {"trip_id": 8, "trip_name": "重新邀請測試", "join_status": "accepted", "member_role": "owner"},
            {"user_id": 4, "email": "member@example.com"},
            {"join_status": "removed"},
            None,
        ])

        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = self.client.post(
                "/member/trips/8/invite",
                data={"username": "member4", "assigned_role": "viewer"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        self.assertTrue(any("INSERT INTO trip_invitations" in query for query, _ in connection.fake_cursor.queries))

    def test_accepting_again_reactivates_the_existing_membership(self):
        self.login(4)
        connection = FakeConnection([
            {"invitation_id": 5, "trip_id": 8, "assigned_role": "editor", "expires_at": None},
            {"deleted_at": None},
        ])

        with patch("blueprints.member.get_db_connection", return_value=connection):
            response = self.client.post("/member/invitations/5/accept")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        membership_query = next(
            query for query, _ in connection.fake_cursor.queries
            if "INSERT INTO trip_members" in query
        )
        self.assertIn("ON DUPLICATE KEY UPDATE", membership_query)
        self.assertIn("join_status='accepted'", membership_query)


if __name__ == "__main__":
    unittest.main()
