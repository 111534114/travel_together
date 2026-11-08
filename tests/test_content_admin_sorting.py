import unittest
from unittest.mock import MagicMock, patch

from app import app


class ContentAdminSortingTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=7, role="content_admin")

    def _open_list(self, module, query):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"total": 45}
        cursor.fetchall.return_value = []
        connection = MagicMock()
        connection.cursor.return_value = cursor
        options = {"countries": [], "cities": [], "categories": []}
        with patch("content_admin_permissions.content_admin_can", return_value=True), \
             patch.dict(app.jinja_env.globals, {"content_admin_can": lambda *_args: True}), \
             patch(f"blueprints.{module}.get_db_connection", return_value=connection), \
             patch(f"blueprints.{module}._load_options", return_value=options):
            response = self.client.get(f"/content-admin/{module}/", query_string=query)
        return response, cursor

    def test_sorting_and_filters_survive_pagination(self):
        for module in ("attractions", "restaurants", "accommodations"):
            with self.subTest(module=module):
                response, cursor = self._open_list(module, {
                    "country_id": "1", "sort": "location-desc", "page": "2",
                })
                html = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn('value="location-desc" selected', html)
                self.assertIn("sort=location-desc", html)
                self.assertIn("country_id=1", html)
                self.assertIn("ORDER BY co.name DESC, ci.name DESC", cursor.execute.call_args_list[1].args[0])

    def test_unlisted_sort_cannot_be_inserted_into_sql(self):
        for module, table in (("attractions", "a.attraction_id"),
                              ("restaurants", "r.restaurant_id"),
                              ("accommodations", "ac.accommodation_id")):
            with self.subTest(module=module):
                response, cursor = self._open_list(module, {"sort": "name-desc;DROP TABLE users"})
                sql = cursor.execute.call_args_list[1].args[0]
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"ORDER BY {table} DESC", sql)
                self.assertNotIn("DROP TABLE", sql)


if __name__ == "__main__":
    unittest.main()
