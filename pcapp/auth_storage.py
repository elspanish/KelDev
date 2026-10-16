import streamlit as st


_STORAGE_STATE_KEY = "_supabase_auth_storage"


class StreamlitAuthStorage:
    def _items(self) -> dict[str, str]:
        items = st.session_state.get(_STORAGE_STATE_KEY)
        if not isinstance(items, dict):
            items = {}
            st.session_state[_STORAGE_STATE_KEY] = items
        return items

    def get_item(self, key: str) -> str | None:
        return self._items().get(key)

    def set_item(self, key: str, value: str) -> None:
        self._items()[key] = value

    def remove_item(self, key: str) -> None:
        self._items().pop(key, None)

    def get_code_verifier(self) -> tuple[str | None, str | None]:
        for key, value in self._items().items():
            if key.endswith("-code-verifier"):
                return key, value
        return None, None
