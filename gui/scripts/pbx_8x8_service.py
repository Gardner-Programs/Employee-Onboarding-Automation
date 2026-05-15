"""8x8 PBX account provisioning via browser automation for new hires."""

from __future__ import annotations

import io
import os
import time
import pandas
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver import Chrome

from scripts.config import (
    create_driver,
    wait_and_click, wait_and_type, wait_clickable, wait_visible, wait_present,
)
from scripts.utils import login_8x8
from scripts.fcr_service import numberRegister
from scripts.data_processing import update_onboarding_sheet

# --- Constants ---
# Extension numbers reserved for ring/hunt groups — new users are never assigned
# an extension from this set. Replace with your actual 8x8 ring group IDs.
RING_GROUPS = {1001, 1002, 1003}  # example IDs — update with your ring groups

DEFAULT_EXT_RANGE = (1000, 1999)
OFFICE_EXT_RANGES = {
    'Branch A': (1000,1999),
    'Remote Field Office': (1000,1999),
    'Remote': (1000,1999),
    'New Branch': (1000,1999),
    'Branch D': (2000,2499),
    'Branch F': (2500,2999),
    'Branch G': (4000,4499),
    'Branch G-II': (4500,4999),
    'Branch C': (5000,5499),
    'Branch H': (6000,6499),
    'Branch J': (7000,7499),
    'Branch B': (8000,8399),
    'Branch E': (8400,8599),
    'Branch I': (8600,8999),
    'Leadership Team': (9000,9499),
}

OFFICE_PHONE_PREFIX = {
    "Branch G-II": "1555",
}
DEFAULT_PHONE_PREFIX = "1555"

# --- 8x8 Admin XPATHs ---
USERS_URL = "https://admin.8x8.com/users"
CREATE_URL = "https://admin.8x8.com/users/user/create"
XPATH_ADD_USER_BTN = "/html/body/div[1]/div/div[3]/div[2]/div/div/div[2]/div[1]/div[2]/button"
XPATH_SITE_INPUT = "/html/body/div[1]/div/div[3]/div[2]/div/div/form/div[1]/div[2]/div[3]/div[1]/div/div[2]/div/div/div[1]/div/div[2]/input"
XPATH_USERNAME_INPUT = "/html/body/div[1]/div/div[3]/div[2]/div/div/form/div[1]/div[2]/div[2]/div[2]/span[1]/div/div/input"
XPATH_LICENSE_INPUT = "/html/body/div[1]/div/div[3]/div[2]/div/div/form/div[3]/div[2]/div[2]/div/div[2]/div/div/div[1]/div/div/div[1]/div/div[2]/input"
XPATH_RECORDING_DROPDOWN = "/html/body/div[1]/div/div[3]/div[2]/div/div/form/div[11]/div[2]/div[2]/div/div/div[2]/div/div/div[1]/div/div[2]/input"
XPATH_SAVE_BTN = "//button[contains(text(),'Save')]"

LICENSE_NAME = "X Series - X2-VOSVC0216-02-US"
FCR_BATCH_SIZE = 20

# Callback for GUI interaction (replaces os.system("pause"))
_pause_callback = None

def set_pause_callback(callback: object) -> None:
    """Register *callback* to be invoked when a Selenium flow needs user interaction."""
    global _pause_callback
    _pause_callback = callback

def _pause(message: str = "Press continue to proceed...") -> None:
    if _pause_callback:
        _pause_callback(message)
    else:
        print(f"PAUSE: {message} (no GUI callback set, continuing automatically)")


def get_number_report(driver: Chrome) -> tuple[list, list] | tuple[None, None]:
    """Download the 8x8 number report via API and return (available_numbers, available_extensions)."""
    print("Capturing session cookies...")
    selenium_cookies = driver.get_cookies()

    s = requests.Session()
    for cookie in selenium_cookies:
        s.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Referer': 'https://admin.8x8.com/phone-numbers'
    })

    start_url = "https://admin.8x8.com/cm-be/dids/api/v1/dids/export/numbers-report/start"
    print(f"Requesting report generation...")
    start_response = s.get(start_url, params={'filter': '', 'lang': 'en-US'})
    start_response.raise_for_status()

    report_uuid = start_response.json()['content'][0]['uuid']
    print(f"Report UUID: {report_uuid}")

    status_url = f"https://admin.8x8.com/cm-be/dids/api/v1/dids/export/numbers-report/{report_uuid}/status"

    for attempt in range(10):
        print(f"Checking report status (Attempt {attempt + 1})...")
        status_response = s.get(status_url)
        status_response.raise_for_status()
        status_data = status_response.json()

        report_status = status_data['content'][0]['status']
        print(f"-> Status is: {report_status}")

        if report_status == 'DONE':
            download_url_path = status_data['content'][0]['presignUrl']
            break

        time.sleep(5)
    else:
        print("Report generation timed out.")
        return None, None

    final_download_url = f"https://admin.8x8.com{download_url_path}"
    print(f"Downloading from: {final_download_url}")

    response = s.get(final_download_url)
    response.raise_for_status()

    csv_content = response.content.decode('utf-8')
    report_df = pandas.read_csv(io.StringIO(csv_content))
    print("\nSuccessfully loaded report.")

    phone_numbers = report_df[report_df["Number status"] == "Available"]["Phone number"].tolist()
    extensions = set(report_df["Extension"].dropna().tolist())
    available_set = (set(range(1, 10000)) - extensions) - RING_GROUPS
    formatted_available_list = [f'{num:04d}' for num in sorted(available_set)]

    return phone_numbers, formatted_available_list


def assign_numbers(office: str, available_numbers: list, available_extensions: list) -> tuple[str, str]:
    """Pop and return the best (extension, phone_number) pair for *office* from the available pools."""
    extension = ""
    number = ""

    low, high = OFFICE_EXT_RANGES.get(office, DEFAULT_EXT_RANGE)
    for ext in available_extensions:
        try:
            val = int(ext)
            if low <= val <= high:
                extension = ext
                available_extensions.remove(ext)
                break
        except (ValueError, TypeError):
            continue

    prefix = OFFICE_PHONE_PREFIX.get(office, DEFAULT_PHONE_PREFIX)
    for num in available_numbers:
        if str(num).startswith(prefix):
            available_numbers.remove(num)
            number = num
            break

    return extension, number


def make8x8(array: list[dict]) -> None:
    """Create 8x8 PBX extensions for all users in *array* that don't have one yet."""
    with create_driver(url=USERS_URL) as driver:
        if not login_8x8(driver):
            return

        available_numbers, available_extensions = get_number_report(driver)
        if not available_numbers:
            print("Failed to get 8x8 numbers")
            return

        driver.get(USERS_URL)
        wait_clickable(driver, XPATH_ADD_USER_BTN, timeout=120)

        for user in array:
            if user.get("Ext", "") != "":
                print(f"\n{user['Preferred First Name']} {user['Preferred Last Name']} already has an 8x8 ext is {user['Ext']}\n")
                continue

            time.sleep(1)
            driver.get(CREATE_URL)
            time.sleep(8)

            wait_present(driver, "//input[@name='basicInfo.firstName']").send_keys(user["Preferred First Name"])
            driver.find_element(By.NAME, "basicInfo.lastName").send_keys(user["Preferred Last Name"])
            driver.find_element(By.NAME, "basicInfo.primaryEmail").send_keys(user["Employee Email"])

            site = user["Reporting Branch"] + " Office"
            time.sleep(5)
            wait_and_type(driver, XPATH_SITE_INPUT, site)
            try:
                wait_and_click(driver, f"//*[text()='{site}']", timeout=10)
            except Exception:
                _pause(f"Could not auto-select site '{site}'. Please select it manually, then click Continue.")

            time.sleep(1.5)
            driver.find_element(By.NAME, "additionalInfo.jobTitle").send_keys(user["Title"])

            username_el = driver.find_element(By.XPATH, XPATH_USERNAME_INPUT)
            for _ in range(70):
                username_el.send_keys(Keys.BACK_SPACE)
            username_el.send_keys(user["Employee Email"])

            driver.find_element(By.NAME, "additionalInfo.department").send_keys(user["Department"])
            time.sleep(.5)

            try:
                wait_and_type(driver, XPATH_LICENSE_INPUT, LICENSE_NAME)
                wait_and_click(driver, f"//*[text()='{LICENSE_NAME}']")
            except Exception:
                _pause(f"Could not auto-select license. Please select '{LICENSE_NAME}' manually, then click Continue.")
                driver.find_element(By.CSS_SELECTOR, "#react-select-8-input").send_keys(LICENSE_NAME)
                wait_and_click(driver, f"//*[text()='{LICENSE_NAME}']")

            time.sleep(4)
            wait_and_click(driver, "//*[text()='Call recording settings']")
            wait_and_click(driver, "//*[text()='Record all calls for this user']")
            time.sleep(2)
            wait_and_type(driver, XPATH_RECORDING_DROPDOWN, "Neither")
            wait_and_click(driver, "//*[text()='Neither']")

            time.sleep(2)
            wait_and_click(driver, "//*[text()='Single Sign-On (SSO)']")
            time.sleep(2)
            driver.find_element(By.NAME, "ssoPolicies.googleId").send_keys(user["Employee Email"])
            wait_and_click(driver, "//*[text()='Voice basic settings']")

            ext, num = assign_numbers(user["Reporting Branch"], available_numbers, available_extensions)
            number = str(num)
            formatted_number = f"+{number[0]} {number[1:4]}-{number[4:7]}-{number[7:]}"

            time.sleep(2)
            wait_visible(driver, '//*[@id="react-select-9-input"]').send_keys(formatted_number)
            wait_and_click(driver, f"//*[text()='{formatted_number}']")
            user["Direct Line"] = formatted_number

            ext_field = driver.find_element(By.NAME, "voiceBasicSettings.extensionNumber")
            ext_field.send_keys(Keys.CONTROL + "a")
            ext_field.send_keys(ext)
            user["Ext"] = ext

            time.sleep(3)
            driver.execute_script("""
                var scrollable = document.querySelector('[data-id="form-container"]') ||
                    document.querySelector('.form-container') ||
                    document.querySelector('form');
                if (scrollable) {
                    scrollable.scrollTop = scrollable.scrollHeight;
                } else {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            """)
            time.sleep(3)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

            try:
                sms_section = driver.find_element(By.XPATH, "//div[@data-id='sms' and @data-test-id='form-section']")
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", sms_section)
                time.sleep(2)
                sms_header = sms_section.find_element(By.XPATH, "./div[@class and contains(@class,'form-section-header-container')]")
                driver.execute_script("arguments[0].click();", sms_header)
                time.sleep(3)
                sms_toggles = sms_section.find_elements(By.XPATH, ".//input[@type='checkbox' and @role='switch']")
                for sms_toggle in sms_toggles:
                    if not sms_toggle.is_selected():
                        label = sms_toggle.find_element(By.XPATH, "./ancestor::label")
                        driver.execute_script("arguments[0].click();", label)
                if not sms_toggles:
                    _pause("No SMS toggles found. Please enable SMS manually, then click Continue.")
            except Exception:
                _pause("Could not find SMS section. Please enable SMS manually, then click Continue.")
            time.sleep(1)

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            try:
                save_btn = driver.find_element(By.XPATH, XPATH_SAVE_BTN)
                driver.execute_script("arguments[0].scrollIntoView(true);", save_btn)
                time.sleep(1)
                save_btn.click()
            except Exception:
                _pause("Could not find save button. Please save manually, then click Continue.")

            update_onboarding_sheet(array)

            if user["Employee Email"] != array[-1]["Employee Email"]:
                driver.execute_script("window.open('');")
                time.sleep(1)
                driver.switch_to.window(driver.window_handles[-1])

        _pause("8x8 account creation complete. Review results, then click Continue.")

    # Register numbers with FCR in batches
    numbers_list = [user["Direct Line"][1:] for user in array if user.get("Direct Line")]
    for i in range(0, len(numbers_list), FCR_BATCH_SIZE):
        numberRegister(numbers_list[i:i + FCR_BATCH_SIZE])
