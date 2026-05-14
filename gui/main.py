"""
Account Creation Tool - GUI Version

Entry point for the application. Run this file or the packaged .exe to launch the GUI.

Usage:
    python main.py          (from source)
    AccountCreationTool.exe (packaged)

Requirements (source install):
    - Python 3.9+
    - Chrome browser installed
    - Access to shared Keys folder (service account JSON, .env)
    - wkhtmltopdf installed and on PATH (for PDF generation)

First-time setup for new admins:
    1. Ensure you have access to the shared Google Drive workspace tools folder
    2. Install dependencies: pip install -r requirements.txt
    3. Run: python main.py
    4. Enter your @company.com admin email and click Login
"""

import os
import sys

# When running as a frozen exe, sys._MEIPASS is the temp extraction dir.
# When running from source, use the normal directory layout.
if getattr(sys, 'frozen', False):
    _PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    _PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from gui.app import launch

if __name__ == "__main__":
    launch()
