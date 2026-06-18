"""Pure terminal-matching logic for Transport Pro provisioning.

These functions take plain data (strings and dicts) and return plain data — no
Selenium, no Google Sheets, no environment. They were extracted out of
``tpp_service`` so the matching algorithm can be tested in isolation, without
standing up a browser driver or any external service. ``tpp_service`` imports
them and wires them to live page data.
"""

from __future__ import annotations

import re


def _strip_terminal_name(name: str) -> str:
    """Strip leading number prefix and trailing 'Office' suffix for fuzzy matching."""
    name = name.lstrip("-").strip()
    name = re.sub(r'^\d+\s*-\s*', '', name)
    name = re.sub(r'\s+Office$', '', name, flags=re.IGNORECASE)
    return name.strip().lower()


def _match_office_to_parent(
    reporting_branch: str,
    hierarchy: dict,
    flat_lookup: dict,
) -> tuple[str | None, list[str]]:
    """Fuzzy-match *reporting_branch* to a parent terminal and return (parent_id, all_child_ids)."""
    search = reporting_branch.lower().strip()

    best_match = None
    best_score = 0

    for parent_id, info in hierarchy.items():
        stripped = _strip_terminal_name(info["name"])
        if stripped == search:
            return parent_id, [parent_id] + info["children"]
        if search in stripped or stripped in search:
            score = len(search) / max(len(stripped), 1)
            if score > best_score:
                best_score = score
                best_match = parent_id

        for child_id in info["children"]:
            child_name = _strip_terminal_name(flat_lookup.get(child_id, ""))
            if child_name == search:
                return parent_id, [parent_id] + info["children"]
            if search in child_name or child_name in search:
                score = len(search) / max(len(child_name), 1)
                if score > best_score:
                    best_score = score
                    best_match = parent_id

    if best_match:
        info = hierarchy[best_match]
        return best_match, [best_match] + info["children"]

    return None, []


def _find_best_sub_terminal(
    reporting_branch: str,
    parent_id: str,
    hierarchy: dict,
    flat_lookup: dict,
) -> str | None:
    """Best-matching child terminal ID under *parent_id*, or None if none match.

    Returning None lets the caller fall back to the parent terminal rather than
    assigning an arbitrary child.
    """
    children = hierarchy.get(parent_id, {}).get("children", [])
    if not children:
        return None

    search = reporting_branch.lower().strip()

    best_child = None
    best_score = 0
    for child_id in children:
        child_name = _strip_terminal_name(flat_lookup.get(child_id, ""))
        if child_name == search:
            return child_id
        if search in child_name or child_name in search:
            score = len(search) / max(len(child_name), 1)
            if score > best_score:
                best_score = score
                best_child = child_id

    return best_child


def _find_hq_parent(hierarchy: dict) -> tuple[str | None, list[str]]:
    """Return (hq_parent_id, all_child_ids) for the headquarters terminal group."""
    for parent_id, info in hierarchy.items():
        stripped = _strip_terminal_name(info["name"])
        if "headquarters" in stripped:
            return parent_id, [parent_id] + info["children"]
    return None, []
