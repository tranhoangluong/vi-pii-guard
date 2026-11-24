import datetime as dt

import pytest

from vi_pii_guard import validators as v
from vi_pii_guard.normalize import fold, normalize, strip_diacritics


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("079204123456", True),  # TP.HCM, male born 2004
        ("001190002468", True),  # Hà Nội, female born 1990
        ("003190002468", False),  # 003 is not a province code
        ("079299123456", False),  # born 2099: in the future
        ("07920412345", False),  # 11 digits
    ],
)
def test_national_id(value: str, expected: bool) -> None:
    assert v.is_valid_national_id(value, today=dt.date(2026, 11, 23)) is expected


def test_birth_year_from_id() -> None:
    assert v.birth_year_from_id("001190002468") == 1990
    assert v.birth_year_from_id("079304123456") == 2004


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0912345678", True),
        ("0912 345 678", True),
        ("+84 912 345 678", True),
        ("84912345678", True),
        ("0112345678", False),  # unassigned prefix
        ("091234567", False),
    ],
)
def test_mobile(value: str, expected: bool) -> None:
    assert v.is_valid_mobile(value) is expected


def test_landline() -> None:
    assert v.is_valid_landline("028 3822 1234")
    assert not v.is_valid_landline("0912345678")


def test_tax_code_checksum_round_trip() -> None:
    check = v.tax_check_digit("010123456")
    assert check is not None
    code = f"010123456{check}"
    assert v.is_valid_tax_code(code)
    assert v.is_valid_tax_code(f"{code}-001")
    assert not v.is_valid_tax_code(f"{code}-000")
    wrong = f"010123456{(check + 1) % 10}"
    assert not v.is_valid_tax_code(wrong)


def test_tax_check_digit_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="9 digits"):
        v.tax_check_digit("123")


def test_luhn() -> None:
    assert v.luhn_ok("4111 1111 1111 1111")
    assert not v.luhn_ok("4111 1111 1111 1112")
    assert not v.luhn_ok("0000000000000000")  # degenerate value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12/05/1990", True),
        ("ngày 5 tháng 3 năm 1990", True),
        ("31/02/1990", False),
        ("01/01/2099", False),
    ],
)
def test_birth_date(value: str, expected: bool) -> None:
    assert v.is_plausible_birth_date(value, today=dt.date(2026, 11, 23)) is expected


def test_fold_preserves_length_and_strips_marks() -> None:
    text = "Số điện thoại ĐẶNG"
    assert fold(text) == "so dien thoai dang"
    assert len(fold(text)) == len(text)


def test_normalize_composes_nfd_input() -> None:
    decomposed = "Nguyễn"  # "Nguyễn" typed as NFD
    assert normalize(decomposed) == "Nguyễn"


def test_strip_diacritics_keeps_case() -> None:
    assert strip_diacritics("Đặng Thị Hương") == "Dang Thi Huong"
