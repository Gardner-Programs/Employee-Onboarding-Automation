import os
import re
import time
import pandas
import gspread_dataframe
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from config import (
    create_driver, DEFAULT_PASSWORD, get_spreadsheet, get_tp_key_worksheet,
    wait_and_click, wait_clickable,
)
from utils import login_tp, display_office_name

TRAINING_TERMINAL = "1145"

# --- TPP User Form XPATHs ---
TPP_URL = "https://cli.transportpro.net/#edit_systemUser"
XPATH_CITY_INPUT = "/html/body/div[5]/table/tbody/tr/td/div/div[2]/form/table[2]/tbody/tr[1]/td/div/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr/td[1]/table/tbody/tr[10]/td[2]/input"
XPATH_LOCATION_SELECT = "/html/body/div[5]/table/tbody/tr/td/div/div[2]/form/table[2]/tbody/tr[1]/td/div/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr/td[2]/table/tbody/tr[9]/td[2]/select"
XPATH_SUBMIT_BTN = "/html/body/div[5]/table/tbody/tr/td/div/div[2]/form/table[2]/tbody/tr[1]/td/div/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr/td[2]/table/tbody/tr[13]/td[2]/input"
XPATH_OK_BTN = "/html/body/div[5]/table/tbody/tr/td/div/div[2]/table[2]/tbody/tr/td[1]/table/tbody/tr/td[1]/img"

# Maintenance location values by branch
MAINTENANCE_MAP = {
    "Fort Wayne": "2", "Remote": "2", "Nashville": "2", "Pittsburgh": "2",
    "Panama": "8",
    "Indianapolis": "4",
    "Detroit": "9",
    "Detroit II": "9",
    "Columbia": "11",
    "Chicago": "3", "Tinley Park": "3", "Troyer": "3",
    "Orlando": "5",
    "Burr Ridge": "6",
    "Phoenix II": "7", "Phoenix": "7", "Phoenix I": "7",
    "Toledo": "10",
}
MAINTENANCE_DEFAULT = "2"


def _strip_terminal_name(name):
    """Strip number prefix and 'Office' suffix for fuzzy matching."""
    name = name.lstrip("-").strip()
    name = re.sub(r'^\d+\s*-\s*', '', name)
    name = re.sub(r'\s+Office$', '', name, flags=re.IGNORECASE)
    return name.strip().lower()


def get_terminals(html_string):
    """Parse the terminal dropdown from TPP page source."""
    spreadsheet = get_spreadsheet()
    tp_key = get_tp_key_worksheet(spreadsheet)
    soup = BeautifulSoup(html_string, 'html.parser')
    select_element = soup.find('select', {'name': 'terminalVisibility[]'})

    terminals_ordered = []
    flat_lookup = {}
    for option in select_element.find_all('option'):
        value = option.get('value')
        text = option.text.strip()
        if value:
            terminals_ordered.append({"id": value, "name": text})
            flat_lookup[value] = text

    # Sync to spreadsheet
    spreadsheet.values_clear(tp_key.title + "!A1:C1000")
    df = pandas.DataFrame([(t["id"], t["name"]) for t in terminals_ordered],
                          columns=["HTML Value", "Terminal Name"])
    gspread_dataframe.set_with_dataframe(tp_key, df.astype(str), 1, 1)

    # Build hierarchy: parent terminals and their sub-terminals
    hierarchy = {}
    current_parent_id = None
    for t in terminals_ordered:
        name = t["name"]
        tid = t["id"]
        if name.startswith("-"):
            if current_parent_id:
                hierarchy[current_parent_id]["children"].append(tid)
        else:
            current_parent_id = tid
            hierarchy[tid] = {"name": name, "children": []}

    return hierarchy, flat_lookup


def _match_office_to_parent(reporting_branch, hierarchy, flat_lookup):
    """Fuzzy match a reporting branch name to a parent terminal."""
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


def _find_best_sub_terminal(reporting_branch, parent_id, hierarchy, flat_lookup):
    """Find the best matching sub-terminal (child) for a reporting branch."""
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

    return best_child if best_child else children[0]


def _find_fw_parent(hierarchy):
    """Find the Fort Wayne parent terminal ID."""
    for parent_id, info in hierarchy.items():
        stripped = _strip_terminal_name(info["name"])
        if "fort wayne" in stripped:
            return parent_id, [parent_id] + info["children"]
    return None, []


def makeTPP(array):
    with create_driver(url=TPP_URL) as driver:
        if not login_tp(driver):
            return

        for user in array:
            driver.get(TPP_URL)
            wait_clickable(driver, '//*[@id="setupDispatchUser"]')

            driver.find_element("id", "setupDispatchUser").click()
            driver.find_element("id", "firstName").send_keys(user["First Name"])
            driver.find_element("id", "lastName").send_keys(user["Last Name"])
            driver.find_element("name", "title").send_keys(user["Title"])
            driver.find_element("name", "team").send_keys("Training")

            city_name = display_office_name(user["Reporting Branch"])
            driver.find_element("name", "city").send_keys(city_name)

            select = Select(driver.find_element("name", "state"))
            try:
                select.select_by_visible_text(user["State"])
            except:
                pass

            driver.find_element("name", "username").send_keys(user["Employee Email"])
            driver.find_element("name", "password").send_keys(DEFAULT_PASSWORD)
            driver.find_element("name", "cpassword").send_keys(DEFAULT_PASSWORD)
            driver.find_element("name", "email").send_keys(user["Employee Email"])
            driver.find_element("name", "officePhone").send_keys(user["Office Phone"])
            driver.find_element("name", "officePhoneExt").send_keys(user.get("Ext", ""))

            city = driver.find_element(By.XPATH, XPATH_CITY_INPUT).get_attribute("value")
            loc_select = Select(driver.find_element(By.XPATH, XPATH_LOCATION_SELECT))
            try:
                loc_select.select_by_visible_text(city)
            except:
                print(f"  WARNING: Location '{city}' not found in dropdown, skipping location selection")

            # Maintenance Location
            rb = user["Reporting Branch"]
            maint_val = MAINTENANCE_MAP.get(rb, MAINTENANCE_DEFAULT)
            Select(driver.find_element("name", "maintenanceLocation")).select_by_value(maint_val)

            # Dashboard
            title = str(user["Title"]).lower()
            dashboard_val = "11" if "track" in title else "9"
            Select(driver.find_element("name", "dashboard")).select_by_value(dashboard_val)

            # Parse live terminal hierarchy
            hierarchy, flat_lookup = get_terminals(driver.page_source)

            # Primary Terminal & Visibility
            is_fw = user.get("Physical Office", "") == "Fort Wayne"

            if is_fw:
                primary_terminal_id = user["Terminal"]
                _, fw_all_ids = _find_fw_parent(hierarchy)
                visibility_ids = set(fw_all_ids)
            else:
                parent_id, office_all_ids = _match_office_to_parent(rb, hierarchy, flat_lookup)
                if parent_id:
                    sub_id = _find_best_sub_terminal(rb, parent_id, hierarchy, flat_lookup)
                    if sub_id:
                        primary_terminal_id = sub_id
                    else:
                        print(f"  WARNING: No sub-terminals found under '{flat_lookup.get(parent_id, parent_id)}' for '{rb}', using parent terminal")
                        primary_terminal_id = parent_id
                    visibility_ids = set(office_all_ids)
                else:
                    print(f"  WARNING: Could not match '{rb}' to any terminal, using pre-computed terminal {user['Terminal']}")
                    primary_terminal_id = user["Terminal"]
                    visibility_ids = set()
                    for pid, info in hierarchy.items():
                        all_in_group = [pid] + info["children"]
                        if primary_terminal_id in all_in_group:
                            visibility_ids = set(all_in_group)
                            break

            visibility_ids.add(TRAINING_TERMINAL)

            Select(driver.find_element("name", "terminalId")).select_by_value(primary_terminal_id)
            primary_name = flat_lookup.get(primary_terminal_id, primary_terminal_id)
            print(f"  {user['Employee Email']}: Primary={primary_name} ({primary_terminal_id}), Visibility={len(visibility_ids)} terminals")

            # Set visibility (multi-select)
            vis_select = Select(driver.find_element("name", "terminalVisibility[]"))
            for option in vis_select.options:
                if option.get_attribute("value") in visibility_ids:
                    option.click()

            # Submit
            wait_and_click(driver, XPATH_SUBMIT_BTN)
            driver.find_element("name", "forceRenew").click()
            wait_and_click(driver, XPATH_OK_BTN)

            if user["Employee Email"] != array[-1]["Employee Email"]:
                driver.execute_script("window.open('');")
                time.sleep(1)
                driver.switch_to.window(driver.window_handles[-1])

        os.system("pause")
