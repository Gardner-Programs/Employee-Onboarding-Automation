"""Pure cookie-expiry check for the cached 8x8 session cookies."""

from __future__ import annotations

import time


def are_cookies_expired(cookies: list[dict]) -> bool:
    """Return True if there are no cookies, or any cookie's expiry is in the past."""
    if not cookies:
        return True
    current_time = time.time()
    for cookie in cookies:
        if 'expiry' in cookie and cookie['expiry'] < current_time:
            print(f"Cookie {cookie['name']} has expired.")
            return True
    return False
