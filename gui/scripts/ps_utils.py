"""PowerShell helper(s).

Pure string utilities used when building PowerShell command strings for the
Active Directory provisioning. Kept dependency-free so the escaping — which is
the injection-safety boundary — can be tested in isolation.
"""

from __future__ import annotations


def ps_escape(val: object) -> str:
    """Escape a value for safe embedding in a single-quoted PowerShell string.

    PowerShell escapes a single quote by doubling it, so any `'` in user-derived
    input must become `''` before it's interpolated into a `'...'` literal.
    """
    return str(val).replace("'", "''")
