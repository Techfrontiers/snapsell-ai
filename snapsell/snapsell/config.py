"""Environment-based config. No credential ever lives in this repo.

Live mode is gated twice: SNAPSELL_MODE must be "live" AND both
META_MODEL_API_KEY and META_MODEL_API_BASE must be set. Anything else
runs the stub path, which makes no network call.
"""

import os


class LiveNotConfigured(Exception):
    """Raised when live mode is requested without the required env vars."""


def mode() -> str:
    return os.environ.get("SNAPSELL_MODE", "stub").strip().lower()


def is_live() -> bool:
    return mode() == "live"


def live_config() -> dict:
    """Return live-mode config or raise if it is incomplete.

    The base URL has no default on purpose: the correct endpoint shape
    must be taken from the official Meta Model API docs at switch-on
    time, not guessed here.
    """
    key = os.environ.get("META_MODEL_API_KEY", "").strip()
    base = os.environ.get("META_MODEL_API_BASE", "").strip()
    if not is_live():
        raise LiveNotConfigured("SNAPSELL_MODE is not 'live'; use the stub path.")
    if not key or not base:
        raise LiveNotConfigured(
            "Live mode needs META_MODEL_API_KEY and META_MODEL_API_BASE set "
            "in the environment. See README.md."
        )
    return {"api_key": key, "base_url": base.rstrip("/")}
