"""Shared configuration: Chrome WebDriver setup, Selenium helpers, and Google Sheets access."""

from __future__ import annotations

import os
import sys
import gspread
from collections.abc import Generator
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
BUNDLE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AccountTool")

# --- Global Constants ---
DEFAULT_PASSWORD = os.environ["DEFAULT_EMP_PASSWORD"]


# --- WebDriver Setup ---

def get_chrome_service_and_options(headless: bool = False) -> tuple[ChromeService, ChromeOptions]:
    """Return a configured (ChromeService, ChromeOptions) pair.

    Uses a fresh temp profile each time — session persistence is handled by
    session_manager.py which saves/restores cookies via pickle files.
    """
    chrome_service = ChromeService()
    chrome_options = ChromeOptions()
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    if headless:
        chrome_options.add_argument("--headless=new")
    return chrome_service, chrome_options


@contextmanager
def create_driver(
    headless: bool = False,
    url: str | None = None,
) -> Generator[webdriver.Chrome, None, None]:
    """Context manager that creates a Chrome WebDriver and guarantees cleanup.

    Args:
        headless: Run Chrome in headless mode (no visible window).
        url: Optional URL to navigate to immediately after launch.

    Yields:
        A fully initialised ``webdriver.Chrome`` instance.
    """
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

def wait_and_click(driver: webdriver.Chrome, xpath: str, timeout: int = 20):
    """Wait for *xpath* to be clickable, click it, and return the element."""
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    element.click()
    return element


def wait_and_type(driver: webdriver.Chrome, xpath: str, text: str, timeout: int = 20):
    """Wait for *xpath* to be present in the DOM, send *text* to it, and return the element."""
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    element.send_keys(text)
    return element


def wait_visible(driver: webdriver.Chrome, xpath: str, timeout: int = 20):
    """Wait for *xpath* to be visible and return the element."""
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.XPATH, xpath))
    )


def wait_present(driver: webdriver.Chrome, xpath: str, timeout: int = 20):
    """Wait for *xpath* to be present in the DOM and return the element."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )


def wait_clickable(driver: webdriver.Chrome, xpath: str, timeout: int = 20):
    """Wait for *xpath* to be clickable and return it (without clicking)."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )


# --- Google Sheets ---

def get_spreadsheet() -> gspread.Spreadsheet:
    """Return the main onboarding spreadsheet using service-account credentials."""
    gc = gspread.authorize(sheets_credentials())
    return gc.open_by_key("YOUR_SPREADSHEET_KEY_HERE")


def get_tp_key_worksheet(spreadsheet: gspread.Spreadsheet | None = None) -> gspread.Worksheet:
    """Return the 'TP Key' worksheet, opening the spreadsheet if not provided."""
    if not spreadsheet:
        spreadsheet = get_spreadsheet()
    return spreadsheet.worksheet("TP Key")


def get_onboarding_worksheet(spreadsheet: gspread.Spreadsheet | None = None) -> gspread.Worksheet:
    """Return the 'Onboarding Form' worksheet, opening the spreadsheet if not provided."""
    if not spreadsheet:
        spreadsheet = get_spreadsheet()
    return spreadsheet.worksheet("Onboarding Form")
