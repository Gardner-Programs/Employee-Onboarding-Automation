"""Guard against the cli and gui copies of the pure-logic modules drifting.

The two apps can't share one import (flat ``cli/`` vs the gui ``scripts`` package
shipped as a frozen exe), so each carries its own copy of the dependency-free
pure modules. They must stay byte-identical — this test fails if they drift,
which is exactly what let the logic diverge before. If you change one copy,
change both (or extract a shared installable package).
"""

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SHARED_PURE_MODULES = [
    "terminal_matching.py",
    "verification.py",
    "enrichment.py",
    "terminal_routing.py",
    "ps_utils.py",
    "number_assignment.py",
    "office_names.py",
]


@pytest.mark.parametrize("module", _SHARED_PURE_MODULES)
def test_cli_and_gui_pure_modules_are_identical(module):
    cli_src = (_REPO_ROOT / "cli" / module).read_text()
    gui_src = (_REPO_ROOT / "gui" / "scripts" / module).read_text()
    assert cli_src == gui_src, (
        f"{module} has drifted between cli/ and gui/scripts/ — keep both copies "
        "in sync (or extract a shared package)."
    )
