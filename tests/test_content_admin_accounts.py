import unittest
from unittest.mock import MagicMock, patch

from werkzeug.security import check_password_hash

from app import app
from content_admin_permissions import CONTENT_ADMIN_ACTIONS


class ContentAdminAccountTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as user_session:
            user_session["user_id"] = 3
            user_session["role"] = "system_admin"
            user_session["admin_account_csrf"] = "test-token"

    def test_create_content_admin_hashes_password_and_saves_denied_modules(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = None
        cursor.lastrowid = 77
        data = {
            "csrf": "test-token", "username": "editor77", "full_name": "測試管理員",
            "email": "editor77@example.com", "password": "Password123",
            "confirm_password": "Password123", "modules": ["attractions"],
        }
        with patch("blueprints.content_admin_accounts.get_db_connection", return_value=connection), patch(
            "blueprints.content_admin_accounts.log_action"
        ):
            response = self.client.post("/system-admin/content-admins/new", data=data)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/system-admin/users/77", response.location)
        statements = [(call.args[0], call.args[1]) for call in cursor.execute.call_args_list]
        insert = next(params for query, params in statements if "INSERT INTO users" in query)
        self.assertTrue(check_password_hash(insert[1], "Password123"))
        self.assertNotIn("Password123", str(cursor.execute.call_args_list))
        cursor.executemany.assert_called_once()
        self.assertNotIn("attractions", [row[1] for row in cursor.executemany.call_args.args[1]])
        connection.commit.assert_called_once()

    def test_reset_password_requires_csrf_and_hashes_new_password(self):
        denied = self.client.post("/system-admin/content-admins/2/reset-password", data={"password": "Newpass123"})
        self.assertEqual(denied.status_code, 400)
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {"user_id": 2, "username": "contentadmin", "role": "content_admin"}
        with patch("blueprints.content_admin_accounts.get_db_connection", return_value=connection), patch(
            "blueprints.content_admin_accounts.log_action"
        ):
            response = self.client.post("/system-admin/content-admins/2/reset-password", data={
                "csrf": "test-token", "password": "Newpass123", "confirm_password": "Newpass123",
            })
        self.assertEqual(response.status_code, 302)
        update = next(call.args[1] for call in cursor.execute.call_args_list if "UPDATE users SET password_hash" in call.args[0])
        self.assertTrue(check_password_hash(update[0], "Newpass123"))
        connection.commit.assert_called_once()

    def test_denied_module_is_blocked_before_its_view(self):
        with self.client.session_transaction() as user_session:
            user_session["user_id"] = 2
            user_session["role"] = "content_admin"
        connection = MagicMock()
        connection.cursor.return_value.fetchall.return_value = [("attractions",)]
        with patch("content_admin_permissions.get_db_connection", return_value=connection), patch(
            "blueprints.attractions.get_db_connection"
        ) as content_db:
            response = self.client.get("/content-admin/attractions/")
        self.assertEqual(response.status_code, 403)
        content_db.assert_not_called()

    def test_permissions_are_limited_to_content_admin_accounts(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {
            "user_id": 2, "username": "contentadmin", "role": "content_admin",
        }
        with patch("blueprints.content_admin_accounts.get_db_connection", return_value=connection), patch(
            "blueprints.content_admin_accounts.log_action"
        ):
            response = self.client.post("/system-admin/content-admins/2/permissions", data={
                "csrf": "test-token", "modules": ["attractions", "restaurants"],
            })
        self.assertEqual(response.status_code, 302)
        cursor.executemany.assert_called_once()
        denied = {module for _, module in cursor.executemany.call_args.args[1]}
        self.assertNotIn("attractions", denied)
        self.assertNotIn("restaurants", denied)
        self.assertIn("accommodations", denied)
        connection.commit.assert_called_once()

        bad_response = self.client.post("/system-admin/content-admins/2/permissions", data={
            "csrf": "test-token", "modules": ["system_admin"],
        })
        self.assertEqual(bad_response.status_code, 400)

    def test_permission_page_shows_action_matrix_for_content_admin(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {
            "user_id": 2, "username": "contentadmin", "full_name": "內容管理員",
            "role": "content_admin",
        }
        cursor.fetchall.return_value = [{"module": "attractions:delete"}]
        with patch("blueprints.content_admin_accounts.get_db_connection", return_value=connection):
            response = self.client.get("/system-admin/content-admins/2/permissions")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("權限設定", body)
        self.assertIn("attractions:create", body)
        self.assertIn("attractions:delete", body)
        self.assertIn("查看", body)

    def test_action_permissions_are_saved_and_enforced(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {
            "user_id": 2, "username": "contentadmin", "role": "content_admin",
        }
        with patch("blueprints.content_admin_accounts.get_db_connection", return_value=connection), patch(
            "blueprints.content_admin_accounts.log_action"
        ):
            response = self.client.post("/system-admin/content-admins/2/permissions", data={
                "csrf": "test-token", "permission_matrix": "1",
                "permissions": ["attractions:view", "attractions:edit"],
            })
        self.assertEqual(response.status_code, 302)
        denied = {permission for _, permission in cursor.executemany.call_args.args[1]}
        self.assertIn("attractions:create", denied)
        self.assertIn("attractions:delete", denied)
        self.assertNotIn("attractions:view", denied)
        connection.commit.assert_called_once()

        with self.client.session_transaction() as user_session:
            user_session["user_id"] = 2
            user_session["role"] = "content_admin"
        permission_db = MagicMock()
        permission_db.cursor.return_value.fetchall.return_value = [("attractions:create",)]
        with patch("content_admin_permissions.get_db_connection", return_value=permission_db), patch(
            "blueprints.attractions.get_db_connection"
        ) as content_db:
            blocked = self.client.get("/content-admin/attractions/new")
        self.assertEqual(blocked.status_code, 403)
        content_db.assert_not_called()

    def test_delete_permission_blocks_direct_request(self):
        with self.client.session_transaction() as user_session:
            user_session["user_id"] = 2
            user_session["role"] = "content_admin"
        permission_db = MagicMock()
        permission_db.cursor.return_value.fetchall.return_value = [("attractions:delete",)]
        with patch("content_admin_permissions.get_db_connection", return_value=permission_db), patch(
            "blueprints.attractions.get_db_connection"
        ) as content_db:
            response = self.client.post("/content-admin/attractions/8/delete")
        self.assertEqual(response.status_code, 403)
        content_db.assert_not_called()

    def test_ai_assistant_cannot_bypass_location_create_permission(self):
        from blueprints.ai_chat import _execute_tool

        cursor = MagicMock()
        with patch("blueprints.ai_chat.content_admin_can", return_value=False) as allowed:
            result = _execute_tool(cursor, "add_country", {"name": "測試國家"})
        self.assertIn("沒有", result)
        allowed.assert_called_once_with("locations", "create")
        cursor.execute.assert_not_called()

    def test_action_permissions_require_view_and_reject_unknown_values(self):
        missing_view = self.client.post("/system-admin/content-admins/2/permissions", data={
            "csrf": "test-token", "permission_matrix": "1",
            "permissions": ["attractions:delete"],
        })
        unknown = self.client.post("/system-admin/content-admins/2/permissions", data={
            "csrf": "test-token", "permission_matrix": "1",
            "permissions": ["users:delete"],
        })
        self.assertEqual(missing_view.status_code, 400)
        self.assertEqual(unknown.status_code, 400)

    def test_promoted_member_starts_without_content_admin_permissions(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {
            "user_id": 17, "username": "member17", "role": "member", "status": "active",
        }
        with patch("app.get_db_connection", return_value=connection), patch("app.log_action"):
            response = self.client.post("/system-admin/users/17/role", data={"role": "content_admin"})
        self.assertEqual(response.status_code, 302)
        denials = {permission for _, permission in cursor.executemany.call_args.args[1]}
        expected = {
            f"{module}:{action}"
            for module, actions in CONTENT_ADMIN_ACTIONS.items() for action in actions
        }
        self.assertEqual(denials, expected)
        connection.commit.assert_called_once()

    def test_content_admin_cannot_create_another_admin(self):
        with self.client.session_transaction() as user_session:
            user_session["user_id"] = 2
            user_session["role"] = "content_admin"
        response = self.client.get("/system-admin/content-admins/new")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    def test_denied_module_is_hidden_from_content_admin_navigation(self):
        with self.client.session_transaction() as user_session:
            user_session["user_id"] = 2
            user_session["role"] = "content_admin"
        connection = MagicMock()
        connection.cursor.return_value.fetchall.return_value = [("attractions",)]
        with patch("content_admin_permissions.get_db_connection", return_value=connection):
            response = self.client.get("/content-admin/account/password")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("景點管理", body)
        self.assertIn("餐廳管理", body)

    def test_logs_filter_uses_exact_admin_id(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {"username": "contentadmin", "full_name": "內容管理員"}
        cursor.fetchall.side_effect = [[], []]
        with patch("app.get_db_connection", return_value=connection):
            response = self.client.get("/system-admin/logs?admin_id=2")
        self.assertEqual(response.status_code, 200)
        log_query = next(call for call in cursor.execute.call_args_list if "FROM admin_logs l" in call.args[0])
        self.assertIn("l.admin_id = %s", log_query.args[0])
        self.assertEqual(log_query.args[1], (2,))


if __name__ == "__main__":
    unittest.main()
