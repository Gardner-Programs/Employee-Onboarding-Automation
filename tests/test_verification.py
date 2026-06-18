"""Tests for the pure verification-code parsing and polling logic.

No Gmail client or Selenium needed — the email *fetching* lives in utils; this
module is only the regexes and the poll-until-fresh loop.
"""

from datetime import datetime

import pytest
import verification
from verification import (
    parse_8x8_code,
    parse_caller_code,
    parse_tp_code,
    wait_for_verification_code,
)

# --------------------------------------------------------------------------
# Code parsers: each pulls a code out of a real-looking email snippet, and
# returns None when the expected pattern isn't present.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "snippet, expected",
    [
        ("Enter the code to complete this process.  654321 to continue", "654321"),
        ("Your Transport Pro code: 654321", None),   # missing the "process." anchor
        ("process. 12345 only five digits", None),   # needs exactly 6 digits
        ("nothing relevant here", None),
    ],
)
def test_parse_tp_code(snippet, expected):
    assert parse_tp_code(snippet) == expected


@pytest.mark.parametrize(
    "snippet, expected",
    [
        ("Free Caller Registry Verification Code: [789012] expires soon", "789012"),
        ("Free Caller Registry Verification Code: [42]", "42"),
        ("no fcr code in this one", None),
    ],
)
def test_parse_caller_code(snippet, expected):
    assert parse_caller_code(snippet) == expected


@pytest.mark.parametrize(
    "snippet, expected",
    [
        ("Your 8x8 login code: 246810 expires in 5 min", "246810"),
        ("Your 8x8 login code: 7", "7"),
        ("unrelated message", None),
    ],
)
def test_parse_8x8_code(snippet, expected):
    assert parse_8x8_code(snippet) == expected


# --------------------------------------------------------------------------
# wait_for_verification_code: polls a supplied code_func until it returns a
# code newer than start_time. Tested by injecting a fake code_func; sleep is
# patched out so the tests run instantly.
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Make time.sleep a no-op inside the verification module for these tests."""
    monkeypatch.setattr(verification.time, "sleep", lambda *_a, **_k: None)


START = datetime(2020, 1, 1)
FRESH = datetime(2025, 1, 1)   # after START
STALE = datetime(2019, 1, 1)   # before START


def test_returns_fresh_code_immediately():
    code = wait_for_verification_code(lambda: ("123456", FRESH), START, max_attempts=3)
    assert code == "123456"


def test_ignores_stale_code_and_gives_up():
    # The code exists but predates start_time, so it's never accepted.
    code = wait_for_verification_code(lambda: ("999999", STALE), START, max_attempts=3)
    assert code is None


def test_returns_none_when_no_code_arrives():
    code = wait_for_verification_code(lambda: None, START, max_attempts=3)
    assert code is None


def test_polls_until_a_fresh_code_appears():
    # No code on the first two polls, then a fresh one — should return it.
    responses = [None, None, ("555444", FRESH)]
    code = wait_for_verification_code(lambda: responses.pop(0), START, max_attempts=5)
    assert code == "555444"
