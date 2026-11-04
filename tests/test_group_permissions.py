import unittest
from unittest.mock import MagicMock, patch

from app import app


class GroupPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=7, role="member")

    def _connection(self, rows):
        cursor = MagicMock()
        cursor.fetchone.side_effect = rows
        connection = MagicMock()
        connection.cursor.return_value = cursor
        return connection, cursor

    def _group_access(self, connection):
        return (
            patch("blueprints.friend_groups.get_db_connection", return_value=connection),
            patch("blueprints.friend_groups._feature_enabled", return_value=True),
            patch("blueprints.friend_groups._has_line_bound", return_value=True),
        )

    def test_host_gets_separate_edit_page_with_approved_members(self):
        connection, cursor = self._connection([{"group_id": 3, "host_user_id": 7, "trip_id": 11, "trip_owner_id": 7, "title": "宜蘭一日遊"}])
        cursor.fetchall.return_value = [{"user_id": 8, "nickname": "旅伴", "full_name": "旅伴", "avatar_path": "uploads/avatars/updated.webp", "member_role": "viewer"}]
        access, enabled, bound = self._group_access(connection)
        with access, enabled, bound:
            response = self.client.get("/member/friend-groups/groups/3/permissions")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("宜蘭一日遊", html)
        self.assertIn('/static/uploads/avatars/updated.webp', html)
        self.assertIn('action="/member/friend-groups/groups/3/permissions/8"', html)
        self.assertIn('value="editor"', html)
        sql = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertIn("m.status='approved'", sql)
        self.assertIn("tm.join_status='accepted'", sql)
        self.assertIn("u.avatar_path", sql)

    def test_host_can_save_role_and_returns_to_permissions_page(self):
        connection, cursor = self._connection([
            {"host_user_id": 7, "trip_id": 11, "trip_owner_id": 7},
            {"trip_member_id": 25},
        ])
        access, enabled, bound = self._group_access(connection)
        with access, enabled, bound:
            response = self.client.post("/member/friend-groups/groups/3/permissions/8", data={"member_role": "editor"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/member/friend-groups/groups/3/permissions"))
        cursor.execute.assert_any_call("UPDATE trip_members SET member_role=%s WHERE trip_member_id=%s", ("editor", 25))
        connection.commit.assert_called_once()

    def test_other_member_and_unapproved_member_cannot_change_roles(self):
        for rows in ([{"host_user_id": 9, "trip_id": 11, "trip_owner_id": 9}],
                     [{"host_user_id": 7, "trip_id": 11, "trip_owner_id": 9}],
                     [{"host_user_id": 7, "trip_id": 11, "trip_owner_id": 7}, None]):
            with self.subTest(rows=rows):
                connection, cursor = self._connection(rows)
                access, enabled, bound = self._group_access(connection)
                with access, enabled, bound:
                    response = self.client.post("/member/friend-groups/groups/3/permissions/8", data={"member_role": "editor"})
                self.assertEqual(response.status_code, 302)
                connection.commit.assert_not_called()
                self.assertFalse(any("UPDATE trip_members" in call.args[0] for call in cursor.execute.call_args_list))


if __name__ == "__main__":
    unittest.main()
