"""Tests for the small pure helpers extracted from the service modules:
PowerShell escaping, 8x8 number assignment, cookie expiry, and office display
names. None require Selenium or any API client.
"""

import time

import pytest

from ps_utils import ps_escape
from number_assignment import assign_numbers
from cookie_utils import are_cookies_expired
from office_names import display_office_name


# --------------------------------------------------------------------------
# ps_escape: doubles single quotes so values are safe inside '...' literals.
# This is the injection-safety boundary for the AD PowerShell commands.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("O'Brien", "O''Brien"),
        ("no quotes", "no quotes"),
        ("''", "''''"),                          # each quote doubled
        ("'; Remove-Item C:\\ -Recurse", "''; Remove-Item C:\\ -Recurse"),  # injection attempt neutralised
        (123, "123"),                            # non-string coerced
    ],
)
def test_ps_escape(value, expected):
    assert ps_escape(value) == expected


# --------------------------------------------------------------------------
# assign_numbers: picks an extension within the office's range and a phone
# number matching the office prefix, removing both from the pools.
# --------------------------------------------------------------------------

def test_assign_numbers_picks_in_range_and_by_prefix():
    exts = ["1000", "8001", "8500"]            # Branch B range is 8000-8399
    nums = ["1666000", "1555123"]              # default prefix is "1555"
    ext, num = assign_numbers("Branch B", nums, exts)
    assert ext == "8001"
    assert num == "1555123"
    # chosen values are popped out of the pools
    assert "8001" not in exts
    assert "1555123" not in nums


def test_assign_numbers_skips_non_numeric_extensions():
    exts = ["abc", "8100"]
    ext, _ = assign_numbers("Branch B", [], exts)
    assert ext == "8100"


def test_assign_numbers_returns_empty_when_nothing_fits():
    # No extension in range, no number with the prefix.
    ext, num = assign_numbers("Branch B", ["2125550000"], ["1000", "9000"])
    assert ext == ""
    assert num == ""


# --------------------------------------------------------------------------
# are_cookies_expired: True if empty or any cookie's expiry is in the past.
# --------------------------------------------------------------------------

def test_cookies_empty_is_expired():
    assert are_cookies_expired([]) is True


def test_cookies_all_valid_not_expired():
    future = time.time() + 10_000
    assert are_cookies_expired([{"name": "a", "expiry": future}]) is False


def test_cookies_missing_expiry_is_not_expired():
    # A cookie without an 'expiry' key is treated as still valid.
    assert are_cookies_expired([{"name": "session"}]) is False


def test_cookies_one_past_expiry_is_expired():
    past = time.time() - 10_000
    future = time.time() + 10_000
    cookies = [{"name": "ok", "expiry": future}, {"name": "old", "expiry": past}]
    assert are_cookies_expired(cookies) is True


# --------------------------------------------------------------------------
# display_office_name: maps sub-offices onto their display branch.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name, expected",
    [
        ("Branch C-II", "Branch C"),
        ("Branch G-I", "Branch G"),
        ("Branch G-II", "Branch G"),
        ("Branch A", "Branch A"),   # unmapped -> unchanged
    ],
)
def test_display_office_name(name, expected):
    assert display_office_name(name) == expected
