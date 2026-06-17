"""Shared pytest setup, auto-discovered before any test module is imported.

config.py reads DEFAULT_EMP_PASSWORD from the environment *at import time*
(module top level), so importing any cli module that depends on config would
raise KeyError before a single assertion runs. We set a throwaway value here so
the code under test imports cleanly without needing a real secret.

This is a workaround, not the real fix: reading secrets at import time is what
makes the module awkward to test in the first place. The cleaner design is to
move that read into a function so importing the module has no side effects.
"""

import os

os.environ.setdefault("DEFAULT_EMP_PASSWORD", "test-password-not-a-real-secret")
