"""Shared configuration: Firefox WebDriver setup, Selenium helpers, and Google Sheets access."""

from __future__ import annotations

import os
import gspread
from contextlib import contextmanager
from typing import Generator
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

def get_firefox_service_and_options(headless: bool = False) -> tuple:
    """Return a configured (FirefoxService, FirefoxOptions) pair."""
    firefox_service = FirefoxService()
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("-profile")
    firefox_options.add_argument(PROFILE_PATH)
    if headless:
        firefox_options.add_argument("-headless")
    return firefox_service, firefox_options


@contextmanager
def create_driver(
    headless: bool = False,
    url: str | None = None,
) -> Generator[webdriver.Firefox, None, None]:
    """Context manager that creates a Firefox WebDriver and guarantees cleanup.

    Args:
        headless: Run Firefox in headless mode (no visible window).
        url: Optional URL to navigate to immediately after launch.

    Yields:
        A fully initialised ``webdriver.Firefox`` instance.
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

def wait_and_click(driver: webdriver.Firefox, xpath: str, timeout: int = 20):
    """Wait for *xpath* to be clickable, click it, and return the element."""
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    element.click()
    return element


def wait_and_type(driver: webdriver.Firefox, xpath: str, text: str, timeout: int = 20):
    """Wait for *xpath* to be present in the DOM, send *text* to it, and return the element."""
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    element.send_keys(text)
    return element


def wait_visible(driver: webdriver.Firefox, xpath: str, timeout: int = 20):
    """Wait for *xpath* to be visible and return the element."""
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.XPATH, xpath))
    )


def wait_present(driver: webdriver.Firefox, xpath: str, timeout: int = 20):
    """Wait for *xpath* to be present in the DOM and return the element."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )


def wait_clickable(driver: webdriver.Firefox, xpath: str, timeout: int = 20):
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
