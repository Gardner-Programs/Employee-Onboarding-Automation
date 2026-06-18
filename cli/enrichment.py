"""Pure enrichment rules for onboarding records.

Each function takes plain strings and returns a plain string — no Google Sheets,
no pandas, no environment. They were lifted out of
``data_processing.get_processed_data`` (which fuses these rules with the Sheets
I/O) so the decision logic can be tested directly. ``data_processing`` imports
them and applies them row by row.
"""

from __future__ import annotations

# Reporting Branch -> base email-signature template key.
BRANCH_MAP = {
    "Branch A": "branch_a",
    "Branch B": "branch_b",
    "Branch C": "branch_c",
    "Branch C-II": "branch_c",
    "Branch D": "branch_d",
    "Branch E": "branch_e",
    "Branch F": "branch_f",
    "Branch G": "default",
    "Branch G-I": "default",
    "Branch G-II": "office_template",
    "Branch H": "branch_h",
    "Branch I": "branch_b",
    "Branch J": "branch_j",
    "International": "international",
}
BRANCH_MAP_DEFAULT = "branch_a"

# Physical Office -> region label.
STATE_MAP = {
    "Branch A": "Region A",
    "Branch B": "Region B",
    "Branch C": "Region C",
    "Branch C-II": "Region C",
    "Branch D": "Region D",
    "Branch E": "Region E",
    "Branch F": "Region F",
    "Branch G": "Region G",
    "Branch G-I": "Region G",
    "Branch G-II": "Region G",
    "Branch H": "Region H",
    "Branch I": "Region B",
    "Branch J": "Region J",
    "International": "International",
    "Remote": "Region A",
    "New Branch": "Region A",
}

# Role keyword sets that append a suffix onto the base branch template.
ROLE_SUFFIXES = [
    (["carrier sales", "carrier rep", "carrier team lead", "carrier sales manager"], "_carrier_sales"),
    (["track and trace", "track & trace", "tracking"], "_track_trace"),
    (["driver service"], "_driver_services"),
    (["expedite"], "_expedite"),
]

# Department/role keyword sets that override the template with a corporate one.
CORP_TEMPLATES = [
    (["billing", "settlements", "pay status"], "corp_billing"),
    (["credit"], "corp_credit"),
    (["claims"], "corp_claims"),
    (["human resources", " hr "], "corp_hr"),
    (["recruiting", "talent acquisition"], "corp_hr"),
    (["fraud"], "corp_fraud"),
    (["transportation"], "corp_transportation"),
]

# Raw location values that map onto canonical branch names.
_INTERNATIONAL_ALIASES = ("International City", "International Office")
_REMOTE_ALIAS = "Remote Field Office"


def clean_identifier(value: object) -> str:
    """Strip dashes and spaces from a name/email fragment."""
    return str(value).replace("-", "").replace(" ", "")


def generate_username(preferred_first: object, preferred_last: object) -> str:
    """Build a ``first.last`` username (first name has dashes/spaces stripped)."""
    return f"{clean_identifier(preferred_first).lower()}.{str(preferred_last).lower()}"


def standardize_location(name: str) -> str:
    """Map raw location labels onto canonical branch names."""
    if name in _INTERNATIONAL_ALIASES:
        return "International"
    if name == _REMOTE_ALIAS:
        return "Branch A"
    return name


def determine_region(physical_office: str) -> str:
    """Return the region label for a physical office, or '' if unknown."""
    return STATE_MAP.get(physical_office, "")


def select_template(reporting_branch: str, department: object, title: object) -> str:
    """Pick the email-signature template key for a new hire.

    Starts from the branch's base template, then a corporate-department keyword
    match overrides it; otherwise a role keyword appends a suffix. The first
    matching rule in each list wins.
    """
    base_template = BRANCH_MAP.get(reporting_branch, BRANCH_MAP_DEFAULT)

    dept_lower = str(department).lower()
    title_lower = str(title).lower()
    combined = dept_lower + " " + title_lower

    selected = base_template
    for keywords, corp_tmpl in CORP_TEMPLATES:
        if any(kw in combined for kw in keywords):
            selected = corp_tmpl
            break
    else:
        for keywords, suffix in ROLE_SUFFIXES:
            if any(kw in combined for kw in keywords):
                selected = base_template + suffix
                break

    return selected
