import os
import re
import time
import base64
from datetime import datetime
from email.message import EmailMessage
from selenium.webdriver.common.by import By
from scripts.authenticator import gmail_v1_api, get_admin_email
from scripts.session_manager import save_session, load_session

# Callback for GUI interaction (pause dialog)
_pause_callback = None

def set_pause_callback(callback):
    global _pause_callback
    _pause_callback = callback

def _pause(message="Press continue to proceed..."):
    if _pause_callback:
        _pause_callback(message)
    else:
        print(f"PAUSE: {message} (no GUI callback set, continuing automatically)")


# --- Office Display Name ---

OFFICE_DISPLAY_MAP = {
    "Detroit II": "Detroit",
    "Phoenix II": "Phoenix",
    "Phoenix I": "Phoenix",
}


def display_office_name(name):
    return OFFICE_DISPLAY_MAP.get(name, name)


# --- Email Utilities ---

def sendEmail(to, subject, html_content):
    gmail_service = gmail_v1_api("notifications@company.com")
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.add_alternative(html_content, subtype='html')
    encoded_message = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
    gmail_service.users().messages().send(userId="me", body=encoded_message).execute()


# --- Verification Code Retrieval ---

def _get_code_from_gmail(snippet_match, parse_func):
    service = gmail_v1_api(get_admin_email())
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


def get_tp_code():
    def parse(snippet):
        search = re.search(r'process\.\s+(\d{6})', snippet)
        if search: return search.group(1)
        return None
    return _get_code_from_gmail("Transport Pro - Verification Code", parse)


def get_caller_code():
    def parse(snippet):
        search = re.findall(r'Free Caller Registry Verification Code: \[\d+', snippet)
        if search: return str(search[0]).replace("Free Caller Registry Verification Code: [", "")
        return None
    return _get_code_from_gmail("Free Caller Registry Verification Code:", parse)


def get_8x8_code():
    def parse(snippet):
        search = re.findall(r'login code: \d+', snippet)
        if search: return str(search[0]).replace("login code: ", "")
        return None
    return _get_code_from_gmail("Your 8x8 login code: ", parse)


# --- 2FA Verification Loop ---

def wait_for_verification_code(code_func, start_time, max_attempts=10, poll_interval=2):
    attempts = 0
    while attempts < max_attempts:
        code_data = code_func()
        if isinstance(code_data, tuple) and start_time < code_data[1]:
            return code_data[0]
        time.sleep(poll_interval)
        attempts += 1
    return None


# --- Selenium Login Helpers (with session restore) ---


def login_8x8(driver):
    """Log in to 8x8 Admin Console.

    Tries cached cookies first. If that fails, navigates to the login page
    and waits for the user to sign in manually, then saves the session.
    """
    # Try restoring session first
    if load_session(driver, "8x8", "https://admin.8x8.com/users"):
        time.sleep(3)
        if "admin.8x8.com" in driver.current_url and "login" not in driver.current_url.lower():
            print("8x8: Restored cached session")
            return True
        print("8x8: Cached session expired, logging in fresh...")

    # Navigate to login page and let the user sign in
    driver.get("https://admin.8x8.com/users")
    print("8x8: Please sign in to the 8x8 Admin Console in the browser window.")
    _pause("Sign in to 8x8 in the browser, then click Continue.")

    # Save session for next time
    save_session(driver, "8x8")
    print("8x8: Session saved")
    return True


def login_tp(driver):
    """Log in to Transport Pro.

    Tries cached cookies first. If that fails, navigates to the login page
    and waits for the user to sign in manually, then saves the session.
    """
    # Try restoring session first
    if load_session(driver, "tp", "https://cli.transportpro.net/"):
        time.sleep(3)
        if "transportpro.net" in driver.current_url:
            try:
                driver.find_element(By.XPATH, "/html/body/center/div/form/a[2]/img")
                print("TP: Cached session expired, logging in fresh...")
            except Exception:
                print("TP: Restored cached session")
                driver.get("https://cli.transportpro.net/#edit_systemUser")
                return True

    # Navigate to login page and let the user sign in
    driver.get("https://cli.transportpro.net/")
    print("TP: Please sign in to Transport Pro in the browser window.")
    _pause("Sign in to Transport Pro in the browser, then click Continue.")

    driver.get("https://cli.transportpro.net/#edit_systemUser")

    # Save session for next time
    save_session(driver, "tp")
    print("TP: Session saved")
    return True
