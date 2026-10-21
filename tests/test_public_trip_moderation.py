import unittest
from unittest.mock import MagicMock, patch

from app import app


class PublicTripModerationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 3
            session["role"] = "system_admin"

    def moderate(self, action, trip, reason="內容違反規範"):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = trip
        with patch("app.get_db_connection", return_value=connection), patch("app.log_action"):
            response = self.client.post(
                "/system-admin/public-trips/8/moderate",
                data={"action": action, "reason": reason},
            )
        return response, connection, cursor

    def test_hide_records_reason_without_changing_visibility(self):
        trip = {"trip_id": 8, "trip_name": "測試", "owner_id": 2, "visibility": "public",
                "moderation_status": "visible", "deleted_at": None}
        response, connection, cursor = self.moderate("hide", trip)
        self.assertEqual(response.status_code, 302)
        connection.commit.assert_called_once()
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("moderation_status = 'hidden'" in sql for sql in statements))
        self.assertFalse(any("visibility = 'private'" in sql for sql in statements))
        self.assertTrue(any("INSERT INTO trip_moderation_history" in sql for sql in statements))

    def test_restore_hidden_private_trip_does_not_make_it_public(self):
        trip = {"trip_id": 8, "trip_name": "測試", "owner_id": 2, "visibility": "private",
                "moderation_status": "hidden", "deleted_at": None}
        _, connection, cursor = self.moderate("restore", trip)
        connection.commit.assert_called_once()
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("moderation_status = 'visible'" in sql for sql in statements))
        self.assertFalse(any("visibility = 'public'" in sql for sql in statements))

    def test_remove_is_soft_delete_and_recorded(self):
        trip = {"trip_id": 8, "trip_name": "測試", "owner_id": 2, "visibility": "public",
                "moderation_status": "visible", "deleted_at": None}
        _, connection, cursor = self.moderate("remove", trip)
        connection.commit.assert_called_once()
        self.assertTrue(any("deleted_at = NOW()" in call.args[0]
                            for call in cursor.execute.call_args_list))

    def test_reason_and_role_are_required(self):
        with patch("app.get_db_connection") as database:
            response = self.client.post("/system-admin/public-trips/8/moderate",
                                        data={"action": "hide", "reason": ""})
            self.assertEqual(response.status_code, 302)
            database.assert_not_called()
        with self.client.session_transaction() as session:
            session["role"] = "member"
        with patch("app.get_db_connection") as database:
            response = self.client.post("/system-admin/public-trips/8/moderate",
                                        data={"action": "hide", "reason": "理由"})
            self.assertEqual(response.status_code, 302)
            database.assert_not_called()


if __name__ == "__main__":
    unittest.main()
