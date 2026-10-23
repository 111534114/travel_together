import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app import app


class MemberProfileMergeTests(unittest.TestCase):
    def test_profile_username_field_is_editable(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, role="member", username="alice")
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = {
            "user_id": 7, "username": "alice", "full_name": "Alice",
            "nickname": "Ali", "email": "old@example.com", "avatar_path": None,
            "created_at": datetime(2026, 1, 1), "status": "active",
        }
        with patch("blueprints.member._connection_or_home", return_value=connection):
            response = client.get("/member/profile")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('name="username"', html)
        self.assertIn('value="alice"', html)
        self.assertNotIn('<input disabled value="alice">', html)

    def test_profile_save_updates_username_and_session(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, role="member", username="alice")
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {"user_id": 7, "username": "alice", "full_name": "Alice",
             "nickname": "Ali", "email": "old@example.com", "avatar_path": None,
             "created_at": datetime(2026, 1, 1), "status": "active"},
            None,
            None,
        ]
        with patch("blueprints.member._connection_or_home", return_value=connection), \
             patch("blueprints.member.save_uploaded_image", return_value=None):
            response = client.post("/member/profile", data={
                "nickname": "New", "email": "new@example.com",
                "username": "alice2",
            })
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_called_once()
        updates = [call for call in cursor.execute.call_args_list
                   if call.args[0].startswith("UPDATE users")]
        self.assertEqual(len(updates), 1)
        self.assertIn("username=%s", updates[0].args[0])
        self.assertEqual(updates[0].args[1], ("alice2", "New", "new@example.com", None, 7))
        with client.session_transaction() as session:
            self.assertEqual(session["username"], "alice2")

    def test_profile_rejects_existing_username(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, role="member", username="alice")
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {"user_id": 7, "username": "alice", "full_name": "Alice",
             "nickname": "Ali", "email": "old@example.com", "avatar_path": None,
             "created_at": datetime(2026, 1, 1), "status": "active"},
            None,
            {"user_id": 9},
        ]
        with patch("blueprints.member._connection_or_home", return_value=connection):
            response = client.post("/member/profile", data={
                "nickname": "New", "email": "new@example.com", "username": "taken",
            })
        self.assertEqual(response.status_code, 200)
        connection.commit.assert_not_called()
        self.assertFalse(any(call.args[0].startswith("UPDATE users")
                             for call in cursor.execute.call_args_list))
        with client.session_transaction() as session:
            self.assertEqual(session["username"], "alice")


if __name__ == "__main__":
    unittest.main()
