"""Tests for the pure HQ terminal-routing logic.

The routing has several layered fallbacks; each test drives one layer. No
Google Sheets or environment needed — the terminal list and HQ IDs are passed
in directly.
"""

import pytest
from terminal_routing import determine_terminal, parse_manager_name

HQ_PARENT = "1"
FALLBACK = "999"


@pytest.fixture
def terminals():
    return [
        {"id": "1", "name": "Headquarters"},        # HQ parent — never assigned
        {"id": "2", "name": "New Branch"},
        {"id": "3", "name": "Carrier Sales Team"},
        {"id": "4", "name": "Sales Team"},
        {"id": "5", "name": "ADMIN - AP Only"},      # safety-net target
        {"id": "6", "name": "Jane Smith"},           # a manager's own terminal
        {"id": "7", "name": "Branch B"},             # a non-HQ office terminal
    ]


# --------------------------------------------------------------------------
# parse_manager_name: manager email local-part -> "first last".
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "email, expected",
    [
        ("jane.smith@example.com", "jane smith"),
        ("jane_smith@example.com", "jane smith"),   # underscore treated as dot
        ("a.b.c@example.com", "a b"),               # only first two parts used
        ("madonna@example.com", "madonna"),         # no separator -> local part
        ("not-an-email", ""),                       # no '@' -> empty
    ],
)
def test_parse_manager_name(email, expected):
    assert parse_manager_name(email) == expected


# --------------------------------------------------------------------------
# Non-HQ offices: simple name match against the terminal list.
# --------------------------------------------------------------------------

def test_non_hq_matches_office_by_name(terminals):
    assert determine_terminal("Branch B", "", "", "", terminals, HQ_PARENT, FALLBACK) == "7"


def test_non_hq_no_match_returns_empty(terminals):
    assert determine_terminal("Nowhere", "", "", "", terminals, HQ_PARENT, FALLBACK) == ""


# --------------------------------------------------------------------------
# HQ (Branch A) layered routing.
# --------------------------------------------------------------------------

def test_hq_title_routing_beats_manager_match(terminals):
    # BDM title routes to "New Branch" even though the manager (Jane Smith) has
    # their own terminal.
    result = determine_terminal(
        "Branch A", "Business Development Manager", "Sales",
        "jane.smith@example.com", terminals, HQ_PARENT, FALLBACK,
    )
    assert result == "2"


def test_hq_manager_match_when_no_title_rule(terminals):
    result = determine_terminal(
        "Branch A", "Coordinator", "Operations",
        "jane.smith@example.com", terminals, HQ_PARENT, FALLBACK,
    )
    assert result == "6"


def test_hq_department_routing_when_no_title_or_manager(terminals):
    # No title rule, no manager email -> department keywords route to a terminal.
    result = determine_terminal(
        "Branch A", "Rep", "Carrier Sales", "", terminals, HQ_PARENT, FALLBACK,
    )
    assert result == "3"


def test_hq_sales_team_resolution_skips_carrier(terminals):
    # "account" routes to "Sales Team"; name resolution must skip the
    # "Carrier Sales Team" entry and land on the plain "Sales Team".
    result = determine_terminal(
        "Branch A", "Rep", "Account Management", "", terminals, HQ_PARENT, FALLBACK,
    )
    assert result == "4"


def test_hq_safety_net_uses_admin_ap_only(terminals):
    # Unmatched department -> safety net finds the "admin ... ap only" terminal.
    result = determine_terminal(
        "Branch A", "Rep", "Unknowndept", "", terminals, HQ_PARENT, FALLBACK,
    )
    assert result == "5"


def test_hq_safety_net_falls_back_to_id_when_no_admin_terminal(terminals):
    no_admin = [t for t in terminals if t["id"] != "5"]
    result = determine_terminal(
        "Branch A", "Rep", "Unknowndept", "", no_admin, HQ_PARENT, FALLBACK,
    )
    assert result == FALLBACK
