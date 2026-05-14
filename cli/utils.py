"""Shared utilities: email sending, 2FA code retrieval, and Selenium login helpers."""

from __future__ import annotations

import os
import re
import time
import base64
from collections.abc import Callable
from datetime import datetime
from email.message import EmailMessage
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from authenticator import gmail_v1_api
from config import wait_and_click, wait_and_type, wait_present


# --- Office Display Name ---
# ONLY for display/address fields (AD City, Gmail address, TPP city).
# Do NOT use for logic that distinguishes offices (templates, terminals, extensions, etc.).

OFFICE_DISPLAY_MAP = {
    "Branch C-II": "Branch C",
    "Branch G-II": "Branch G",
    "Branch G-I": "Branch G",
}

def display_office_name(name: str) -> str:
    """Convert office name for display fields only (e.g. AD City, Gmail address).

    Branch C-II and Branch G-II are distinct offices — this is ONLY for
    fields where the system expects 'Branch C' or 'Branch G' as a city name.
    """
    return OFFICE_DISPLAY_MAP.get(name, name)


# --- Email Utilities ---

def sendEmail(to: str, subject: str, html_content: str) -> None:
    """Send an HTML email via the onboarding Gmail account."""
    gmail_service = gmail_v1_api("formresponse@company.com")
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.add_alternative(html_content, subtype='html')
    encoded_message = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
    gmail_service.users().messages().send(userId="me", body=encoded_message).execute()


# --- Verification Code Retrieval ---

def _get_code_from_gmail(
    snippet_match: str,
    parse_func: Callable[[str], str | None],
) -> tuple[str, datetime] | str:
    service = gmail_v1_api(os.environ["EMAIL"])
    result = service.users().messages().list(userId="me", maxResults=5).execute()
    for x in result.get("messages", []):
        message = service.users().messages().get(userId="me", id=x["id"]).execute()
        snippet = message.get("snippet", "")
        if snippet_match in snippet:
            code = parse_func(snippet)
            if code:
                epoch = int(message["internalDate"]) / 1000
                msg_time = datetime.fromtimestamp(epoch)
                body = {'removeLabelIds': ['UNREAD']}
                try:
                    service.users().messages().modify(userId="me", id=x["id"], body=body).execute()
                except Exception as e:
                    print(f"Could not mark as read: {e}")
                return (code, msg_time)
    return "No code found."


def get_tp_code() -> tuple[str, datetime] | str:
    """Return the latest Transport Pro 2FA code and its timestamp from Gmail."""
    def parse(snippet):
        search = re.search(r'process\.\s+(\d{6})', snippet)
        if search: return search.group(1)
        return None
    return _get_code_from_gmail("Transport Pro - Verification Code", parse)


def get_caller_code() -> tuple[str, datetime] | str:
    """Return the latest Free Caller Registry verification code and timestamp from Gmail."""
    def parse(snippet):
        search = re.findall(r'Free Caller Registry Verification Code: \[\d+', snippet)
        if search: return str(search[0]).replace("Free Caller Registry Verification Code: [", "")
        return None
    return _get_code_from_gmail("Free Caller Registry Verification Code:", parse)


def get_8x8_code() -> tuple[str, datetime] | str:
    """Return the latest 8x8 login code and its timestamp from Gmail."""
    def parse(snippet):
        search = re.findall(r'login code: \d+', snippet)
        if search: return str(search[0]).replace("login code: ", "")
        return None
    return _get_code_from_gmail("Your 8x8 login code: ", parse)


# --- 2FA Verification Loop ---

def wait_for_verification_code(
    code_func: Callable,
    start_time: datetime,
    max_attempts: int = 10,
    poll_interval: int = 2,
) -> str | None:
    """Poll for a fresh verification code from email.

    Args:
        code_func: Function that returns ``(code, timestamp)`` or a non-tuple sentinel.
        start_time: Only accept codes whose timestamp is after this datetime.
        max_attempts: Maximum number of polling attempts before giving up.
        poll_interval: Seconds to wait between attempts.

    Returns:
        The code string, or None if max attempts are exceeded.
    """
    attempts = 0
    while attempts < max_attempts:
        code_data = code_func()
        if isinstance(code_data, tuple) and start_time < code_data[1]:
            return code_data[0]
        time.sleep(poll_interval)
        attempts += 1
    return None


# --- Selenium Login Helpers ---

# 8x8 XPATHs
_8X8_2FA_INPUT = "/html/body/main/div[1]/div/div[2]/form/div[2]/div/div[2]/input"
_8X8_2FA_SUBMIT = "/html/body/main/div[1]/div/div[2]/form/div[6]/button"

# TP XPATHs
_TP_LOGIN_IMG = "/html/body/center/div/form/a[2]/img"
_TP_EMAIL_INPUT = "/html/body/center/div/form/table/tbody/tr[3]/td/table/tbody/tr[1]/td[2]/input"
_TP_PASS_INPUT = "/html/body/center/div/form/table/tbody/tr[3]/td/table/tbody/tr[2]/td[2]/input"
_TP_LOGIN_BTN = "/html/body/center/div/form/table/tbody/tr[3]/td/table/tbody/tr[3]/td/input"
_TP_2FA_INPUT = "/html/body/center/div/form/sl-card/input"
_TP_2FA_SHADOW_HOST = "/html/body/center/div/form/sl-card/sl-input"
_TP_2FA_SHADOW_BTN = "/html/body/center/div/form/sl-card/sl-button[1]"


def login_8x8(driver: webdriver.Firefox) -> bool:
    """Perform 8x8 login with 2FA on an already-navigated driver.

    Returns True on success, False on failure (driver is quit on failure).
    """
    now = datetime.now()
    try:
        driver.find_element("id", "loginId").send_keys(os.environ["EMAIL"])
        driver.find_element("id", "loginId").send_keys(Keys.RETURN)
        time.sleep(2)
        driver.find_element("id", "password").send_keys(os.environ["PASSWORD"])
        driver.find_element("id", "password").send_keys(Keys.RETURN)

        code = wait_for_verification_code(get_8x8_code, now)
        if not code:
            print("Could not get 8x8 verification code.")
            driver.quit()
            return False

        time.sleep(2)
        wait_and_type(driver, _8X8_2FA_INPUT, code)
        time.sleep(2)
        wait_and_click(driver, _8X8_2FA_SUBMIT)
        return True
    except Exception:
        # May already be logged in via profile cookies
        time.sleep(5)
        return True


def login_tp(driver: webdriver.Firefox) -> bool:
    """Perform Transport Pro login with 2FA.

    Expects driver is already at the TP login page.
    Returns True on success, False on failure (driver is quit on failure).
    """
    now = datetime.now()
    try:
        wait_present(driver, _TP_LOGIN_IMG, timeout=10)
        wait_and_click(driver, _TP_LOGIN_IMG)
        wait_and_type(driver, _TP_EMAIL_INPUT, os.environ["EMAIL"])
        wait_and_type(driver, _TP_PASS_INPUT, os.environ["TPASSWORD"])
        wait_and_click(driver, _TP_LOGIN_BTN)

        code = wait_for_verification_code(get_tp_code, now)
        if not code:
            print("Could not get TP verification code.")
            driver.quit()
            return False

        try:
            driver.find_element(By.XPATH, _TP_2FA_INPUT).send_keys(code)
        except Exception:
            # Handle Shadow DOM variant
            shadow_host = wait_present(driver, _TP_2FA_SHADOW_HOST, timeout=10)
            shadow_root = shadow_host.shadow_root
            verification_input = WebDriverWait(shadow_root, 10).until(
                EC.visibility_of_element_located((By.ID, 'input'))
            )
            verification_input.send_keys(code)
            wait_and_click(driver, _TP_2FA_SHADOW_BTN)

        time.sleep(3)
        driver.get("https://cli.transportpro.net/#edit_systemUser")
        return True
    except Exception as e:
        print(f"TP login error: {e}")
        return True  # May already be logged in
