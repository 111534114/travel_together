import unittest
from unittest.mock import MagicMock, patch

from app import app
from chat_moderation import blocked_term


class ChatTermsAdminTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _login(self, role):
        with self.client.session_transaction() as session:
            session["user_id"] = 2
            session["role"] = role

    def test_system_admin_sees_existing_terms(self):
        self._login("system_admin")
        cursor = MagicMock()
        cursor.fetchone.return_value = {"setting_value": "測試詞,廣告"}
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with patch("blueprints.friend_groups_admin.get_db_connection", return_value=connection):
            response = self.client.get("/content-admin/friend-groups/settings/chat-terms")
        self.assertEqual(response.status_code, 200)
        self.assertIn("測試詞,廣告".encode(), response.data)

    def test_system_admin_can_save_terms(self):
        self._login("system_admin")
        cursor = MagicMock()
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with patch("blueprints.friend_groups_admin.get_db_connection", return_value=connection), \
             patch("blueprints.friend_groups_admin.log_action"):
            response = self.client.post("/content-admin/friend-groups/settings/chat-terms",
                                        data={"blocked_terms": "測試詞\n廣告"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/settings/chat-terms", response.location)
        self.assertTrue(any(call.args[1] == ("chat_blocked_terms", "測試詞,廣告", 2)
                            for call in cursor.execute.call_args_list))
        connection.commit.assert_called_once()

    def test_content_admin_cannot_read_or_save_terms(self):
        self._login("content_admin")
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__), \
                 patch("blueprints.friend_groups_admin.get_db_connection") as db:
                response = method("/content-admin/friend-groups/settings/chat-terms")
                self.assertEqual(response.status_code, 302)
                db.assert_not_called()

    def test_long_term_list_is_saved_and_last_term_is_blocked(self):
        self._login("system_admin")
        terms = [f"測試詞{i:03d}" for i in range(100)]
        cursor = MagicMock()
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with patch("blueprints.friend_groups_admin.get_db_connection", return_value=connection), \
             patch("blueprints.friend_groups_admin.log_action"):
            response = self.client.post("/content-admin/friend-groups/settings/chat-terms",
                                        data={"blocked_terms": "\n".join(terms)})
        saved = next(call.args[1][1] for call in cursor.execute.call_args_list
                     if "INSERT INTO app_settings" in call.args[0])
        self.assertGreater(len(saved), 255)
        self.assertEqual(len(saved.split(",")), 100)
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_called_once()
        cursor.fetchone.return_value = {"setting_value": saved}
        self.assertEqual(blocked_term(cursor, "這裡有測試詞099"), "測試詞099")

    def test_single_overlong_term_is_rejected(self):
        self._login("system_admin")
        with patch("blueprints.friend_groups_admin.get_db_connection") as db:
            response = self.client.post("/content-admin/friend-groups/settings/chat-terms",
                                        data={"blocked_terms": "字" * 41})
        self.assertEqual(response.status_code, 302)
        db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
