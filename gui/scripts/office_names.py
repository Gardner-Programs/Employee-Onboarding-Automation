"""Pure office display-name mapping.

ONLY for display/address fields (AD City, Gmail address, TPP city). Do NOT use
for logic that distinguishes offices (templates, terminals, extensions, etc.) —
Branch C-II and Branch G-II are distinct offices that merely *display* as their
parent branch.
"""

from __future__ import annotations


OFFICE_DISPLAY_MAP = {
    "Branch C-II": "Branch C",
    "Branch G-II": "Branch G",
    "Branch G-I": "Branch G",
}


def display_office_name(name: str) -> str:
    """Convert office name for display fields only (e.g. AD City, Gmail address)."""
    return OFFICE_DISPLAY_MAP.get(name, name)
