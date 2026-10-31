import unittest
from unittest.mock import Mock, patch

from app import app
from content_admin_permissions import _ENDPOINT_ACTIONS
from google_places import search_places


class GooglePlacesBatchMergeTests(unittest.TestCase):
    def test_search_places_uses_next_page_token(self):
        first = Mock(ok=True)
        first.json.return_value = {"places": [{"id": str(i)} for i in range(20)], "nextPageToken": "page-2"}
        second = Mock(ok=True)
        second.json.return_value = {"places": [{"id": "20"}]}
        with patch("google_places.requests.post", side_effect=[first, second]) as post:
            places = search_places("台北 景點", max_results=21)
        self.assertEqual(len(places), 21)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[1].kwargs["json"]["pageToken"], "page-2")

    def test_new_admin_routes_have_create_permission_and_templates(self):
        for module in ("attractions", "restaurants", "accommodations"):
            with self.subTest(module=module):
                self.assertIn(f"{module}.search_import_{module}", app.view_functions)
                self.assertIn(f"{module}.confirm_search_import_{module}", app.view_functions)
                self.assertEqual(_ENDPOINT_ACTIONS[module][f"geocode_{module[:-1] if module != 'accommodations' else 'accommodation'}"], "create")
                app.jinja_env.get_template(f"content_admin/{module}/import_google_search.html")
                app.jinja_env.get_template(f"content_admin/{module}/import_google_search_preview.html")
                app.jinja_env.get_template(f"content_admin/{module}/form.html")
                app.jinja_env.get_template(f"content_admin/{module}/list.html")
        app.jinja_env.get_template("member/attraction_detail.html")

    def test_search_pages_open_for_authorized_content_admin(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "content_admin"
        with patch("content_admin_permissions.content_admin_can", return_value=True), \
             patch.dict(app.jinja_env.globals, {"content_admin_can": lambda *_args: True}):
            for module in ("attractions", "restaurants", "accommodations"):
                with self.subTest(module=module):
                    response = client.get(f"/content-admin/{module}/import/google-search")
                    self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
