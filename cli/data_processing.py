import os
import sys
import pandas
from unidecode import unidecode
from config import get_spreadsheet, get_tp_key_worksheet, get_onboarding_worksheet

# Maps Reporting Branch -> base template key from email_templates.CONFIGS.
# Role-specific templates (e.g. branch_b_carrier_sales) are assigned manually after.
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
HQ_PARENT_TERMINAL_ID = "1003"
# Last-resort fallback when nothing else matches a real sub-terminal.
HQ_ADMIN_FALLBACK_ID = "1071"


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
        if row["Reporting Branch"] in ["International City", "International Office"]:
            row["Reporting Branch"] = "International"
        if row["Physical Office"] in ["International City", "International Office"]:
            row["Physical Office"] = "International"

        if row["Reporting Branch"] == "Remote Field Office":
            row["Reporting Branch"] = "Branch A"
        if row["Physical Office"] == "Remote Field Office":
            row["Physical Office"] = "Branch A"

        # 3. Unidecode all fields
        for col in row:
            row[col] = unidecode(str(row[col]))

        # --- A. GENERATE USERNAME ---
        row["Username"] = f"{row['Preferred First Name'].lower()}.{row['Preferred Last Name'].lower()}"

        # --- B. DETERMINE REGION ---
        state_map = {
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
        row["State"] = state_map.get(row["Physical Office"], "")

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
        phone_map = {
            "1057": "5550000001",
            "1065": "5550000001",
            "1015": "5550000002",
            "1029": "5550000003",
            "1035": "5550000004",
            "1107": "5550000005",
            "1126": "5550000006",
            "1069": "5550000002",
            "1068": "5550000002",
            "1129": "5550000002"
        }
        row["Office Phone"] = phone_map.get(str(row["Terminal"]), "5550000000")

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
