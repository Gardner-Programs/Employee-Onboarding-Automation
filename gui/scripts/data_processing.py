import os
import pandas
from unidecode import unidecode
from scripts.config import get_spreadsheet, get_tp_key_worksheet, get_onboarding_worksheet

# Valid email signature template keys (mirrored from Email_Signatures/scripts/EmailTemplates.py CONFIGS).
# Only the key names are needed here — data_processing just checks membership.
# Update this set when new templates are added to EmailTemplates.py.
VALID_TEMPLATES = {
    "chicago", "chicago_carrier_sales", "chicago_driver_services", "chicago_track_trace",
    "corp_billing", "corp_claims", "corp_credit", "corp_fraud", "corp_hr", "corp_transportation",
    "default", "detroit",
    "fort_wayne", "fort_wayne_carrier_sales", "fort_wayne_expedite", "fort_wayne_track_trace",
    "indianapolis",
    "nashville", "nashville_carrier_sales",
    "orlando", "orlando_carrier_sales", "orlando_track_trace",
    "panama", "panama_carrier_sales", "panama_track_trace",
    "phoenix_ii", "phoenix_ii_carrier_sales", "phoenix_ii_track_trace",
    "pittsburgh", "pittsburgh_carrier_sales", "pittsburgh_track_trace",
    "toledo",
    "transport_dispatch",
}

# Maps Reporting Branch -> base template key from VALID_TEMPLATES.
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

        if row["Reporting Branch"] in ["Panama City, PA", "Panama City, Panama"]:
            row["Reporting Branch"] = "Panama"
        if row["Physical Office"] in ["Panama City, PA", "Panama City, Panama"]:
            row["Physical Office"] = "Panama"

        if row["Reporting Branch"] == "Remote Field Office":
            row["Reporting Branch"] = "Fort Wayne"
        if row["Physical Office"] == "Remote Field Office":
            row["Physical Office"] = "Fort Wayne"

        for col in row:
            row[col] = unidecode(str(row[col]))

        row["Username"] = f"{row['Preferred First Name'].lower()}.{row['Preferred Last Name'].lower()}"

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

        found_terminal_id = ""
        physical_office = str(row["Physical Office"])
        search_term = physical_office.lower()

        if physical_office == "Fort Wayne":
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

            if found_terminal_id == "" or found_terminal_id == "1003":
                target_terminal_name = "ADMIN"
                for term in tp_terminals:
                    if "admin" in str(term["name"]).lower() and "ap only" in str(term["name"]).lower():
                        found_terminal_id = term["id"]
                        break
                if found_terminal_id == "":
                    found_terminal_id = "1071"
        else:
            for term in tp_terminals:
                if search_term in str(term["name"]).lower():
                    found_terminal_id = term["id"]
                    break

        row["Terminal"] = found_terminal_id

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
