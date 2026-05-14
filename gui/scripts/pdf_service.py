import os
import sys
import tempfile
import pdfkit
from datetime import datetime
from googleapiclient.http import MediaFileUpload
from scripts.authenticator import drive_v3_api
from scripts.config import DEFAULT_PASSWORD, IS_FROZEN, BUNDLE_DIR

# When frozen, wkhtmltopdf is bundled inside the exe
if IS_FROZEN:
    _WKHTMLTOPDF_PATH = os.path.join(BUNDLE_DIR, 'wkhtmltopdf', 'wkhtmltopdf.exe')
    pdfkit_config = pdfkit.configuration(wkhtmltopdf=_WKHTMLTOPDF_PATH)
else:
    pdfkit_config = None  # use system PATH

# Shared Drive names
LOGIN_SHEETS_DRIVE = "Login Sheets"
SMITH_TEAMS_DRIVE = "New Hire Login Sheets - A. Smith Teams"

# Cache: (drive_id, folder_path) -> folder_id
_folder_cache = {}
_drive_cache = {}


def _get_drive_service():
    return drive_v3_api()


def _get_shared_drive_id(service, drive_name):
    if drive_name in _drive_cache:
        return _drive_cache[drive_name]
    result = service.drives().list(
        q=f"name='{drive_name}'", pageSize=100
    ).execute()
    drives = result.get("drives", [])
    for d in drives:
        if d["name"] == drive_name:
            _drive_cache[drive_name] = d["id"]
            return d["id"]
    raise ValueError(f"Shared drive '{drive_name}' not found")


def _find_folder(service, parent_id, folder_name, drive_id):
    q = (
        f"name='{folder_name}' and '{parent_id}' in parents "
        f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    result = service.files().list(
        q=q, spaces="drive", fields="files(id, name)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
        corpora="drive", driveId=drive_id
    ).execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(service, parent_id, folder_name, drive_id):
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(
        body=metadata, fields="id",
        supportsAllDrives=True
    ).execute()
    return folder["id"]


def _ensure_folder_path(service, drive_id, folder_names):
    cache_key = (drive_id, "/".join(folder_names))
    if cache_key in _folder_cache:
        return _folder_cache[cache_key]

    parent_id = drive_id
    for name in folder_names:
        folder_id = _find_folder(service, parent_id, name, drive_id)
        if not folder_id:
            folder_id = _create_folder(service, parent_id, name, drive_id)
        parent_id = folder_id

    _folder_cache[cache_key] = parent_id
    return parent_id


def _find_existing_file(service, folder_id, filename, drive_id):
    q = (
        f"name='{filename}' and '{folder_id}' in parents "
        f"and mimeType='application/pdf' and trashed=false"
    )
    result = service.files().list(
        q=q, spaces="drive", fields="files(id)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
        corpora="drive", driveId=drive_id
    ).execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _upload_pdf(service, folder_id, filename, pdf_path, drive_id):
    media = MediaFileUpload(pdf_path, mimetype="application/pdf")
    existing_id = _find_existing_file(service, folder_id, filename, drive_id)
    if existing_id:
        service.files().update(
            fileId=existing_id, media_body=media,
            supportsAllDrives=True
        ).execute()
        print(f"  Updated: {filename} -> {folder_id}")
    else:
        metadata = {
            "name": filename,
            "parents": [folder_id],
        }
        service.files().create(
            body=metadata, media_body=media, fields="id",
            supportsAllDrives=True
        ).execute()
        print(f"  Uploaded: {filename} -> {folder_id}")


def makeLoginSheets(array):
    service = _get_drive_service()
    login_drive_id = _get_shared_drive_id(service, LOGIN_SHEETS_DRIVE)
    smith_drive_id = _get_shared_drive_id(service, SMITH_TEAMS_DRIVE)

    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'quiet': '',
        'enable-local-file-access': '',
        'no-stop-slow-scripts': '',
    }

    for user in array:
        username = user["Username"]
        email = user["Employee Email"]

        if user.get("Needs Server Account") == "True":
            html = f"""<html><head><title>{username}</title></head><body style="font-family:arial;font-size:12pt;line-height:2;"><p style="text-align:center;"><img src="YOUR_LOGO_URL" alt="Logo"></P><p style="text-align:center;font-family:arial;font-size:16pt;"><b>Accounts &amp; Initial Logins</b></p><p><b><u>Server Access:</u></b></br> This login is for the server/computer when you sit down. You will click another user and then type the following in in order to login. The first login on a new computer may take several minutes for setup. </br><b>Computer Login: {username}</br>Password: {DEFAULT_PASSWORD}</b></p><p><b><u>Gmail Access:</u></b></br> This will be your login for Gmail as well as Google Chrome. Once you open up Google Chrome you will navigate to the small icon in the upper right corner that shows a head. Click that then log in. Once logged in a pop up window will come up, click &#34;I&#39;m In&#34; and then on the next one click &#34;Link Data&#34;. Once done you can then go to <a href="https://www.gmail.com/" target="_blank">gmail.com</a></br><b>Gmail Login: {email}</br>Password: {DEFAULT_PASSWORD}</b></p><p><b><u>TPP (Transport Pro) Access:</u></b></br> Navigate to <a href="http://cli.transportpro.net" target="_blank">cli.transportpro.net</a>. Once there you can click the system login button on the page and you enter your email and {DEFAULT_PASSWORD} as the password. After the first login you should be able to press login with Google to sign in immediately. </br><b>TPP Login: {email}</br>Password: {DEFAULT_PASSWORD}</b></p><p><b><u>8x8 Login:</u></b></br> A welcome email will be sent to your work email, click the button located there to create your first password. </p></body></html>"""
        else:
            html = f"""<html><head><title>{username}</title></head><body style="font-family:arial;font-size:12pt;line-height:2;"><p style="text-align:center;"><img src="YOUR_LOGO_URL" alt="Logo"></P><p style="text-align:center;font-family:arial;font-size:16pt;"><b>Accounts &amp; Initial Logins</b></p><p><b><u>Gmail Access:</u></b></br> This will be your login for Gmail as well as Google Chrome. Once you open up Google Chrome you will navigate to the small icon in the upper right corner that shows a head. Click that then log in. Once logged in a pop up window will come up, click &#34;I&#39;m In&#34; and then on the next one click &#34;Link Data&#34;. Once done you can then go to <a href="https://www.gmail.com/" target="_blank">gmail.com</a></br><b>Gmail Login: {email}</br>Password: {DEFAULT_PASSWORD}</b></p><p><b><u>TPP (Transport Pro) Access:</u></b></br> Navigate to <a href="http://cli.transportpro.net" target="_blank">cli.transportpro.net</a>. Once there you can click the system login button on the page and you enter your email and {DEFAULT_PASSWORD} as the password. After the first login you should be able to press login with Google to sign in immediately. </br><b>TPP Login: {email}</br>Password: {DEFAULT_PASSWORD}</b></p><p><b><u>8x8 Login:</u></b></br> A welcome email will be sent to your work email, click the button located there to create your first password. </p></body></html>"""

        if str(user["Physical Office"]).lower() in ("branch g-ii", "international"):
            html = f"""<html><head><title>{username}</title></head><body style="font-family:arial;font-size:12pt;line-height:2;"><p style="text-align:center;"><img src="YOUR_LOGO_URL" alt="Logo"></P><p style="text-align:center;font-family:arial;font-size:16pt;"><b>Accounts &amp; Initial Logins</b></p><p><b><u>Gmail Access:</u></b></br> This will be your login for Gmail as well as Google Chrome. Once you open up Google Chrome you will navigate to the small icon in the upper right corner that shows a head. Click that then log in. Once logged in a pop up window will come up, click &#34;I&#39;m In&#34; and then on the next one click &#34;Link Data&#34;. Once done you can then go to <a href="https://www.gmail.com/" target="_blank">gmail.com</a></br><b>Gmail Login: {email}</br>Password: {DEFAULT_PASSWORD}</b></p><p><b><u>TPP (Transport Pro) Access:</u></b></br> Navigate to <a href="http://cli.transportpro.net" target="_blank">cli.transportpro.net</a>. Once there you can click the system login button on the page and you enter your email and {DEFAULT_PASSWORD} as the password. After the first login you should be able to press login with Google to sign in immediately. </br><b>TPP Login: {email}</br>Password: {DEFAULT_PASSWORD}</b></p><p><b><u>8x8 Login:</u></b></br> A welcome email will be sent to your work email, click the button located there to create your first password. </p><p><b><u>Talent LMS Access:</u></b></br> Go to <a href="your-company.talentlms.com/dashboard" target="_blank">your company's LMS dashboard</a> and click login.</br><b>Talent LMS Login: {email}</br>Password: {DEFAULT_PASSWORD}</b></p></body></html>"""

        date_str = user.get("Effective Date", "")
        if date_str:
            try:
                date_str = datetime.strptime(date_str, "%Y-%m-%d").strftime("%m-%d-%Y")
            except:
                pass

        reporting = user["Reporting Branch"]
        physical = user["Physical Office"]
        pdf_name = f"{username}.pdf"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            pdfkit.from_string(html, tmp_path, options=options, configuration=pdfkit_config)

            def upload_to(drive_id, folder_path):
                folder_id = _ensure_folder_path(service, drive_id, folder_path)
                _upload_pdf(service, folder_id, pdf_name, tmp_path, drive_id)

            upload_to(login_drive_id, ["Master", date_str])

            if reporting in ["Branch B", "Branch E", "Branch I"]:
                upload_to(smith_drive_id, [physical, date_str])
                if "International" in [physical, reporting]:
                    upload_to(login_drive_id, ["International", date_str])
            elif "International" in [physical, reporting]:
                upload_to(login_drive_id, ["International", date_str])
            elif reporting == "Branch G-II":
                upload_to(login_drive_id, ["Branch G-II", date_str])
                if physical == "International":
                    upload_to(login_drive_id, ["International", date_str])
            elif physical == "Branch A":
                upload_to(login_drive_id, ["Branch A", date_str])
            else:
                upload_to(login_drive_id, [physical, date_str])
                upload_to(login_drive_id, [reporting, date_str])

            print(f"Done: {username}")
        finally:
            os.unlink(tmp_path)
