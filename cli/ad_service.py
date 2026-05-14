import subprocess
import json
from config import DEFAULT_PASSWORD
from utils import display_office_name


# AD domain config
DOMAIN_SUFFIX = "DC=corp,DC=company,DC=com"
AD_ROOT = f"OU=Corp,{DOMAIN_SUFFIX}"
UPN_DOMAIN = "corp.company.com"

# Map Reporting Branch -> AD OU path under Corp
OU_BRANCH_MAP = {
    "Branch A":      f"OU=Branch A,OU=All Sites,{AD_ROOT}",
    "Branch B":      f"OU=Branch B,OU=All Sites,{AD_ROOT}",
    "Branch C":      f"OU=Branch C,OU=All Sites,{AD_ROOT}",
    "Branch C-II":   f"OU=Branch C,OU=All Sites,{AD_ROOT}",
    "Branch D":      f"OU=Branch D,OU=All Sites,{AD_ROOT}",
    "Branch E":      f"OU=Branch E,OU=All Sites,{AD_ROOT}",
    "Branch F":      f"OU=Branch F,OU=All Sites,{AD_ROOT}",
    "Branch G":      f"OU=Branch G,OU=All Sites,{AD_ROOT}",
    "Branch G-I":    f"OU=Branch G,OU=All Sites,{AD_ROOT}",
    "Branch G-II":   f"OU=Branch G,OU=All Sites,{AD_ROOT}",
    "Branch H":      f"OU=Branch H,OU=All Sites,{AD_ROOT}",
    "Branch I":      f"OU=Branch I,OU=All Sites,{AD_ROOT}",
    "International": f"OU=International,OU=All Sites,{AD_ROOT}",
    "Branch J":      f"OU=Branch J,OU=All Sites,{AD_ROOT}",
    "Remote":        f"OU=Branch A,OU=All Sites,{AD_ROOT}",
}


def _ps_escape(val):
    return str(val).replace("'", "''")


def _run_ps(command):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, timeout=60,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def pull_current_users():
    """Pull ALL AD users (enabled + disabled) keyed by SamAccountName, UPN, and Mail
    (all lowercased). Including disabled accounts is intentional: forest-wide
    UPN uniqueness blocks New-ADUser even when the existing account is disabled,
    so we need to detect those collisions before we try to create.
    """
    ps_command = (
        "Get-ADUser -Filter * "
        "-Properties SamAccountName,UserPrincipalName,Mail,DisplayName,GivenName,Surname,Enabled,DistinguishedName,Description "
        "| Select-Object SamAccountName,UserPrincipalName,Mail,DisplayName,GivenName,Surname,Enabled,DistinguishedName,Description "
        "| ConvertTo-Json -Depth 3"
    )
    print("  Pulling current AD users (incl. disabled)...")
    try:
        out, err, rc = _run_ps(ps_command)
    except subprocess.TimeoutExpired:
        print("  ERROR: PowerShell timed out pulling AD users.")
        return {}

    if rc != 0 or not out:
        print(f"  ERROR pulling AD users: {err}")
        return {}

    users = json.loads(out)
    if isinstance(users, dict):
        users = [users]

    user_map = {}
    enabled_count = 0
    for u in users:
        if u.get("Enabled"):
            enabled_count += 1
        sam = str(u.get("SamAccountName", "")).lower()
        upn = str(u.get("UserPrincipalName", "")).lower()
        mail = str(u.get("Mail", "")).lower()
        if sam:
            user_map[sam] = u
        if upn:
            user_map[upn] = u
        if mail:
            user_map[mail] = u

    print(f"  Found {len(users)} AD users ({enabled_count} enabled, {len(users) - enabled_count} disabled).")
    return user_map


def _reuse_disabled_account(existing_user, *, sam, target_ou, display_name, first, last,
                           email, title, department, office, phone, state, branch,
                           direct_line, ext, password):
    """Re-enable a disabled AD account: move it to the new target OU, reset the
    password, update profile attributes to match the new hire, and re-enable.

    Group memberships are intentionally NOT wiped -- those persist from the
    previous incarnation and the operator can manually clean up if needed
    (e.g., when the SAM is being re-used for a *different* person with the
    same name; flagged via the warning message printed in makeAD).
    """
    current_dn = existing_user.get("DistinguishedName", "")
    sam_esc = _ps_escape(sam)

    # 1) Move to target OU if currently elsewhere
    if current_dn and target_ou and target_ou not in current_dn:
        _, err, rc = _run_ps(
            f"Move-ADObject -Identity '{_ps_escape(current_dn)}' -TargetPath '{_ps_escape(target_ou)}'"
        )
        if rc != 0:
            return False, f"Move-ADObject failed: {err}"

    # 2) Reset password + force change at next logon
    _, err, rc = _run_ps(
        f"Set-ADAccountPassword -Identity '{sam_esc}' -Reset "
        f"-NewPassword (ConvertTo-SecureString '{_ps_escape(password)}' -AsPlainText -Force)"
    )
    if rc != 0:
        return False, f"Set-ADAccountPassword failed: {err}"

    # 3) Build attribute update. Only set fields we have values for so we don't
    # blank out anything inadvertently.
    set_parts = [
        f"-DisplayName '{_ps_escape(display_name)}'",
        f"-GivenName '{_ps_escape(first)}'",
        f"-Surname '{_ps_escape(last)}'",
        f"-ChangePasswordAtLogon $true",
        f"-Description 'Re-enabled $(Get-Date -Format yyyy-MM-dd) via autoAccounts (was disabled)'",
    ]
    if email:
        set_parts.append(f"-EmailAddress '{_ps_escape(email)}'")
    if title:
        set_parts.append(f"-Title '{_ps_escape(title)}'")
    if department:
        set_parts.append(f"-Department '{_ps_escape(department)}'")
    if office:
        set_parts.append(f"-Office '{_ps_escape(display_office_name(office))}'")
    if phone:
        set_parts.append(f"-OfficePhone '{_ps_escape(phone)}'")
    if state:
        set_parts.append(f"-State '{_ps_escape(state)}'")
    if branch:
        set_parts.append(f"-City '{_ps_escape(display_office_name(branch))}'")
    if direct_line:
        set_parts.append(f"-MobilePhone '{_ps_escape(direct_line)}'")

    set_cmd = f"Set-ADUser -Identity '{sam_esc}' " + " ".join(set_parts)
    _, err, rc = _run_ps(set_cmd)
    if rc != 0:
        return False, f"Set-ADUser failed: {err}"

    # 4) Re-enable
    _, err, rc = _run_ps(f"Enable-ADAccount -Identity '{sam_esc}'")
    if rc != 0:
        return False, f"Enable-ADAccount failed: {err}"

    return True, "ok"


def _ou_exists(dn):
    out, _, _ = _run_ps(
        f"try {{ Get-ADOrganizationalUnit -Identity '{_ps_escape(dn)}' | Out-Null; Write-Output 'EXISTS' }} "
        f"catch {{ Write-Output 'NOT_FOUND' }}"
    )
    return "EXISTS" in out


def _ensure_ou(target_ou):
    """Create the OU chain if it doesn't exist. Returns True on success."""
    if _ou_exists(target_ou):
        return True

    # Parse the OU chain and create from root to leaf
    parts = []
    remaining = target_ou
    while remaining.startswith("OU="):
        comma_idx = remaining.find(",")
        if comma_idx == -1:
            break
        ou_part = remaining[:comma_idx]
        parts.append(ou_part.split("=", 1)[1])
        remaining = remaining[comma_idx + 1:]
        if remaining == DOMAIN_SUFFIX or remaining == AD_ROOT:
            break

    # parts is leaf-to-root, reverse to create root-to-leaf
    parts.reverse()
    base = remaining if not remaining.startswith("OU=") else AD_ROOT

    for i, ou_name in enumerate(parts):
        if i == 0:
            parent = base
        else:
            parent_components = ",".join(f"OU={parts[j]}" for j in range(i - 1, -1, -1))
            parent = f"{parent_components},{base}"

        current_dn = ",".join(f"OU={parts[j]}" for j in range(i, -1, -1)) + f",{base}"

        if _ou_exists(current_dn):
            continue

        _, err, rc = _run_ps(
            f"New-ADOrganizationalUnit -Name '{_ps_escape(ou_name)}' "
            f"-Path '{_ps_escape(parent)}' -ProtectedFromAccidentalDeletion $false"
        )
        if rc != 0:
            print(f"    ERROR creating OU {current_dn}: {err}")
            return False
        print(f"    Created OU: {current_dn}")

    return True


def _resolve_manager_dn(manager_email):
    """Look up manager's AD DistinguishedName by email."""
    if not manager_email or "@" not in manager_email:
        return None

    # Try by mail attribute
    out, _, rc = _run_ps(
        f"(Get-ADUser -Filter \"Mail -eq '{_ps_escape(manager_email)}'\" -Properties Mail).DistinguishedName"
    )
    if rc == 0 and out:
        return out

    # Try by SamAccountName derived from email
    sam_guess = manager_email.split("@")[0].lower()
    out, _, rc = _run_ps(
        f"try {{ (Get-ADUser -Identity '{_ps_escape(sam_guess)}').DistinguishedName }} catch {{ }}"
    )
    if rc == 0 and out:
        return out

    return None


def makeAD(array):
    """Create Active Directory accounts for new hires that need a server account."""
    if not array:
        print("No users to process.")
        return

    # Filter to only users flagged as needing a server account
    ad_users = [u for u in array if str(u.get("Needs Server Account", "")).strip().upper() in ("TRUE", "YES", "1")]
    if not ad_users:
        print("No users with 'Needs Server Account' enabled.")
        return

    print(f"  {len(ad_users)} of {len(array)} users need a server account.")
    existing = pull_current_users()
    created = 0
    skipped = 0
    reused = 0
    errors = 0

    for user in ad_users:
        first = user.get("Preferred First Name", "").strip()
        last = user.get("Preferred Last Name", "").strip()
        email = user.get("Employee Email", "").strip()
        username = user.get("Username", f"{first.lower()}.{last.lower()}")
        title = user.get("Title", "").strip()
        department = user.get("Department", "").strip()
        branch = user.get("Reporting Branch", "").strip()
        office = user.get("Physical Office", "").strip()
        phone = user.get("Office Phone", "").strip()
        ext = user.get("Ext", "").strip()
        direct_line = user.get("Direct Line", "").strip()
        manager_email = user.get("Direct Report", "").strip()
        state = user.get("State", "").strip()
        display_name = f"{first} {last}"

        # Determine target OU
        target_ou = OU_BRANCH_MAP.get(branch, f"OU=Staff,{AD_ROOT}")

        existing_user = (
            existing.get(username.lower())
            or existing.get(email.lower())
            or existing.get(f"{username.lower()}@{UPN_DOMAIN}")
        )
        if existing_user:
            if existing_user.get("Enabled"):
                print(f"  SKIP: {display_name} ({username}) - already enabled in AD")
                skipped += 1
                continue
            # Reuse the disabled account
            current_dn = existing_user.get("DistinguishedName") or ""
            existing_desc = (existing_user.get("Description") or "").strip()
            print(f"  REUSE: {display_name} ({username}) - found DISABLED account, re-enabling")
            if existing_desc:
                print(f"    prior description: {existing_desc}")
            print(f"    was at: {current_dn}")
            print(f"    moving to: {target_ou}")
            _ensure_ou(target_ou)
            ok, msg = _reuse_disabled_account(
                existing_user,
                sam=username, target_ou=target_ou, display_name=display_name,
                first=first, last=last, email=email, title=title, department=department,
                office=office, phone=phone, state=state, branch=branch,
                direct_line=direct_line, ext=ext, password=DEFAULT_PASSWORD,
            )
            if not ok:
                print(f"    ERROR re-enabling: {msg}")
                errors += 1
                continue
            if manager_email:
                manager_dn = _resolve_manager_dn(manager_email)
                if manager_dn:
                    _, merr, mrc = _run_ps(
                        f"Set-ADUser -Identity '{_ps_escape(username)}' -Manager '{_ps_escape(manager_dn)}'"
                    )
                    if mrc == 0:
                        print(f"    Set manager: {manager_email}")
                    else:
                        print(f"    WARNING: Could not set manager: {merr}")
                else:
                    print(f"    WARNING: Manager '{manager_email}' not found in AD")
            print(f"    NOTE: Existing group memberships preserved -- review manually if this is a different person with the same name.")
            print(f"    OK (reused, password reset to default)")
            reused += 1
            continue

        _ensure_ou(target_ou)

        # Build the New-ADUser command with all available fields
        sam = _ps_escape(username)
        upn = f"{username}@{UPN_DOMAIN}"

        cmd_parts = [
            f"New-ADUser",
            f"-Name '{_ps_escape(display_name)}'",
            f"-SamAccountName '{sam}'",
            f"-UserPrincipalName '{_ps_escape(upn)}'",
            f"-GivenName '{_ps_escape(first)}'",
            f"-Surname '{_ps_escape(last)}'",
            f"-DisplayName '{_ps_escape(display_name)}'",
            f"-AccountPassword (ConvertTo-SecureString '{_ps_escape(DEFAULT_PASSWORD)}' -AsPlainText -Force)",
            f"-Enabled $true",
            f"-ChangePasswordAtLogon $true",
            f"-Path '{_ps_escape(target_ou)}'",
        ]

        if email:
            cmd_parts.append(f"-EmailAddress '{_ps_escape(email)}'")
        if title:
            cmd_parts.append(f"-Title '{_ps_escape(title)}'")
        if department:
            cmd_parts.append(f"-Department '{_ps_escape(department)}'")
        if office:
            cmd_parts.append(f"-Office '{_ps_escape(display_office_name(office))}'")
        if phone:
            cmd_parts.append(f"-OfficePhone '{_ps_escape(phone)}'")
        if state:
            cmd_parts.append(f"-State '{_ps_escape(state)}'")
        if branch:
            cmd_parts.append(f"-City '{_ps_escape(display_office_name(branch))}'")
        if direct_line:
            cmd_parts.append(f"-MobilePhone '{_ps_escape(direct_line)}'")
        if ext:
            cmd_parts.append(f"-Description 'Ext: {_ps_escape(ext)}'")

        create_cmd = " ".join(cmd_parts)

        print(f"  Creating: {display_name} ({username}) -> {target_ou}")
        out, err, rc = _run_ps(create_cmd)
        if rc != 0:
            print(f"    ERROR: {err}")
            errors += 1
            continue

        if manager_email:
            manager_dn = _resolve_manager_dn(manager_email)
            if manager_dn:
                _, merr, mrc = _run_ps(
                    f"Set-ADUser -Identity '{sam}' -Manager '{_ps_escape(manager_dn)}'"
                )
                if mrc == 0:
                    print(f"    Set manager: {manager_email}")
                else:
                    print(f"    WARNING: Could not set manager: {merr}")
            else:
                print(f"    WARNING: Manager '{manager_email}' not found in AD")

        created += 1
        print(f"    OK")

    print(f"\n--- AD Account Creation Summary ---")
    print(f"  Created: {created}")
    print(f"  Reused (disabled account re-enabled + password reset): {reused}")
    print(f"  Skipped (already enabled): {skipped}")
    print(f"  Errors:  {errors}")
