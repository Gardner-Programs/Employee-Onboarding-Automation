"""
Session manager for Selenium cookie persistence.

Saves/restores browser cookies per service (8x8, TP, FCR) so that
if the app crashes or restarts, users don't have to re-authenticate
through 2FA every time.
"""

import os
import sys
import pickle
import time
from datetime import datetime, timedelta

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# When running as a frozen exe, sessions go to a writable app data folder
# instead of the temp extraction dir which gets deleted between runs.
if getattr(sys, 'frozen', False):
    _SESSION_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "AccountTool", "sessions"
    )
else:
    _SESSION_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "sessions")

# How long cached cookies are considered valid before forcing re-login
SESSION_MAX_AGE_HOURS = {
    "8x8": 12,
    "tp": 4,
    "fcr": 4,
}


def _session_path(service_name: str) -> str:
    return os.path.join(_SESSION_DIR, f"{service_name}_cookies.pkl")


def _meta_path(service_name: str) -> str:
    return os.path.join(_SESSION_DIR, f"{service_name}_meta.pkl")


def save_session(driver, service_name: str):
    """Save browser cookies and timestamp for a service after successful login."""
    os.makedirs(_SESSION_DIR, exist_ok=True)
    cookies = driver.get_cookies()
    with open(_session_path(service_name), "wb") as f:
        pickle.dump(cookies, f)
    with open(_meta_path(service_name), "wb") as f:
        pickle.dump({"saved_at": datetime.now(), "url": driver.current_url}, f)


def load_session(driver, service_name: str, base_url: str) -> bool:
    """Attempt to restore cookies for a service.

    Args:
        driver: Selenium WebDriver instance
        service_name: Key for the session (e.g. '8x8', 'tp', 'fcr')
        base_url: URL to navigate to before loading cookies (must match domain)

    Returns:
        True if cookies were loaded and appear fresh, False otherwise.
    """
    cookie_file = _session_path(service_name)
    meta_file = _meta_path(service_name)

    if not os.path.exists(cookie_file) or not os.path.exists(meta_file):
        return False

    try:
        with open(meta_file, "rb") as f:
            meta = pickle.load(f)

        max_age = SESSION_MAX_AGE_HOURS.get(service_name, 4)
        if datetime.now() - meta["saved_at"] > timedelta(hours=max_age):
            clear_session(service_name)
            return False

        with open(cookie_file, "rb") as f:
            cookies = pickle.load(f)

        # Navigate to the domain first so cookies can be set
        driver.get(base_url)
        time.sleep(1)

        for cookie in cookies:
            # Some cookie fields cause issues when restoring
            for key in ["sameSite", "expiry"]:
                cookie.pop(key, None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass  # Skip cookies that fail (wrong domain, etc.)

        # Reload the page with cookies applied
        driver.get(base_url)
        time.sleep(2)
        return True

    except Exception:
        clear_session(service_name)
        return False


def clear_session(service_name: str):
    """Remove cached session files for a service."""
    for path in [_session_path(service_name), _meta_path(service_name)]:
        if os.path.exists(path):
            os.remove(path)


def clear_all_sessions():
    """Remove all cached sessions."""
    for svc in ["8x8", "tp", "fcr"]:
        clear_session(svc)


def session_status(service_name: str) -> dict:
    """Return info about a cached session (for display in GUI)."""
    meta_file = _meta_path(service_name)
    if not os.path.exists(meta_file):
        return {"active": False}
    try:
        with open(meta_file, "rb") as f:
            meta = pickle.load(f)
        max_age = SESSION_MAX_AGE_HOURS.get(service_name, 4)
        age = datetime.now() - meta["saved_at"]
        expired = age > timedelta(hours=max_age)
        return {
            "active": not expired,
            "saved_at": meta["saved_at"].strftime("%I:%M %p"),
            "age_minutes": int(age.total_seconds() / 60),
            "expired": expired,
        }
    except Exception:
        return {"active": False}
