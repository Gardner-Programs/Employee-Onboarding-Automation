"""Tests for the pure onboarding enrichment rules.

No Google Sheets or pandas needed — these are the plain decision rules lifted
out of data_processing.get_processed_data().
"""

import pytest
from enrichment import (
    clean_identifier,
    determine_region,
    generate_username,
    select_template,
    standardize_location,
)

# --------------------------------------------------------------------------
# clean_identifier: strips dashes and spaces, coerces to str.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("Mary-Jane Smith", "MaryJaneSmith"),
        ("a-b c", "abc"),
        ("  spaced  ", "spaced"),
        (123, "123"),   # non-string coerced
    ],
)
def test_clean_identifier(value, expected):
    assert clean_identifier(value) == expected


# --------------------------------------------------------------------------
# generate_username: first.last, lower-cased. First name has dashes/spaces
# stripped; the last name is only lower-cased (NOT stripped) — a deliberate
# quirk worth pinning down.
# --------------------------------------------------------------------------

def test_username_basic():
    assert generate_username("John", "Smith") == "john.smith"


def test_username_strips_first_name_punctuation_and_spaces():
    assert generate_username("Mary-Jane", "Lee") == "maryjane.lee"
    assert generate_username("Anna Marie", "Lee") == "annamarie.lee"


def test_username_does_not_strip_last_name():
    # Documents current behaviour: a space in the last name survives.
    assert generate_username("Jo", "Van Dyke") == "jo.van dyke"


# --------------------------------------------------------------------------
# standardize_location: collapse raw labels onto canonical branch names.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("International City", "International"),
        ("International Office", "International"),
        ("Remote Field Office", "Branch A"),
        ("Branch C", "Branch C"),   # already canonical -> unchanged
    ],
)
def test_standardize_location(raw, expected):
    assert standardize_location(raw) == expected


# --------------------------------------------------------------------------
# determine_region: physical office -> region, '' when unknown.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "office, expected",
    [
        ("Branch A", "Region A"),
        ("Branch I", "Region B"),       # I deliberately maps to Region B
        ("International", "International"),
        ("Somewhere Else", ""),         # unknown -> empty
    ],
)
def test_determine_region(office, expected):
    assert determine_region(office) == expected


# --------------------------------------------------------------------------
# select_template: base branch template, overridden by corp-department
# keywords, else a role suffix is appended. First match wins; corp beats role.
# --------------------------------------------------------------------------

def test_template_base_branch_when_no_keywords():
    assert select_template("Branch B", "", "") == "branch_b"


def test_template_unknown_branch_falls_back_to_default():
    assert select_template("Nowhere", "", "") == "branch_a"


def test_template_corp_keyword_overrides():
    assert select_template("Branch B", "Billing", "Clerk") == "corp_billing"


def test_template_spaced_hr_keyword_matches():
    # " hr " needs surrounding spaces; it's found inside a title like this.
    assert select_template("Branch A", "Operations", "Senior HR Manager") == "corp_hr"


def test_template_role_suffix_appended_to_base():
    assert select_template("Branch B", "Sales", "Carrier Sales Rep") == "branch_b_carrier_sales"


def test_template_corp_takes_precedence_over_role():
    # Both "credit" (corp) and "carrier sales" (role) appear; corp wins and the
    # role suffix is not applied.
    assert select_template("Branch B", "Credit", "Carrier Sales") == "corp_credit"
