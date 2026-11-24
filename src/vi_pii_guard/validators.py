"""Structural validators for Vietnamese identifiers.

A validator only checks that a value *could* be real (structure, checksum,
plausible ranges). It never proves that the identifier was issued.
"""

from __future__ import annotations

import datetime as dt
import re

from vi_pii_guard.normalize import digits_only

# Province / centrally-run city codes used as the first three digits of the
# 12-digit personal identification number (63 pre-2025 provinces, 001-096).
# Source: Circular 07/2016/TT-BCA, Article 7. Citizens whose birth was
# registered abroad carry a country code instead, so an unknown prefix lowers
# confidence but does not reject the value.
PROVINCE_CODES: frozenset[str] = frozenset(
    {
        "001", "002", "004", "006", "008", "010", "011", "012", "014", "015",
        "017", "019", "020", "022", "024", "025", "026", "027", "030", "031",
        "033", "034", "035", "036", "037", "038", "040", "042", "044", "045",
        "046", "048", "049", "051", "052", "054", "056", "058", "060", "062",
        "064", "066", "067", "068", "070", "072", "074", "075", "077", "079",
        "080", "082", "083", "084", "086", "087", "089", "091", "092", "093",
        "094", "095", "096",
    }
)  # fmt: skip

# Three-digit mobile prefixes (with leading 0) currently assigned to carriers.
MOBILE_PREFIXES: frozenset[str] = frozenset(
    {
        "032", "033", "034", "035", "036", "037", "038", "039",  # Viettel
        "086", "096", "097", "098",                              # Viettel
        "070", "076", "077", "078", "079", "089", "090", "093",  # MobiFone
        "081", "082", "083", "084", "085", "088", "091", "094",  # VinaPhone
        "052", "056", "058", "092",                              # Vietnamobile
        "059", "099",                                            # Gmobile
        "087",                                                   # iTel
        "055",                                                   # Reddi
    }
)  # fmt: skip

_TAX_WEIGHTS = (31, 29, 23, 19, 17, 13, 7, 5, 3)
_TAX_PATTERN = re.compile(r"^(\d{10})(?:-(\d{3}))?$")


def birth_year_from_id(value: str) -> int | None:
    """Decode the birth year from a 12-digit personal ID (century/gender digit + yy)."""
    digits = digits_only(value)
    if len(digits) != 12:
        return None
    century_gender = int(digits[3])
    return 1900 + (century_gender // 2) * 100 + int(digits[4:6])


def is_valid_national_id(value: str, *, today: dt.date | None = None) -> bool:
    """Check a 12-digit personal ID (CCCD / số định danh cá nhân).

    Layout: 3-digit province code, 1 century+gender digit, 2-digit birth year,
    6 random digits. The birth year must not be in the future.
    """
    digits = digits_only(value)
    if len(digits) != 12 or digits[:3] not in PROVINCE_CODES:
        return False
    year = birth_year_from_id(digits)
    current_year = (today or dt.date.today()).year
    return year is not None and 1900 <= year <= current_year


def normalize_phone(value: str) -> str:
    """Return the national form (``0xxxxxxxxx``) of a phone number."""
    digits = digits_only(value)
    if digits.startswith("84") and len(digits) in (11, 12):
        return "0" + digits[2:]
    return digits


def is_valid_mobile(value: str) -> bool:
    national = normalize_phone(value)
    return len(national) == 10 and national[:3] in MOBILE_PREFIXES


def is_valid_landline(value: str) -> bool:
    """Fixed-line numbers have 11 digits and start with ``02`` since 2017."""
    national = normalize_phone(value)
    return len(national) == 11 and national.startswith("02")


def is_valid_phone(value: str) -> bool:
    return is_valid_mobile(value) or is_valid_landline(value)


def tax_check_digit(first_nine: str) -> int | None:
    """Compute the 10th digit of a tax code; ``None`` if no digit is valid."""
    if len(first_nine) != 9 or not first_nine.isdigit():
        raise ValueError("expected exactly 9 digits")
    remainder = sum(int(d) * w for d, w in zip(first_nine, _TAX_WEIGHTS, strict=True)) % 11
    check = 10 - remainder
    return check if check <= 9 else None


def is_valid_tax_code(value: str) -> bool:
    """Validate a 10-digit tax code, or 13-digit branch form ``NNNNNNNNNN-NNN``."""
    match = _TAX_PATTERN.match(value.strip())
    if match is None:
        return False
    main, branch = match.group(1), match.group(2)
    if branch is not None and branch == "000":
        return False
    return tax_check_digit(main[:9]) == int(main[9])


def luhn_ok(value: str) -> bool:
    digits = digits_only(value)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


_DATE_NUMERIC = re.compile(r"(\d{1,2})\D+(\d{1,2})\D+(\d{4})")


def is_plausible_birth_date(value: str, *, today: dt.date | None = None) -> bool:
    """Accept ``dd/mm/yyyy``-like or ``ngày d tháng m năm yyyy`` dates in the past."""
    match = _DATE_NUMERIC.search(value)
    if match is None:
        return False
    day, month, year = (int(g) for g in match.groups())
    try:
        parsed = dt.date(year, month, day)
    except ValueError:
        return False
    return dt.date(1900, 1, 1) <= parsed <= (today or dt.date.today())
