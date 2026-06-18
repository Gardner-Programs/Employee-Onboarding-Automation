"""
Load, enrich, and write back onboarding form data from Google Sheets.

get_processed_data() reads the Onboarding Form and TP Key sheets, then
enriches each row with a generated username, region, terminal ID, office
phone, and email signature template key before returning the final list.
"""

from __future__ import annotations

import os
import sys
import pandas
from unidecode import unidecode
from config import get_spreadsheet, get_tp_key_worksheet, get_onboarding_worksheet
from enrichment import (
    clean_identifier, generate_username, standardize_location, determine_region,
    select_template,
)

# --- HQ sub-terminal routing ---
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

# HQ parent terminal — must never be assigned as a primary terminal.
# Set to the terminal ID of your HQ parent terminal in Transport Pro
HQ_PARENT_TERMINAL_ID = os.environ.get("HQ_PARENT_TERMINAL_ID", "YOUR_PARENT_TERMINAL_ID")
# Fallback terminal ID when no department match is found
HQ_ADMIN_FALLBACK_ID = os.environ.get("HQ_ADMIN_FALLBACK_ID", "YOUR_FALLBACK_TERMINAL_ID")


def get_processed_data() -> list[dict]:
    """Load the Onboarding Form and return enriched new-hire records.

    Reads the Google Sheet, normalises names/locations, and adds computed
    fields: Username, State, Terminal, Office Phone, and Template.
    Returns an empty list when the sheet has no data rows.
    """
    spreadsheet = get_spreadsheet()
    tp_key = get_tp_key_worksheet(spreadsheet)

    # --- LOAD TP KEY DATA FOR LOOKUPS ---
    tp_key_data = tp_key.get_all_values()
    tp_terminals = []
    if len(tp_key_data) > 1:
        for r in tp_key_data:
            if len(r) >= 2:
                tp_terminals.append({"id": r[0], "name": r[1]})

    aa_sheet = get_onboarding_worksheet(spreadsheet)
    wks = aa_sheet.get_all_values()
    df = pandas.DataFrame(wks)
    if len(df) <= 1:
        return []

    df = df.tail(-1).rename(columns=df.iloc[0])

    array = df.to_dict("records")

    for row in array:
        # 1. Clean Names and Email
        row["Preferred First Name"] = clean_identifier(row["Preferred First Name"])
        row["Employee Email"] = clean_identifier(row["Employee Email"])

        # 2. Handle Location Standardization
        row["Reporting Branch"] = standardize_location(row["Reporting Branch"])
        row["Physical Office"] = standardize_location(row["Physical Office"])

        # 3. Unidecode all fields
        for col in row:
            row[col] = unidecode(str(row[col]))

        # --- A. GENERATE USERNAME ---
        row["Username"] = generate_username(row["Preferred First Name"], row["Preferred Last Name"])

        # --- B. DETERMINE REGION ---
        row["State"] = determine_region(row["Physical Office"])

        # --- C. DETERMINE TERMINAL ---
        found_terminal_id = ""
        physical_office = str(row["Physical Office"])
        search_term = physical_office.lower()

        # === 1. BRANCH A SPECIFIC LOGIC ===
        if physical_office == "Branch A":
            title_lower = str(row["Title"]).lower()
            dept_lower = str(row["Department"]).lower()
            target_terminal_name = ""

            # A. Title-based routing
            for keyword, target in HQ_TITLE_ROUTING:
                if keyword in title_lower:
                    target_terminal_name = target
                    break

            # B. Manager match — only when no title rule fires.
            if not target_terminal_name:
                direct_report_email = str(row["Direct Report"])
                manager_name = ""
                if "@" in direct_report_email:
                    local_part = direct_report_email.split("@")[0]
                    parts = local_part.replace("_", ".").split(".")
                    manager_name = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else local_part
                if manager_name:
                    search_name = manager_name.lower()
                    for term in tp_terminals:
                        if term["id"] == HQ_PARENT_TERMINAL_ID:
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
                    if term["id"] == HQ_PARENT_TERMINAL_ID:
                        continue
                    key_name = str(term["name"]).lower()
                    if target == "sales team" and "carrier" in key_name:
                        continue
                    if target in key_name:
                        found_terminal_id = term["id"]
                        break

            # E. Safety net
            if found_terminal_id in ("", HQ_PARENT_TERMINAL_ID):
                found_terminal_id = ""
                for term in tp_terminals:
                    tn = str(term["name"]).lower()
                    if "admin" in tn and "ap only" in tn and term["id"] != HQ_PARENT_TERMINAL_ID:
                        found_terminal_id = term["id"]
                        break
                if not found_terminal_id:
                    found_terminal_id = HQ_ADMIN_FALLBACK_ID

        # === 2. GENERAL LOGIC ===
        else:
            for term in tp_terminals:
                if search_term in str(term["name"]).lower():
                    found_terminal_id = term["id"]
                    break

        row["Terminal"] = found_terminal_id

        # --- D. DETERMINE OFFICE PHONE ---
        # Maps Transport Pro terminal IDs to direct-dial office phone numbers.
        # Update these with your actual terminal ID -> phone number pairs.
        phone_map = {
            "YOUR_TERMINAL_ID_1": "5550000001",
            "YOUR_TERMINAL_ID_2": "5550000002",
        }
        row["Office Phone"] = phone_map.get(str(row["Terminal"]), "5550000000")

        # --- E. DETERMINE TEMPLATE ---
        row["Template"] = select_template(
            row["Reporting Branch"], row.get("Department", ""), row.get("Title", "")
        )

    return array

def update_onboarding_sheet(array: list[dict]) -> None:
    """Write *array* back to the Onboarding Form sheet, stripping computed columns."""
    if not array:
        return
    import pandas
    from config import get_spreadsheet, get_onboarding_worksheet
    spreadsheet = get_spreadsheet()
    aa_sheet = get_onboarding_worksheet(spreadsheet)
    df = pandas.DataFrame(array)
    df = df.drop(["Template","Terminal","Office Phone","State","Username"], axis=1)
    spreadsheet.values_clear("Onboarding Form!A2:P30")
    data = df.values.tolist()
    if data:
        aa_sheet.append_rows(values=data, table_range="A2:L2")
