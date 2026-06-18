"""Load, enrich, and write back onboarding form data from Google Sheets."""

from __future__ import annotations

import os

import pandas
from unidecode import unidecode

from scripts.config import get_onboarding_worksheet, get_spreadsheet, get_tp_key_worksheet
from scripts.enrichment import (
    clean_identifier,
    determine_region,
    generate_username,
    select_template,
    standardize_location,
)
from scripts.terminal_routing import determine_terminal

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
        row["Terminal"] = determine_terminal(
            str(row["Physical Office"]),
            row["Title"],
            row["Department"],
            row["Direct Report"],
            tp_terminals,
            HQ_PARENT_TERMINAL_ID,
            HQ_ADMIN_FALLBACK_ID,
        )

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

    from scripts.config import get_onboarding_worksheet, get_spreadsheet
    spreadsheet = get_spreadsheet()
    aa_sheet = get_onboarding_worksheet(spreadsheet)
    df = pandas.DataFrame(array)
    df = df.drop(["Template", "Terminal", "Office Phone", "State", "Username"], axis=1)
    spreadsheet.values_clear("Onboarding Form!A2:P30")
    data = df.values.tolist()
    if data:
        aa_sheet.append_rows(values=data, table_range="A2:L2")
