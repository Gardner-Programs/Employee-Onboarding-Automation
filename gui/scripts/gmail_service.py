import os
import sys
import base64
from scripts.authenticator import admin_directory_v1_api
from googleapiclient.errors import HttpError
from scripts.config import DEFAULT_PASSWORD, IS_FROZEN, BUNDLE_DIR
from scripts.utils import display_office_name

def get_org_unit(service, branch_name):
    if not branch_name:
        return "/"
    try:
        results = service.orgunits().list(customerId='my_customer', type='all').execute()
        org_units = results.get('organizationUnits', [])
        for ou in org_units:
            if ou.get('name', '') == branch_name:
                return ou.get('orgUnitPath')

        new_ou = {
            "name": branch_name,
            "description": f"Auto-created OU for {branch_name}",
            "parentOrgUnitPath": "/All Sites"
        }
        created_ou = service.orgunits().insert(customerId='my_customer', body=new_ou).execute()
        print(f"Created new Organizational Unit: {created_ou.get('orgUnitPath')}")
        return created_ou.get('orgUnitPath')

    except Exception as e:
        print(f"Warning: Could not resolve org unit for '{branch_name}'. Defaulting to root (/). Error: {e}")
        return "/"

def makeGmail(array):
    service = admin_directory_v1_api()
    for user in array:
        branch = user.get("Reporting Branch", "")
        orgUnit = get_org_unit(service, branch)

        person = {
            "primaryEmail": user["Employee Email"],
            "name": {
                "givenName": user["Preferred First Name"],
                "familyName": user["Preferred Last Name"],
                "fullName": user["Preferred First Name"] + " " + user["Preferred Last Name"]
            },
            "orgUnitPath": orgUnit,
            "password": DEFAULT_PASSWORD,
            "changePasswordAtNextLogin": "true",
            "relations": [{"value": user["Direct Report"], "type": "manager"}]
        }

        try:
            results = service.users().insert(body=person).execute()
        except HttpError as e:
            username = user["Preferred First Name"] + " " + user["Preferred Last Name"]
            err = str(e._get_reason())
            print("Error with " + username + " " + err)

def updateUserInfo(array):
    service = admin_directory_v1_api()
    for user in array:
        try:
            key = str(user["Employee Email"])
            title = str(user["Title"])
            department = str(user["Department"])
            address = display_office_name(user["Reporting Branch"])

            phone = str(user["Ext"])
            mobile = str(user.get("Direct Line", ""))

            data = {
                'organizations': [{'title': title, 'primary': True, 'customType': '', 'department': department}],
                'addresses': [{'type': 'home', 'formatted': address}],
                'phones': [{'value': phone, 'type': 'work'}, {'value': mobile, 'type': 'mobile'}],
                "customSchemas": [{"Signature_Info": {"Extension": phone, "Template": str(user.get("Template", "default")), "Title": title, "Location": address}}]
            }
            results = service.users().update(userKey=key, body=data).execute()

            try:
                # Example entries — replace with actual employee group keys
                if user["Physical Office"] == "International" or user["Reporting Branch"] == "International":
                    body = {"email": key, "role": "MEMBER"}
                    result = service.members().insert(groupKey="international@company.com", body=body).execute()
                if user["Physical Office"] != "International" and user["Reporting Branch"] != "International":
                    body = {"email": key, "role": "MEMBER"}
                    result = service.members().insert(groupKey="domestic@company.com", body=body).execute()
                if user["Physical Office"] == "Branch A" and user["Reporting Branch"] == "Branch A":
                    body = {"email": key, "role": "MEMBER"}
                    result = service.members().insert(groupKey="branch-a@company.com", body=body).execute()
            except Exception as e:
                error = str(e)
                print(error)

            # Load blank profile photo
            if IS_FROZEN:
                keys_dir = os.path.join(BUNDLE_DIR, 'keys')
            else:
                keys_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'Keys')
            with open(os.path.join(keys_dir, 'blank.jpg'), "rb") as image_file:
                ph_data = base64.urlsafe_b64encode(image_file.read()).decode('ascii')

            user_photo = {"kind": "admin#directory#user#photo", "photoData": ph_data, "mimeType": "JPG"}
            results = service.users().photos().update(userKey=key, body=user_photo).execute()

        except Exception as e:
            error = str(e)
            print(error)
