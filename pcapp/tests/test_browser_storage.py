import unittest
from types import SimpleNamespace

from browser_storage import build_browser_storage_payload


class BrowserStoragePayloadTests(unittest.TestCase):
    def test_keeps_widget_values_and_auth_tokens_without_passwords(self):
        payload = build_browser_storage_payload(
            {
                "project_title": "Plataforma comunitaria",
                "project_tasks_editor_0": [{"titulo": "Crear pantalla"}],
                "login_pass": "not-persisted",
                "reg_password": "not-persisted",
                "user": object(),
                "supabase_client": object(),
                "user_overview": {"profile": {"email": "user@example.com"}},
            },
            SimpleNamespace(
                access_token="access-token",
                refresh_token="refresh-token",
            ),
        )

        self.assertEqual(
            payload["widgets"],
            {
                "project_title": "Plataforma comunitaria",
                "project_tasks_editor_0": [{"titulo": "Crear pantalla"}],
            },
        )
        self.assertEqual(
            payload["auth"],
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
            },
        )

    def test_clears_auth_tokens_when_there_is_no_session(self):
        payload = build_browser_storage_payload({}, None)

        self.assertIsNone(payload["auth"])


if __name__ == "__main__":
    unittest.main()
