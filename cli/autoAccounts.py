import os
import re
import sys
import time
from data_processing import get_processed_data, update_onboarding_sheet
from utils import sendEmail
from gmail_service import makeGmail, updateUserInfo
from pbx_8x8_service import make8x8
from tpp_service import makeTPP
from pdf_service import makeLoginSheets
from ad_service import makeAD
from fcr_service import numberRegister


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def pause():
    os.system("pause")


def notify(array):
    if not array:
        print("No users to notify HR about.")
        return
    email_body = """
    <div style="font-family: Arial, sans-serif; color: #333;">
        <p>Hello, please review the upcoming hires listed below and complete account creation according to their position/title. If you have any questions or concerns please reach out to the HR Team.</p>
        <hr>
    </div>
    """
    for hire in array:
        email_body += f"""
        <div style="margin-bottom: 20px;">
            <strong>Employee Name:</strong> {hire.get('Preferred First Name', '')} {hire.get('Preferred Last Name', '')}<br>
            <strong>Employee Email:</strong> {hire.get('Employee Email', '')}<br>
            <strong>Direct Line:</strong> {hire.get('Direct Line', '')}<br>
            <strong>Ext:</strong> {hire.get('Ext', '')}<br>
            <strong>Employee Title:</strong> {hire.get('Title', '')}<br>
            <strong>Employee Supervisor Email:</strong> {hire.get('Direct Report', '')}
        </div>
        """
    sendTo = "notifications@company.com,hr@company.com,admin@company.com,crm.admin@company.com"
    sendEmail(sendTo, "New Hire Accounts", email_body)
    print("Notification email sent successfully.")


def fcr_prompt():
    print("Enter phone numbers to register (comma-separated, or one per line).")
    print("Press Enter twice when done:")
    numbers = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        for n in line.split(","):
            cleaned = re.sub(r'\D', '', n.strip())
            if cleaned:
                numbers.append(cleaned)
    if numbers:
        print(f"Registering {len(numbers)} number(s)...")
        numberRegister(numbers)
        print("FCR Done")
    else:
        print("No numbers entered.")


def run_service(name, func, array):
    if not array:
        print("No users to process!")
        return
    try:
        func(array)
        print(f"{name} Done")
    except Exception as e:
        print(f"{name} Failed: {e}")


# Each menu entry: (key, label, handler)
# handler is either a callable(array) or a special string for unique flows
MENU_ITEMS = [
    ("1", "Run All Flows (Sheets -> Gmail -> 8x8 -> TPP -> Update -> AD)", "run_all"),
    ("2", "Generate Login Sheets",                lambda a: run_service("Login Sheets", makeLoginSheets, a)),
    ("3", "Create Gmail Accounts",                lambda a: run_service("Gmail", makeGmail, a)),
    ("4", "Setup 8x8 PBX Extensions",            lambda a: run_service("8x8", make8x8, a)),
    ("5", "Create Transport Pro (TPP) Accounts",  lambda a: run_service("TPP", makeTPP, a)),
    ("6", "Update Gmail Profiles & Signatures",   lambda a: run_service("Gmail Update", updateUserInfo, a)),
    ("7", "Send Notification Email to HR/QC",     lambda a: notify(a)),
    ("8", "Create AD Server Accounts",            lambda a: run_service("AD", makeAD, a)),
    ("9", "Register Numbers (Free Caller Registry)", lambda a: fcr_prompt()),
    ("U", "Update Onboarding Sheet",              lambda a: run_service("Sheet Update", update_onboarding_sheet, a)),
    ("R", "Reload Data from Source",              "reload"),
    ("Q", "Quit Application",                     "quit"),
]

RUN_ALL_STEPS = [
    ("Login Sheets", makeLoginSheets),
    ("Gmail", makeGmail),
    ("8x8", make8x8),
    ("TPP", makeTPP),
    ("Gmail Update", updateUserInfo),
    ("AD", makeAD),
]


def print_menu(array):
    clear_screen()
    print("=" * 60)
    print(" " * 15 + "AUTO ACCOUNTS ORCHESTRATOR")
    print("=" * 60)

    if array:
        print(f"Loaded {len(array)} records to process:")
        for u in array:
            name = f"{u.get('Preferred First Name', '')} {u.get('Preferred Last Name', '')}"
            print(f"  - {name} ({u.get('Employee Email', 'No Email')})")
    else:
        print("  [!] No users found in the Onboarding Form.")

    print("-" * 60)
    print(" Select an action to execute:")
    for key, label, _ in MENU_ITEMS:
        print(f"  {key}. {label}")
    print("=" * 60)


def start():
    array = []
    print("Loading data...")
    try:
        array = get_processed_data()
    except Exception as e:
        print(f"Error loading initial data: {e}")
        pause()

    while True:
        print_menu(array)
        choice = input(" > ").strip().upper()

        matched = None
        for key, label, handler in MENU_ITEMS:
            if choice == key:
                matched = handler
                break

        if matched is None:
            print("Invalid selection. Please choose a valid option.")
            time.sleep(1)
            continue

        if matched == "run_all":
            if not array:
                print("No users to process!")
                pause()
                continue
            for name, func in RUN_ALL_STEPS:
                run_service(name, func, array)
                pause()
        elif matched == "reload":
            print("Reloading data...")
            try:
                array = get_processed_data()
                print(f"Successfully loaded {len(array)} records.")
            except Exception as e:
                print(f"Error reloading data: {e}")
            pause()
        elif matched == "quit":
            clear_screen()
            print("Exiting...")
            sys.exit(0)
        else:
            matched(array)
            pause()


if __name__ == "__main__":
    start()
