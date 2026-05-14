"""
Local authenticator module for Account Creation GUI.
Authentication helper module with configurable admin user.

Other admins need:
  - Access to the shared Keys folder (service account JSON, .env)
  - Their @company.com email set as ADMIN_EMAIL in .env or at login
"""

import os
import sys
import requests
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, build_from_document
from google.oauth2 import service_account
from dotenv import load_dotenv

# --- FILE NAMES ---
KEY_FILE = "service-account-key.json"
SECRET_FILE = "credentials.json"
ENV_FILE = ".env"

# --- Frozen exe awareness ---
_IS_FROZEN = getattr(sys, 'frozen', False)

# --- DEFAULT PATHS (fallback if env vars are not set) ---
_BUNDLE_DIR = getattr(sys, '_MEIPASS', '')
_EXE_DIR = os.path.dirname(sys.executable) if _IS_FROZEN else ""

if _IS_FROZEN:
    # Frozen exe: bundled keys inside temp extraction, and Keys/ next to exe
    _BUNDLED_KEYS_DIR = os.path.join(_BUNDLE_DIR, "keys")
    _EXE_KEYS_DIR = os.path.join(_EXE_DIR, "Keys")
    _DEFAULT_KEYS_DIR = _BUNDLED_KEYS_DIR  # fallback is the bundle itself
else:
    # Running from source: repo-relative Keys/
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
    _REPO_ROOT = os.path.dirname(_PROJECT_ROOT)
    _BUNDLED_KEYS_DIR = ""
    _EXE_KEYS_DIR = ""
    _DEFAULT_KEYS_DIR = os.path.join(_REPO_ROOT, "Keys")

_LINUX_CREDS_DIR = "/home/ubuntu/.creds"

# Build ordered search list for credential directories
_KEYS_SEARCH_DIRS = [
    d for d in [
        _BUNDLED_KEYS_DIR,               # inside frozen exe bundle (highest priority)
        _EXE_KEYS_DIR,                   # Keys/ next to the exe
        os.getcwd(),                     # cwd
        _LINUX_CREDS_DIR,                # Linux deploy
        _DEFAULT_KEYS_DIR,               # repo-relative Keys/ (source only)
    ] if d
]

def _find_file(filename):
    """Search known directories for a file."""
    for d in _KEYS_SEARCH_DIRS:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            return path
    return os.path.join(_DEFAULT_KEYS_DIR, filename)  # last resort

# --- PATH LOGIC ---
env_override = os.environ.get("ENV_PATH", "").strip()
if env_override and os.path.exists(env_override):
    env_path = env_override
else:
    env_path = _find_file(ENV_FILE)

load_dotenv(dotenv_path=env_path)

# --- Resolve credential file paths ---
_env_key_path = os.environ.get("KEY_PATH", "").strip()
_env_secret_path = os.environ.get("SECRET_PATH", "").strip()

if _env_key_path and os.path.exists(_env_key_path):
    key_path = _env_key_path
    secret_path = _env_secret_path or os.path.join(os.path.dirname(_env_key_path), SECRET_FILE)
else:
    key_path = _find_file(KEY_FILE)
    secret_path = _find_file(SECRET_FILE)
    secret_path = os.path.join(_DEFAULT_KEYS_DIR, SECRET_FILE)


# --- Admin user (configurable at runtime) ---
_admin_email = os.environ.get("ADMIN_EMAIL", os.environ.get("EMAIL", ""))


def set_admin_email(email: str):
    """Set the admin email used for API delegation. Called from GUI login."""
    global _admin_email
    _admin_email = email


def get_admin_email() -> str:
    return _admin_email


def _default_user(user: str = None) -> str:
    """Return explicit user or fall back to configured admin email."""
    return user or _admin_email


# --- Google API Builders ---

def sheets_credentials():
    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
            "https://spreadsheets.google.com/feeds",
        ],
    )
    return credentials


def gmail_v1_api(user: str = None):
    user = _default_user(user)
    scopes = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://mail.google.com/",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.settings.basic",
        "https://www.googleapis.com/auth/gmail.settings.sharing",
    ]
    credentials = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)
    credentials_delegated = credentials.with_subject(user)
    return build("gmail", "v1", credentials=credentials_delegated, cache_discovery=False)


def admin_directory_v1_api(user: str = None):
    user = _default_user(user)
    scopes = [
        "https://www.googleapis.com/auth/admin.directory.user",
        "https://www.googleapis.com/auth/admin.directory.orgunit",
        "https://www.googleapis.com/auth/admin.directory.group",
        "https://www.googleapis.com/auth/admin.directory.device.mobile.readonly",
        "https://www.googleapis.com/auth/admin.directory.device.chromeos.readonly",
        "https://www.googleapis.com/auth/admin.directory.userschema",
    ]
    credentials = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)
    credentials_delegated = credentials.with_subject(user)
    return build("admin", "directory_v1", credentials=credentials_delegated, cache_discovery=False)


def drive_v3_api(user: str = None):
    user = _default_user(user)
    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
    ]
    credentials = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)
    credentials_delegated = credentials.with_subject(user)
    return build("drive", "v3", credentials=credentials_delegated, cache_discovery=False)


def drive_v2_api(user: str = None):
    user = _default_user(user)
    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
    ]
    credentials = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)
    credentials_delegated = credentials.with_subject(user)
    return build("drive", "v2", credentials=credentials_delegated, cache_discovery=False)


def calendar_v3_api(user: str = None):
    user = _default_user(user)
    credentials = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/calendar"]
    )
    credentials_delegated = credentials.with_subject(user)
    return build("calendar", "v3", credentials=credentials_delegated, cache_discovery=False)


def cloud_identity_v1_api(user: str = None):
    user = _default_user(user)
    credentials = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/cloud-identity.devices.readonly"]
    )
    credentials_delegated = credentials.with_subject(user)
    return build("cloudidentity", "v1", credentials=credentials_delegated, cache_discovery=False)


def custom_api_build(service_name: str, version: str, scopes: list, user: str = None):
    user = _default_user(user)
    credentials = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)
    credentials_delegated = credentials.with_subject(user)
    return build(service_name, version, credentials=credentials_delegated)


class GmailBatchAuthenticator:
    def __init__(self):
        self.base_creds = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://mail.google.com/",
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/gmail.settings.basic",
                "https://www.googleapis.com/auth/gmail.settings.sharing",
            ],
        )
        response = requests.get("https://gmail.googleapis.com/$discovery/rest?version=v1")
        self.discovery_doc = response.json()

    def get_service(self, user_email):
        delegated_creds = self.base_creds.with_subject(user_email)
        return build_from_document(self.discovery_doc, credentials=delegated_creds)
