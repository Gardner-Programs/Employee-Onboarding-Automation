import os
import sys
import time
import gspread
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from scripts.authenticator import sheets_credentials

# --- Frozen exe helpers ---
IS_FROZEN = getattr(sys, 'frozen', False)
# Bundled read-only data lives here when frozen
BUNDLE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
# Writable app data dir (persists across runs)
APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AccountTool")

# --- Global Constants ---
DEFAULT_PASSWORD = os.environ.get("DEFAULT_EMP_PASSWORD", "Welcome1!")


# --- WebDriver Setup ---

def get_chrome_service_and_options(headless=False):
    chrome_service = ChromeService()
    chrome_options = ChromeOptions()
    # No --user-data-dir: fresh temp profile each time avoids org-managed
    # Chrome policies. Session persistence is handled by session_manager.py
    # which saves/restores cookies via pickle files.
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    if headless:
        chrome_options.add_argument("--headless=new")
    return chrome_service, chrome_options


@contextmanager
def create_driver(headless=False, url=None):
    """Context manager that creates a Chrome driver and guarantees cleanup."""
    service, options = get_chrome_service_and_options(headless=headless)
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    try:
        if url:
            driver.get(url)
        yield driver
    finally:
        driver.quit()


# --- Standardized Selenium Wait Helpers ---

def wait_and_click(driver, xpath, timeout=20):
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    element.click()
    return element


def wait_and_type(driver, xpath, text, timeout=20):
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    element.send_keys(text)
    return element


def wait_visible(driver, xpath, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.XPATH, xpath))
    )


def wait_present(driver, xpath, timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )


def wait_clickable(driver, xpath, timeout=20):
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
