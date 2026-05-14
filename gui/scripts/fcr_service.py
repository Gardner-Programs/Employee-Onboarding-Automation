import os
import time
from datetime import datetime, timedelta
from selenium.webdriver.support.ui import Select

from scripts.config import create_driver, wait_and_click, wait_and_type, wait_visible
from scripts.utils import get_caller_code, wait_for_verification_code
from scripts.authenticator import get_admin_email
from scripts.session_manager import save_session, load_session

FCR_URL = "https://freecallerregistry.com/fcr/"

# --- FCR Form XPATHs ---
XPATH_EMAIL_INPUT = "/html/body/div[2]/div/div/div/form/div[2]/section[1]/div/div[2]/div/div/input"
XPATH_EMAIL_SUBMIT = "/html/body/div[2]/div/div/div/form/div[2]/section[1]/div/div[2]/div/input"
XPATH_CODE_INPUT = "/html/body/div[2]/div/div/div/form/div[2]/section[2]/div/div/div/input"
XPATH_CODE_SUBMIT = "/html/body/div[2]/div/div/div/form/div[2]/div/div/button[7]"


def numberRegister(numbers):
    with create_driver(url=FCR_URL) as driver:
        now = datetime.now() - timedelta(seconds=30)
        wait_and_type(driver, XPATH_EMAIL_INPUT, get_admin_email())
        wait_and_click(driver, XPATH_EMAIL_SUBMIT)
        code = wait_for_verification_code(get_caller_code, now, max_attempts=10, poll_interval=6)
        if not code:
            print("Could not get verification code.")
            return

        time.sleep(2)
        wait_and_type(driver, XPATH_CODE_INPUT, code)
        time.sleep(2)
        wait_and_click(driver, XPATH_CODE_SUBMIT)

        # Save session after successful auth
        save_session(driver, "fcr")

        # Wait for the registration form to fully load
        wait_visible(driver, '//*[@id="enterprise_company_name"]', timeout=30)
        time.sleep(1)

        # Replace with your company's registration details
        wait_and_type(driver, '//*[@id="enterprise_company_name"]', "[Company] Logistics")
        driver.find_element("xpath", '//*[@id="enterprise_company_address_line_1"]').send_keys("YOUR COMPANY ADDRESS")
        driver.find_element("xpath", '//*[@id="enterprise_company_address_line_2"]').send_keys("Suite 100")
        driver.find_element("xpath", '//*[@id="enterprise_company_address_city"]').send_keys("YOUR CITY")
        Select(driver.find_element("xpath", '//*[@id="enterprise_company_address_state"]')).select_by_visible_text("YOUR STATE")
        driver.find_element("xpath", '//*[@id="enterprise_company_address_zip"]').send_keys("00000")
        driver.find_element("xpath", '//*[@id="enterprise_company_url"]').send_keys("https://company.com/")
        driver.find_element("xpath", '//*[@id="enterprise_contact_name"]').send_keys("YOUR CONTACT NAME")
        driver.find_element("xpath", '//*[@id="enterprise_contact_phone"]').send_keys("555-555-0100")
        Select(driver.find_element("xpath", '//*[@id="enterprise_category"]')).select_by_visible_text("Telemarketing")
        wait_and_click(driver, '//*[@id="nextButton1"]')
        time.sleep(2)

        for i in range(len(numbers)):
            wait_and_type(driver, f'//*[@id="enterprise_phone_{i}"]', numbers[i])

        wait_and_click(driver, '//*[@id="nextButton2"]')
        wait_and_click(driver, '//*[@id="enableCheckbox"]')
        wait_and_click(driver, '//*[@id="submitButton"]')
        time.sleep(2)
