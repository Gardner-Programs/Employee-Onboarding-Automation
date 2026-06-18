"""Pure 8x8 extension/number allocation logic.

Picks an extension (within the office's range) and a phone number (matching the
office's prefix) from the available pools. No Selenium — the pools and the
result are plain lists/strings. NOTE: this mutates the pools it's given, popping
the chosen extension and number out so the caller doesn't reuse them.
"""

from __future__ import annotations

DEFAULT_EXT_RANGE = (1000, 1999)
OFFICE_EXT_RANGES = {
    'Branch A': (1000, 1999),
    'Remote Field Office': (1000, 1999),
    'Remote': (1000, 1999),
    'New Branch': (1000, 1999),
    'Branch D': (2000, 2499),
    'Branch F': (2500, 2999),
    'Branch G': (4000, 4499),
    'Branch G-II': (4500, 4999),
    'Branch C': (5000, 5499),
    'Branch H': (6000, 6499),
    'Branch J': (7000, 7499),
    'Branch B': (8000, 8399),
    'Branch E': (8400, 8599),
    'Branch I': (8600, 8999),
    'Leadership Team': (9000, 9499),
}

# Phone number area code prefixes by office
OFFICE_PHONE_PREFIX = {
    "Branch G-II": "1555",
}
DEFAULT_PHONE_PREFIX = "1555"


def assign_numbers(
    office: str,
    available_numbers: list[str],
    available_extensions: list[str],
) -> tuple[str, str]:
    """Pop and return the best (extension, phone_number) pair for *office*.

    Chosen items are removed from *available_numbers* / *available_extensions*.
    Returns "" for either slot when nothing in the pool fits.
    """
    extension = ""
    number = ""

    low, high = OFFICE_EXT_RANGES.get(office, DEFAULT_EXT_RANGE)
    for ext in available_extensions:
        try:
            val = int(ext)
            if low <= val <= high:
                extension = ext
                available_extensions.remove(ext)
                break
        except (ValueError, TypeError):
            continue

    prefix = OFFICE_PHONE_PREFIX.get(office, DEFAULT_PHONE_PREFIX)
    for num in available_numbers:
        if str(num).startswith(prefix):
            available_numbers.remove(num)
            number = num
            break

    return extension, number
