"""Tests for the pure Transport Pro terminal-matching logic.

These are characterization tests: they pin down what the matching algorithm
*currently* does, so future refactors can't silently change behaviour. No
Selenium, Google auth, or environment is needed — that's the whole point of
having extracted these functions into terminal_matching.py.
"""

import pytest

from terminal_matching import (
    _strip_terminal_name,
    _match_office_to_parent,
    _find_best_sub_terminal,
    _find_hq_parent,
)


# --------------------------------------------------------------------------
# _strip_terminal_name: normalises a raw terminal label for fuzzy comparison.
# Transport Pro labels look like "12 - Branch B Office" or "-Carrier Sales"
# (children are prefixed with a dash). Matching needs them reduced to a bare,
# lower-cased core like "branch b" / "carrier sales".
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Sales Team", "sales team"),            # plain name -> just lower-cased
        ("12 - Sales Team", "sales team"),       # leading "<number> - " prefix removed
        ("-Carrier Sales", "carrier sales"),     # leading dash (child marker) removed
        ("Branch K Office", "branch k"),         # trailing " Office" removed
        ("Branch K OFFICE", "branch k"),         # ... case-insensitively
        ("-  45 - Branch K Office", "branch k"), # all rules combined
        ("  admin  ", "admin"),                  # surrounding whitespace trimmed
        ("", ""),                                # empty stays empty (no crash)
    ],
)
def test_strip_terminal_name(raw, expected):
    assert _strip_terminal_name(raw) == expected


# --------------------------------------------------------------------------
# Shared sample hierarchy, shaped exactly like get_terminals() produces:
#   hierarchy: parent_id -> {"name": <label>, "children": [child_id, ...]}
#   flat_lookup: every id (parent and child) -> <label>
# --------------------------------------------------------------------------

@pytest.fixture
def hierarchy():
    return {
        "100": {"name": "10 - Headquarters", "children": ["101", "102"]},
        "200": {"name": "20 - Branch B", "children": ["201"]},
        "300": {"name": "30 - International Office", "children": []},
    }


@pytest.fixture
def flat_lookup():
    return {
        "100": "10 - Headquarters",
        "101": "-Sales Team",
        "102": "-Carrier Sales",
        "200": "20 - Branch B",
        "201": "-Branch B Dispatch",
        "300": "30 - International Office",
    }


# --------------------------------------------------------------------------
# _find_hq_parent: finds the parent whose name normalises to contain
# "headquarters", returning it plus all its children.
# --------------------------------------------------------------------------

def test_find_hq_parent_returns_parent_and_all_children(hierarchy):
    parent_id, all_ids = _find_hq_parent(hierarchy)
    assert parent_id == "100"
    assert all_ids == ["100", "101", "102"]


def test_find_hq_parent_returns_none_when_absent():
    no_hq = {"200": {"name": "20 - Branch B", "children": ["201"]}}
    assert _find_hq_parent(no_hq) == (None, [])


# --------------------------------------------------------------------------
# _match_office_to_parent: maps a reporting-branch string to a parent terminal.
# Returns (parent_id, [parent_id, *children]). An exact match — on the parent
# OR on any child — wins immediately; otherwise a fuzzy substring score breaks
# ties; no match returns (None, []).
# --------------------------------------------------------------------------

def test_match_exact_parent_name(hierarchy, flat_lookup):
    assert _match_office_to_parent("Branch B", hierarchy, flat_lookup) == ("200", ["200", "201"])


def test_match_is_case_insensitive(hierarchy, flat_lookup):
    assert _match_office_to_parent("branch b", hierarchy, flat_lookup) == ("200", ["200", "201"])


def test_match_on_child_returns_the_parent_group(hierarchy, flat_lookup):
    # Searching a child's name resolves to its PARENT plus all siblings,
    # not just the matched child.
    result = _match_office_to_parent("Branch B Dispatch", hierarchy, flat_lookup)
    assert result == ("200", ["200", "201"])


def test_match_strips_office_suffix_for_exact_hit(hierarchy, flat_lookup):
    # "30 - International Office" normalises to "international", so the bare
    # branch name matches exactly.
    assert _match_office_to_parent("International", hierarchy, flat_lookup) == ("300", ["300"])


def test_match_fuzzy_partial_name(hierarchy, flat_lookup):
    # "branch" isn't an exact label, but it's the strongest substring match
    # against "branch b".
    parent_id, _ = _match_office_to_parent("branch", hierarchy, flat_lookup)
    assert parent_id == "200"


def test_match_no_match_returns_none(hierarchy, flat_lookup):
    assert _match_office_to_parent("Nonexistent Place", hierarchy, flat_lookup) == (None, [])


# --------------------------------------------------------------------------
# _find_best_sub_terminal: picks the best child under a known parent. Exact
# child name wins; with no match it returns None (so the caller falls back to
# the parent terminal); a childless parent also yields None.
# --------------------------------------------------------------------------

def test_sub_terminal_exact_child_match(hierarchy, flat_lookup):
    assert _find_best_sub_terminal("Sales Team", "100", hierarchy, flat_lookup) == "101"


def test_sub_terminal_returns_none_on_no_match(hierarchy, flat_lookup):
    # No child matches; return None so the caller falls back to the parent
    # terminal instead of assigning an arbitrary child.
    assert _find_best_sub_terminal("totally unrelated", "100", hierarchy, flat_lookup) is None


def test_sub_terminal_none_when_parent_has_no_children(hierarchy, flat_lookup):
    assert _find_best_sub_terminal("anything", "300", hierarchy, flat_lookup) is None
