"""Pure HQ terminal-routing logic.

Decides which Transport Pro terminal a new hire is assigned to. Takes plain
data — strings plus the terminal list and the HQ terminal IDs (injected, not
read from the environment here) — and returns a terminal ID string. Lifted out
of ``data_processing.get_processed_data`` so the multi-step routing can be
tested without Google Sheets.
"""

from __future__ import annotations


# Title-keyword -> target terminal name. Title routing wins over manager match,
# so a Sr. BDM whose manager has their own terminal still lands in New Branch.
HQ_TITLE_ROUTING = [
    ("business development manager", "New Branch"),
]

# Department-keyword tuples -> target terminal name.
HQ_DEPT_ROUTING = [
    (("carrier", "sales"),  "Carrier Sales Team"),
    (("track",),            "Track & Trace"),
    (("account",),          "Sales Team"),
    (("sales",),            "Sales Team"),
    (("hr",),               "ADMIN"),
    (("it",),               "ADMIN"),
    (("credit",),           "ADMIN"),
    (("billing",),          "ADMIN"),
    (("accounting",),       "ADMIN"),
    (("admin",),            "ADMIN"),
    (("recruiting",),       "ADMIN"),
    (("marketing",),        "ADMIN"),
]


def parse_manager_name(direct_report_email: str) -> str:
    """Turn a manager's email local-part into a "first last" name.

    "jane_smith@x.com" / "jane.smith@x.com" -> "jane smith"; a local-part with
    no separator is returned as-is; a value with no '@' yields "".
    """
    if "@" in direct_report_email:
        local_part = direct_report_email.split("@")[0]
        parts = local_part.replace("_", ".").split(".")
        return f"{parts[0]} {parts[1]}" if len(parts) >= 2 else local_part
    return ""


def determine_terminal(
    physical_office: str,
    title: str,
    department: str,
    direct_report: str,
    tp_terminals: list[dict],
    hq_parent_terminal_id: str,
    hq_admin_fallback_id: str,
) -> str:
    """Resolve the primary terminal ID for a new hire.

    For HQ (Branch A) hires the routing is layered: title keyword, then a match
    on the manager's name, then a department keyword, then name->ID resolution,
    then a safety net (an "admin ... ap only" terminal, else the fallback ID).
    Non-HQ hires simply match their office name against the terminal list.
    """
    found_terminal_id = ""
    search_term = physical_office.lower()

    # === 1. BRANCH A SPECIFIC LOGIC ===
    if physical_office == "Branch A":
        title_lower = str(title).lower()
        dept_lower = str(department).lower()
        target_terminal_name = ""

        # A. Title-based routing
        for keyword, target in HQ_TITLE_ROUTING:
            if keyword in title_lower:
                target_terminal_name = target
                break

        # B. Manager match — only when no title rule fires.
        if not target_terminal_name:
            manager_name = parse_manager_name(str(direct_report))
            if manager_name:
                search_name = manager_name.lower()
                for term in tp_terminals:
                    if term["id"] == hq_parent_terminal_id:
                        continue
                    if search_name in str(term["name"]).lower():
                        found_terminal_id = term["id"]
                        break

        # C. Department fallback
        if not found_terminal_id and not target_terminal_name:
            for keywords, target in HQ_DEPT_ROUTING:
                if all(kw in dept_lower for kw in keywords):
                    target_terminal_name = target
                    break
            if not target_terminal_name:
                target_terminal_name = dept_lower

        # D. Resolve target terminal name -> ID
        if target_terminal_name and not found_terminal_id:
            target = target_terminal_name.lower()
            for term in tp_terminals:
                if term["id"] == hq_parent_terminal_id:
                    continue
                key_name = str(term["name"]).lower()
                if target == "sales team" and "carrier" in key_name:
                    continue
                if target in key_name:
                    found_terminal_id = term["id"]
                    break

        # E. Safety net
        if found_terminal_id in ("", hq_parent_terminal_id):
            found_terminal_id = ""
            for term in tp_terminals:
                tn = str(term["name"]).lower()
                if "admin" in tn and "ap only" in tn and term["id"] != hq_parent_terminal_id:
                    found_terminal_id = term["id"]
                    break
            if not found_terminal_id:
                found_terminal_id = hq_admin_fallback_id

    # === 2. GENERAL LOGIC ===
    else:
        for term in tp_terminals:
            if search_term in str(term["name"]).lower():
                found_terminal_id = term["id"]
                break

    return found_terminal_id
