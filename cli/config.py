import os
import gspread
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from authenticator import sheets_credentials

# --- Global Constants ---
PROFILE_PATH = r"C:\Users\your_username\AppData\Roaming\Mozilla\Firefox\Profiles\selenium_profile"
DEFAULT_PASSWORD = os.environ["DEFAULT_EMP_PASSWORD"]


# --- WebDriver Setup ---

def get_firefox_service_and_options(headless=False):
    firefox_service = FirefoxService()
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("-profile")
    firefox_options.add_argument(PROFILE_PATH)
    if headless:
        firefox_options.add_argument("-headless")
    return firefox_service, firefox_options


@contextmanager
def create_driver(headless=False, url=None):
    """Context manager that creates a Firefox driver and guarantees cleanup.

    Usage:
        with create_driver(url="https://example.com") as driver:
            driver.find_element(...)
    """
    service, options = get_firefox_service_and_options(headless=headless)
    driver = webdriver.Firefox(service=service, options=options)
    driver.maximize_window()
    try:
        if url:
            driver.get(url)
        yield driver
    finally:
        driver.quit()


# --- Standardized Selenium Wait Helpers ---

def wait_and_click(driver, xpath, timeout=20):
    """Wait for element to be clickable, then click it."""
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    element.click()
    return element


def wait_and_type(driver, xpath, text, timeout=20):
    """Wait for element to be present, then type into it."""
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    element.send_keys(text)
    return element


def wait_visible(driver, xpath, timeout=20):
    """Wait for element to be visible and return it."""
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.XPATH, xpath))
    )


def wait_present(driver, xpath, timeout=20):
    """Wait for element to be present in DOM and return it."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )


def wait_clickable(driver, xpath, timeout=20):
    """Wait for element to be clickable and return it (without clicking)."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )


# --- Google Sheets ---

def get_spreadsheet():
    gc = gspread.authorize(sheets_credentials())
    return gc.open_by_key("YOUR_SPREADSHEET_KEY_HERE")


def get_tp_key_worksheet(spreadsheet=None):
    if not spreadsheet:
        spreadsheet = get_spreadsheet()
    return spreadsheet.worksheet("TP Key")


def get_onboarding_worksheet(spreadsheet=None):
    if not spreadsheet:
        spreadsheet = get_spreadsheet()
    return spreadsheet.worksheet("Onboarding Form")
