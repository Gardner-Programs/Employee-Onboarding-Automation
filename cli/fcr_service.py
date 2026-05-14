"""Register phone numbers with the Free Caller Registry via Selenium automation."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from selenium.webdriver.support.ui import Select

from config import create_driver, wait_and_click, wait_and_type
from utils import get_caller_code, wait_for_verification_code

FCR_URL = "https://freecallerregistry.com/fcr/"

# --- FCR Form XPATHs ---
XPATH_EMAIL_INPUT = "/html/body/div[2]/div/div/div/form/div[2]/section[1]/div/div[2]/div/div/input"
XPATH_EMAIL_SUBMIT = "/html/body/div[2]/div/div/div/form/div[2]/section[1]/div/div[2]/div/input"
XPATH_CODE_INPUT = "/html/body/div[2]/div/div/div/form/div[2]/section[2]/div/div/div/input"
XPATH_CODE_SUBMIT = "/html/body/div[2]/div/div/div/form/div[2]/div/div/button[7]"


def numberRegister(numbers: list[str]) -> None:
    """Register *numbers* with the Free Caller Registry using browser automation.

    Authenticates via the FCR email verification flow, fills in company details,
    and submits a batch of phone numbers for registration.
    """
    with create_driver(url=FCR_URL) as driver:
        now = datetime.now() - timedelta(seconds=30)
        wait_and_type(driver, XPATH_EMAIL_INPUT, os.environ["EMAIL"])
        wait_and_click(driver, XPATH_EMAIL_SUBMIT)
        code = wait_for_verification_code(get_caller_code, now, max_attempts=10, poll_interval=6)
        if not code:
            print("Could not get verification code.")
            return

        time.sleep(2)
        wait_and_type(driver, XPATH_CODE_INPUT, code)
        time.sleep(2)
        wait_and_click(driver, XPATH_CODE_SUBMIT)

        # Fill in company registration details — replace with your organization's info
        wait_and_type(driver, '//*[@id="enterprise_company_name"]', "[Company] Logistics")
        driver.find_element("xpath", '//*[@id="enterprise_company_address_line_1"]').send_keys("YOUR COMPANY ADDRESS")
        driver.find_element("xpath", '//*[@id="enterprise_company_address_line_2"]').send_keys("")
        driver.find_element("xpath", '//*[@id="enterprise_company_address_city"]').send_keys("YOUR CITY")
        Select(driver.find_element("xpath", '//*[@id="enterprise_company_address_state"]')).select_by_visible_text("YOUR STATE")
        driver.find_element("xpath", '//*[@id="enterprise_company_address_zip"]').send_keys("YOUR ZIP")
        driver.find_element("xpath", '//*[@id="enterprise_company_url"]').send_keys("https://company.com/")
        driver.find_element("xpath", '//*[@id="enterprise_contact_name"]').send_keys("YOUR NAME")
        driver.find_element("xpath", '//*[@id="enterprise_contact_phone"]').send_keys("YOUR PHONE")
        Select(driver.find_element("xpath", '//*[@id="enterprise_category"]')).select_by_visible_text("Telemarketing")
        wait_and_click(driver, '//*[@id="nextButton1"]')
        time.sleep(2)

        for i in range(len(numbers)):
            wait_and_type(driver, f'//*[@id="enterprise_phone_{i}"]', numbers[i])

        wait_and_click(driver, '//*[@id="nextButton2"]')
        wait_and_click(driver, '//*[@id="enableCheckbox"]')
        wait_and_click(driver, '//*[@id="submitButton"]')
        time.sleep(2)
