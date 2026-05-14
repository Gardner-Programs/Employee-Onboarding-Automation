import os
import pandas
from unidecode import unidecode
from scripts.config import get_spreadsheet, get_tp_key_worksheet, get_onboarding_worksheet

# Valid email signature template keys (mirrored from scripts/email_templates.py CONFIGS).
# Only the key names are needed here — data_processing just checks membership.
# Update this set when new templates are added to email_templates.py.
VALID_TEMPLATES = {
    "branch_a", "branch_a_carrier_sales", "branch_a_expedite", "branch_a_track_trace",
    "branch_b", "branch_b_carrier_sales", "branch_b_driver_services", "branch_b_track_trace",
    "branch_c",
    "branch_d",
    "branch_e", "branch_e_carrier_sales", "branch_e_track_trace",
    "branch_f", "branch_f_carrier_sales",
    "branch_h",
    "branch_j", "branch_j_carrier_sales", "branch_j_track_trace",
    "corp_billing", "corp_claims", "corp_credit", "corp_fraud", "corp_hr", "corp_transportation",
    "default",
    "international", "international_carrier_sales", "international_track_trace",
    "office_template", "office_template_carrier_sales", "office_template_track_trace",
    "transport_dispatch",
}

# Maps Reporting Branch -> base template key from VALID_TEMPLATES.
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

# Set these in environment variables or replace with your actual Transport Pro terminal IDs
HQ_PARENT_TERMINAL_ID = os.environ.get("HQ_PARENT_TERMINAL_ID", "YOUR_PARENT_TERMINAL_ID")
HQ_ADMIN_FALLBACK_ID = os.environ.get("HQ_ADMIN_FALLBACK_ID", "YOUR_FALLBACK_TERMINAL_ID")

for _branch, _tmpl in BRANCH_MAP.items():
    if _tmpl not in VALID_TEMPLATES:
        print(f"WARNING: Branch '{_branch}' maps to template '{_tmpl}' which is missing from VALID_TEMPLATES")

def get_processed_data():
    spreadsheet = get_spreadsheet()
    tp_key = get_tp_key_worksheet(spreadsheet)

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
        row["Preferred First Name"] = str(row["Preferred First Name"]).replace("-", "").replace(" ", "")
        row["Employee Email"] = str(row["Employee Email"]).replace("-", "").replace(" ", "")

        if row["Reporting Branch"] in ["International City", "International Office"]:
            row["Reporting Branch"] = "International"
        if row["Physical Office"] in ["International City", "International Office"]:
            row["Physical Office"] = "International"

        if row["Reporting Branch"] == "Remote Field Office":
            row["Reporting Branch"] = "Branch A"
        if row["Physical Office"] == "Remote Field Office":
            row["Physical Office"] = "Branch A"

        for col in row:
            row[col] = unidecode(str(row[col]))

        row["Username"] = f"{row['Preferred First Name'].lower()}.{row['Preferred Last Name'].lower()}"

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

        found_terminal_id = ""
        physical_office = str(row["Physical Office"])
        search_term = physical_office.lower()

        if physical_office == "Branch A":
            direct_report_email = str(row["Direct Report"])
            manager_name = ""

            if "@" in direct_report_email:
                local_part = direct_report_email.split("@")[0]
                parts = local_part.replace("_", ".").split(".")
                if len(parts) >= 2:
                    manager_name = f"{parts[0]} {parts[1]}"
                else:
                    manager_name = local_part

            if manager_name:
                search_name = manager_name.lower()
                for term in tp_terminals:
                    if search_name in str(term["name"]).lower():
                        found_terminal_id = term["id"]
                        break

            if found_terminal_id == "":
                dept = str(row["Department"]).lower()
                title = str(row["Title"]).lower()
                target_terminal_name = ""

                if "carrier" in dept and "sales" in dept:
                    target_terminal_name = "Carrier Sales Team"
                elif "track" in dept:
                    target_terminal_name = "Track & Trace"
                elif "business development manager" in title:
                    target_terminal_name = "New Branch"
                elif "account" in dept or "sales" in dept:
                    target_terminal_name = "Sales Team"
                elif any(k in dept for k in ["hr", "it", "credit", "billing", "accounting", "admin", "recruiting", "marketing"]):
                    target_terminal_name = "ADMIN"
                else:
                    target_terminal_name = dept

                if target_terminal_name:
                    for term in tp_terminals:
                        key_name = str(term["name"]).lower()
                        target = target_terminal_name.lower()

                        if target == "sales team" and "carrier" in key_name:
                            continue

                        if target in key_name:
                            found_terminal_id = term["id"]
                            break

            if found_terminal_id == "" or found_terminal_id == HQ_PARENT_TERMINAL_ID:
                target_terminal_name = "ADMIN"
                for term in tp_terminals:
                    if "admin" in str(term["name"]).lower() and "ap only" in str(term["name"]).lower():
                        found_terminal_id = term["id"]
                        break
                if found_terminal_id == "":
                    found_terminal_id = HQ_ADMIN_FALLBACK_ID
        else:
            for term in tp_terminals:
                if search_term in str(term["name"]).lower():
                    found_terminal_id = term["id"]
                    break

        row["Terminal"] = found_terminal_id

        # Maps Transport Pro terminal IDs to direct-dial office phone numbers.
        # Update these with your actual terminal ID -> phone number pairs.
        phone_map = {
            "YOUR_TERMINAL_ID_1": "5550000001",
            "YOUR_TERMINAL_ID_2": "5550000002",
        }
        row["Office Phone"] = phone_map.get(str(row["Terminal"]), "5550000000")

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
            if any(kw in combined for kw in keywords) and corp_tmpl in VALID_TEMPLATES:
                selected = corp_tmpl
                break
        else:
            for keywords, suffix in ROLE_SUFFIXES:
                if any(kw in combined for kw in keywords):
                    candidate = base_template + suffix
                    if candidate in VALID_TEMPLATES:
                        selected = candidate
                    break

        row["Template"] = selected

    return array

def update_onboarding_sheet(array):
    if not array:
        return
    import pandas
    from scripts.config import get_spreadsheet, get_onboarding_worksheet
    spreadsheet = get_spreadsheet()
    aa_sheet = get_onboarding_worksheet(spreadsheet)
    df = pandas.DataFrame(array)
    df = df.drop(["Template","Terminal","Office Phone","State","Username"], axis=1)
    spreadsheet.values_clear("Onboarding Form!A2:P30")
    data = df.values.tolist()
    if data:
        aa_sheet.append_rows(values=data, table_range="A2:L2")
