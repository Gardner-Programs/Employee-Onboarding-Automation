"""Download the 8x8 phone-number report using session-cookie auth."""

from __future__ import annotations

import io
import os
import pickle
import time

import pandas as pd
import requests

from config import create_driver
from utils import login_8x8

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

COOKIE_FILE = os.path.join(OUTPUT_DIR, "8x8_cookies.pkl")

API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'Referer': 'https://admin.8x8.com/phone-numbers'
}


def _apply_cookies(session: requests.Session, cookies: list[dict]) -> None:
    """Clear *session* cookies and apply *cookies* from a Selenium driver."""
    session.cookies.clear()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])


def _are_cookies_expired(cookies: list[dict]) -> bool:
    """Return True if any cookie in *cookies* has a past expiry timestamp."""
    if not cookies:
        return True
    current_time = time.time()
    for cookie in cookies:
        if 'expiry' in cookie and cookie['expiry'] < current_time:
            print(f"Cookie {cookie['name']} has expired.")
            return True
    return False


def _get_fresh_cookies() -> list[dict] | None:
    """Log in via headless Selenium and return fresh session cookies."""
    with create_driver(headless=True, url="https://admin.8x8.com/users") as driver:
        if not login_8x8(driver):
            return None

        print("Login successful. Capturing session cookies...")
        time.sleep(5)
        cookies = driver.get_cookies()

        with open(COOKIE_FILE, "wb") as f:
            pickle.dump(cookies, f)
        print("Cookies saved to disk.")
        return cookies


def _get_session() -> requests.Session | None:
    """Return a requests Session with valid 8x8 cookies (loaded from disk or freshly obtained)."""
    cookies = None

    if os.path.exists(COOKIE_FILE):
        print("Found cached cookies. Checking expiration...")
        try:
            with open(COOKIE_FILE, "rb") as f:
                cookies = pickle.load(f)
            if _are_cookies_expired(cookies):
                print("Cached cookies are expired.")
                cookies = _get_fresh_cookies()
            else:
                print("Cached cookies look valid.")
        except Exception as e:
            print(f"Error reading cookie file: {e}")
            cookies = _get_fresh_cookies()
    else:
        print("No cached cookies found.")
        cookies = _get_fresh_cookies()

    if not cookies:
        return None

    s = requests.Session()
    _apply_cookies(s, cookies)
    s.headers.update(API_HEADERS)
    return s


def _request_with_retry(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """Make a GET request, retrying once with fresh cookies on 401/403."""
    response = session.get(url, **kwargs)
    if response.status_code in [401, 403]:
        print("Session rejected. Refreshing cookies...")
        cookies = _get_fresh_cookies()
        if cookies:
            _apply_cookies(session, cookies)
            response = session.get(url, **kwargs)
    response.raise_for_status()
    return response


def get_number_report() -> pd.DataFrame | None:
    """Download the 8x8 numbers report and return it as a DataFrame (also saved to CSV)."""
    s = _get_session()
    if not s:
        print("Failed to establish session.")
        return None

    start_url = "https://admin.8x8.com/cm-be/dids/api/v1/dids/export/numbers-report/start"
    print("Requesting report generation...")

    try:
        start_response = _request_with_retry(s, start_url, params={'filter': '', 'lang': 'en-US'})
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

    start_data = start_response.json()
    try:
        report_uuid = start_data['content'][0]['uuid']
    except (KeyError, IndexError):
        print("Failed to find UUID in response:", start_data)
        return None

    print(f"Report UUID: {report_uuid}")

    status_url = f"https://admin.8x8.com/cm-be/dids/api/v1/dids/export/numbers-report/{report_uuid}/status"

    for attempt in range(20):
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
        return None

    final_download_url = f"https://admin.8x8.com{download_url_path}"
    print(f"Downloading from: {final_download_url}")

    response = s.get(final_download_url)
    response.raise_for_status()

    csv_content = response.content.decode('utf-8')
    report_df = pd.read_csv(io.StringIO(csv_content))
    report_df.to_csv(os.path.join(OUTPUT_DIR, "8x8_number_report.csv"), index=False)
    print(report_df)
    return report_df


if __name__ == "__main__":
    get_number_report()
