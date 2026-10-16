import unittest
from unittest.mock import patch

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from auth_storage import StreamlitAuthStorage


class AuthStorageTests(unittest.TestCase):
    def setUp(self):
        self.session_state = {}
        self.storage = StreamlitAuthStorage()
        self.patch_session_state = patch(
            "auth_storage.st.session_state", self.session_state
        )
        self.patch_session_state.start()
        self.addCleanup(self.patch_session_state.stop)

    def test_stores_and_reads_supabase_auth_values(self):
        self.storage.set_item("sb-project-auth-token-code-verifier", "verifier")

        self.assertEqual(
            self.storage.get_item("sb-project-auth-token-code-verifier"),
            "verifier",
        )
        self.assertEqual(
            self.storage.get_code_verifier(),
            ("sb-project-auth-token-code-verifier", "verifier"),
        )

    def test_removes_auth_values(self):
        self.storage.set_item("session-key", "session")

        self.storage.remove_item("session-key")

        self.assertIsNone(self.storage.get_item("session-key"))
        self.assertEqual(self.session_state["_supabase_auth_storage"], {})

    def test_supabase_pkce_flow_stores_verifier_in_streamlit_session(self):
        client = create_client(
            "https://example.supabase.co",
            "public-anon-key",
            options=SyncClientOptions(
                flow_type="pkce",
                storage=self.storage,
            ),
        )

        response = client.auth.sign_in_with_oauth({"provider": "github"})

        verifier_key, verifier = self.storage.get_code_verifier()
        self.assertIn("code_challenge=", response.url)
        self.assertTrue(verifier_key.endswith("-code-verifier"))
        self.assertTrue(verifier)


if __name__ == "__main__":
    unittest.main()
