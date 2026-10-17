import json
from pathlib import Path

import streamlit.components.v1 as components


_EXCLUDED_STATE_KEYS = {
    "overview_user_id",
    "persistent_browser_storage",
    "supabase_client",
    "user",
    "user_overview",
}

_browser_storage = components.declare_component(
    "platform_dev_browser_storage",
    path=str(Path(__file__).resolve().parent / "browser_storage"),
)


def build_browser_storage_payload(session_state, auth_session):
    widgets = {}
    for key, value in session_state.items():
        normalized_key = str(key)
        lowered_key = normalized_key.casefold()
        if (
            lowered_key in _EXCLUDED_STATE_KEYS
            or normalized_key.startswith("_")
            or any(
                sensitive in lowered_key
                for sensitive in (
                    "password",
                    "passwd",
                    "secret",
                    "token",
                    "supabase",
                )
            )
            or lowered_key.endswith("_pass")
        ):
            continue
        try:
            widgets[normalized_key] = json.loads(
                json.dumps(value, allow_nan=False)
            )
        except (TypeError, ValueError):
            continue

    auth = None
    if auth_session:
        auth = {
            "access_token": auth_session.access_token,
            "refresh_token": auth_session.refresh_token,
        }
    return {"auth": auth, "widgets": widgets}


def persistent_browser_storage(
    storage_key,
    payload,
    *,
    component_key="persistent_browser_storage_unique",
    clear=False,
):
    return _browser_storage(
        storage_key=storage_key,
        payload=payload,
        clear=clear,
        default=None,
        key=component_key,
    )
