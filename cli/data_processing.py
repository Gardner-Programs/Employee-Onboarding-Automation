import os
import sys
import pandas
from unidecode import unidecode
from config import get_spreadsheet, get_tp_key_worksheet, get_onboarding_worksheet

# Maps Reporting Branch -> base template key from EmailTemplates.CONFIGS.
# Role-specific templates (e.g. chicago_carrier_sales) are assigned manually after.
BRANCH_MAP = {
    "Chicago": "chicago",
    "Detroit": "detroit",
    "Detroit II": "detroit",
    "Indianapolis": "indianapolis",
    "Nashville": "nashville",
    "Orlando": "orlando",
    "Panama": "panama",
    "Phoenix": "default",
    "Phoenix I": "default",
    "Phoenix II": "phoenix_ii",
    "Pittsburgh": "pittsburgh",
    "Tinley Park": "chicago",
    "Toledo": "toledo",
}
BRANCH_MAP_DEFAULT = "fort_wayne"

# --- Fort Wayne sub-terminal routing ---
# Title-keyword -> target terminal name. Title routing wins over manager match,
# so a Sr. BDM whose manager has their own terminal still lands in New Branch.
FW_TITLE_ROUTING = [
    ("business development manager", "New Branch"),
]

# Department-keyword tuples -> target terminal name.
FW_DEPT_ROUTING = [
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

# FW parent terminal — must never be assigned as a primary terminal.
FW_PARENT_TERMINAL_ID = "1003"
# Last-resort fallback when nothing else matches a real sub-terminal.
FW_ADMIN_FALLBACK_ID = "1071"


def get_processed_data():
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
        row["Preferred First Name"] = str(row["Preferred First Name"]).replace("-", "").replace(" ", "")
        row["Employee Email"] = str(row["Employee Email"]).replace("-", "").replace(" ", "")

        # 2. Handle Location Standardization
        if row["Reporting Branch"] in ["Panama City, PA", "Panama City, Panama"]:
            row["Reporting Branch"] = "Panama"
        if row["Physical Office"] in ["Panama City, PA", "Panama City, Panama"]:
            row["Physical Office"] = "Panama"

        if row["Reporting Branch"] == "Remote Field Office":
            row["Reporting Branch"] = "Fort Wayne"
        if row["Physical Office"] == "Remote Field Office":
            row["Physical Office"] = "Fort Wayne"

        # 3. Unidecode all fields
        for col in row:
            row[col] = unidecode(str(row[col]))

        # --- A. GENERATE USERNAME ---
        row["Username"] = f"{row['Preferred First Name'].lower()}.{row['Preferred Last Name'].lower()}"

        # --- B. DETERMINE STATE ---
        state_map = {
            "Chicago": "Illinois",
            "Indianapolis": "Indiana",
            "Fort Wayne": "Indiana",
            "Orlando": "Florida",
            "Tinley Park": "Illinois",
            "Phoenix": "Arizona",
            "Phoenix II": "Arizona",
            "Remote": "Indiana",
            "Toledo": "Ohio",
            "Nashville": "Tennessee",
            "Phoenix I": "Arizona",
            "Panama": "Indiana",
            "Panama City, PA": "Indiana",
            "Detroit": "Michigan",
            "Detroit II": "Michigan",
            "New Branch": "Indiana",
            "Pittsburgh": "Pennsylvania"
        }
        row["State"] = state_map.get(row["Physical Office"], "")

        # --- C. DETERMINE TERMINAL ---
        found_terminal_id = ""
        physical_office = str(row["Physical Office"])
        search_term = physical_office.lower()

        # === 1. FORT WAYNE SPECIFIC LOGIC ===
        if physical_office == "Fort Wayne":
            title_lower = str(row["Title"]).lower()
            dept_lower = str(row["Department"]).lower()
            target_terminal_name = ""

            # A. Title-based routing
            for keyword, target in FW_TITLE_ROUTING:
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
                        if term["id"] == FW_PARENT_TERMINAL_ID:
                            continue
                        if search_name in str(term["name"]).lower():
                            found_terminal_id = term["id"]
                            break

            # C. Department fallback
            if not found_terminal_id and not target_terminal_name:
                for keywords, target in FW_DEPT_ROUTING:
                    if all(kw in dept_lower for kw in keywords):
                        target_terminal_name = target
                        break
                if not target_terminal_name:
                    target_terminal_name = dept_lower

            # D. Resolve target terminal name -> ID
            if target_terminal_name and not found_terminal_id:
                target = target_terminal_name.lower()
                for term in tp_terminals:
                    if term["id"] == FW_PARENT_TERMINAL_ID:
                        continue
                    key_name = str(term["name"]).lower()
                    if target == "sales team" and "carrier" in key_name:
                        continue
                    if target in key_name:
                        found_terminal_id = term["id"]
                        break

            # E. Safety net
            if found_terminal_id in ("", FW_PARENT_TERMINAL_ID):
                found_terminal_id = ""
                for term in tp_terminals:
                    tn = str(term["name"]).lower()
                    if "admin" in tn and "ap only" in tn and term["id"] != FW_PARENT_TERMINAL_ID:
                        found_terminal_id = term["id"]
                        break
                if not found_terminal_id:
                    found_terminal_id = FW_ADMIN_FALLBACK_ID

        # === 2. GENERAL LOGIC ===
        else:
            for term in tp_terminals:
                if search_term in str(term["name"]).lower():
                    found_terminal_id = term["id"]
                    break

        row["Terminal"] = found_terminal_id

        # --- D. DETERMINE OFFICE PHONE ---
        phone_map = {
            "1057": "4805060355",
            "1065": "4805060355",
            "1015": "3123007447",
            "1029": "3133346600",
            "1035": "2609180254",
            "1107": "3133853745",
            "1126": "2602046180",
            "1069": "3123007447",
            "1068": "3123007447",
            "1129": "3123007447"
        }
        row["Office Phone"] = phone_map.get(str(row["Terminal"]), "2602084500")

        # --- E. DETERMINE TEMPLATE ---
        base_template = BRANCH_MAP.get(row["Reporting Branch"], BRANCH_MAP_DEFAULT)

        dept_lower = str(row.get("Department", "")).lower()
        title_lower = str(row.get("Title", "")).lower()
        combined = dept_lower + " " + title_lower

        ROLE_SUFFIXES = [
            (["carrier sales", "carrier rep", "carrier team lead", "carrier sales manager"], "_carrier_sales"),
            (["track and trace", "track & trace", "tracking"], "_track_trace"),
            (["driver service"], "_driver_services"),
            (["expedite"], "_expedite"),
        ]

        CORP_TEMPLATES = [
            (["billing", "settlements", "pay status"], "corp_billing"),
            (["credit"], "corp_credit"),
            (["claims"], "corp_claims"),
            (["human resources", " hr "], "corp_hr"),
            (["recruiting", "talent acquisition"], "corp_hr"),
            (["fraud"], "corp_fraud"),
            (["transportation"], "corp_transportation"),
        ]

        selected = base_template
        for keywords, corp_tmpl in CORP_TEMPLATES:
            if any(kw in combined for kw in keywords):
                selected = corp_tmpl
                break
        else:
            for keywords, suffix in ROLE_SUFFIXES:
                if any(kw in combined for kw in keywords):
                    candidate = base_template + suffix
                    selected = candidate
                    break

        row["Template"] = selected

    return array

def update_onboarding_sheet(array):
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
