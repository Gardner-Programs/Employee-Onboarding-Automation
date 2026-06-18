"""Pure verification-code logic: parsing 2FA codes out of email snippets and
polling for a fresh one.

These functions take plain strings / callables and return plain values — no
Gmail client, no Selenium, no environment. The Gmail *fetching* lives in
``utils._get_code_from_gmail``; this module is only the parsing and the
poll-until-fresh loop, so the fiddly regexes and the timing logic can be tested
in isolation.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from collections.abc import Callable


def parse_tp_code(snippet: str) -> str | None:
    """Extract a 6-digit Transport Pro verification code from an email snippet."""
    search = re.search(r'process\.\s+(\d{6})', snippet)
    if search:
        return search.group(1)
    return None


def parse_caller_code(snippet: str) -> str | None:
    """Extract a Free Caller Registry verification code from an email snippet."""
    search = re.findall(r'Free Caller Registry Verification Code: \[\d+', snippet)
    if search:
        return str(search[0]).replace("Free Caller Registry Verification Code: [", "")
    return None


def parse_8x8_code(snippet: str) -> str | None:
    """Extract an 8x8 login code from an email snippet."""
    search = re.findall(r'login code: \d+', snippet)
    if search:
        return str(search[0]).replace("login code: ", "")
    return None


def wait_for_verification_code(
    code_func: Callable,
    start_time: datetime,
    max_attempts: int = 10,
    poll_interval: int = 2,
) -> str | None:
    """Poll *code_func* for a fresh verification code from email.

    Args:
        code_func: Function that returns ``(code, timestamp)`` or None.
        start_time: Only accept codes whose timestamp is after this datetime.
        max_attempts: Maximum number of polling attempts before giving up.
        poll_interval: Seconds to wait between attempts.

    Returns:
        The code string, or None if max attempts are exceeded.
    """
    attempts = 0
    while attempts < max_attempts:
        code_data = code_func()
        if isinstance(code_data, tuple) and start_time < code_data[1]:
            return code_data[0]
        time.sleep(poll_interval)
        attempts += 1
    return None
