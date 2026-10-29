import unittest
from unittest.mock import patch

from app import app
import serve_public


class PublicHostSettingsTests(unittest.TestCase):
    def test_app_does_not_use_old_public_session_key(self):
        self.assertNotEqual(app.secret_key, "travel-together-secret-key")
        self.assertGreaterEqual(len(app.secret_key), 32)

    def test_public_server_rejects_missing_secret_key(self):
        with patch.object(serve_public, "FLASK_SECRET_KEY", "short"):
            with self.assertRaises(SystemExit):
                serve_public.validate_public_settings()

    def test_public_server_rejects_root_or_passwordless_database(self):
        with patch.object(serve_public, "FLASK_SECRET_KEY", "s" * 32), \
             patch.object(serve_public, "PUBLIC_BASE_URL", "https://example.test"), \
             patch.dict(serve_public.DB_CONFIG, {"user": "root", "password": ""}):
            with self.assertRaises(SystemExit):
                serve_public.validate_public_settings()

    def test_public_server_requires_https(self):
        with patch.object(serve_public, "FLASK_SECRET_KEY", "s" * 32), \
             patch.object(serve_public, "PUBLIC_BASE_URL", "http://example.test"), \
             patch.dict(serve_public.DB_CONFIG, {"user": "travel_app", "password": "password"}):
            with self.assertRaises(SystemExit):
                serve_public.validate_public_settings()

    def test_valid_public_settings_pass(self):
        with patch.object(serve_public, "FLASK_SECRET_KEY", "s" * 32), \
             patch.object(serve_public, "PUBLIC_BASE_URL", "https://example.test"), \
             patch.dict(serve_public.DB_CONFIG, {"user": "travel_app", "password": "password"}):
            serve_public.validate_public_settings()


if __name__ == "__main__":
    unittest.main()
