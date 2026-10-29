import unittest
from unittest.mock import patch

from flask import redirect

import app as app_module


class OAuthRedirectUriTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.public_base = "https://public.example.test"

    def test_google_public_login_uses_https_even_when_proxy_request_is_http(self):
        with patch.object(app_module, "PUBLIC_BASE_URL", self.public_base), \
             patch.object(app_module, "GOOGLE_CLIENT_ID", "test-client"), \
             patch.object(app_module, "GOOGLE_CLIENT_SECRET", "test-secret"), \
             patch.object(app_module.google_oauth, "authorize_redirect", side_effect=lambda uri: redirect(uri)) as authorize:
            response = self.client.get("/auth/google/login", headers={"Host": "public.example.test"})

        self.assertEqual(response.status_code, 302)
        authorize.assert_called_once_with("https://public.example.test/auth/google/callback")

    def test_google_local_login_keeps_local_callback(self):
        with patch.object(app_module, "PUBLIC_BASE_URL", self.public_base), \
             patch.object(app_module, "GOOGLE_CLIENT_ID", "test-client"), \
             patch.object(app_module, "GOOGLE_CLIENT_SECRET", "test-secret"), \
             patch.object(app_module.google_oauth, "authorize_redirect", side_effect=lambda uri: redirect(uri)) as authorize:
            response = self.client.get("/auth/google/login", base_url="http://127.0.0.1:5000")

        self.assertEqual(response.status_code, 302)
        authorize.assert_called_once_with("http://127.0.0.1:5000/auth/google/callback")

    def test_line_public_login_uses_https(self):
        with patch.object(app_module, "PUBLIC_BASE_URL", self.public_base), \
             patch.object(app_module, "LINE_CHANNEL_ID", "test-client"), \
             patch.object(app_module, "LINE_CHANNEL_SECRET", "test-secret"), \
             patch.object(app_module.line_oauth, "authorize_redirect", side_effect=lambda uri, **kw: redirect(uri)) as authorize:
            response = self.client.get("/auth/line/login", headers={"Host": "public.example.test"})

        self.assertEqual(response.status_code, 302)
        authorize.assert_called_once_with("https://public.example.test/auth/line/callback", bot_prompt="aggressive")

    def test_line_public_binding_uses_https(self):
        with patch.object(app_module, "PUBLIC_BASE_URL", self.public_base), \
             patch.object(app_module, "LINE_CHANNEL_ID", "test-client"), \
             patch.object(app_module, "LINE_CHANNEL_SECRET", "test-secret"), \
             patch.object(app_module.line_oauth, "authorize_redirect", side_effect=lambda uri, **kw: redirect(uri)) as authorize:
            with self.client.session_transaction(base_url="http://public.example.test") as session:
                session["role"] = "member"
                session["user_id"] = 1
            response = self.client.get("/auth/line/bind", headers={"Host": "public.example.test"})

        self.assertEqual(response.status_code, 302)
        authorize.assert_called_once_with("https://public.example.test/auth/line/callback", bot_prompt="aggressive")


if __name__ == "__main__":
    unittest.main()
