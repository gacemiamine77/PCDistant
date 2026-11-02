import unittest
from unittest.mock import Mock, patch

from server import create_app


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.token = "0042"
        self.capture = Mock(return_value=b"fake-png")
        self.apps = Mock(return_value=[{"id": 42, "name": "Bloc-notes", "title": "Notes"}])
        self.notify = Mock()
        self.client = create_app(self.token, self.notify, self.capture, self.apps).test_client()
        self.headers = {"Authorization": "Bearer " + self.token}

    def test_page_and_assets_are_public(self):
        for path in ["/", "/static/app.js", "/static/style.css"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(self.token.encode(), response.data)
            response.close()

    def test_apis_require_code_before_reading_anything(self):
        for path in ["/api/apps", "/api/screenshot"]:
            for headers in [{}, {"Authorization": "Bearer wrong"}]:
                self.assertEqual(self.client.get(path, headers=headers).status_code, 401)
        self.capture.assert_not_called()
        self.apps.assert_not_called()

    def test_valid_apps(self):
        response = self.client.get("/api/apps", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0]["id"], 42)
        self.notify.assert_called_once()

    def test_capture_and_rate_limit(self):
        response = self.client.get("/api/screenshot", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "image/png")
        self.assertEqual(response.data, b"fake-png")
        self.assertEqual(self.client.get("/api/screenshot", headers=self.headers).status_code, 429)
        self.capture.assert_called_once()

    def test_capture_failure_is_safe(self):
        self.capture.side_effect = RuntimeError("private information")
        response = self.client.get("/api/screenshot", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"private information", response.data)

    def test_headers_no_cors_no_cache(self):
        response = self.client.get("/api/apps", headers=self.headers)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_new_token_revokes_old_access(self):
        other = create_app("1234", applications=self.apps).test_client()
        self.assertEqual(other.get("/api/apps", headers=self.headers).status_code, 401)

    def test_lockout_expires_and_covers_both_routes(self):
        with patch("server.time.monotonic", return_value=100):
            for _ in range(4):
                self.assertEqual(self.client.get("/api/apps").status_code, 401)
            response = self.client.get("/api/screenshot")
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["Retry-After"], "60")
            self.assertEqual(self.client.get("/api/apps", headers=self.headers).status_code, 429)
        with patch("server.time.monotonic", return_value=161):
            self.assertEqual(self.client.get("/api/apps", headers=self.headers).status_code, 200)
        self.capture.assert_not_called()

    def test_success_resets_failed_attempt_counter(self):
        for _ in range(4):
            self.assertEqual(self.client.get("/api/apps").status_code, 401)
        self.assertEqual(self.client.get("/api/apps", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get("/api/apps").status_code, 401)

    def test_no_write_routes(self):
        self.assertEqual(self.client.post("/api/apps", headers=self.headers).status_code, 405)


if __name__ == "__main__":
    unittest.main()
