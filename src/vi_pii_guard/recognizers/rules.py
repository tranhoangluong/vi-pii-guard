"""Built-in regex rules for structured Vietnamese PII."""

from __future__ import annotations

import re

from vi_pii_guard import validators as v
from vi_pii_guard.domain import EntityType
from vi_pii_guard.recognizers.context import KeywordSet
from vi_pii_guard.recognizers.patterns import PatternRecognizer, PatternRule

PHONE_CONTEXT = KeywordSet(
    [
        "sđt", "số điện thoại", "điện thoại", "đt", "dt", "phone", "tel", "zalo",
        "di động", "liên hệ", "gọi", "hotline", "nhắn tin", "sms",
    ]
)  # fmt: skip
ID_CONTEXT = KeywordSet(
    [
        "cccd", "căn cước", "căn cước công dân", "cmnd", "chứng minh", "chứng minh nhân dân",
        "cmt", "số định danh", "định danh", "giấy tờ tùy thân",
    ]
)  # fmt: skip
TAX_CONTEXT = KeywordSet(["mst", "mã số thuế", "tax code", "mã thuế", "masothue"])
BANK_CONTEXT = KeywordSet(
    [
        "stk", "số tài khoản", "tài khoản", "tk", "account", "chuyển khoản", "ck",
        "ngân hàng", "vietcombank", "vcb", "techcombank", "tcb", "bidv", "vietinbank",
        "agribank", "mb", "mbbank", "acb", "vpbank", "tpbank", "sacombank", "hdbank",
        "vib", "shb", "ocb", "msb", "seabank", "pvcombank", "lpbank", "eximbank",
    ]
)  # fmt: skip
CARD_CONTEXT = KeywordSet(["thẻ", "card", "visa", "mastercard", "jcb", "napas", "atm"])
PASSPORT_CONTEXT = KeywordSet(["hộ chiếu", "passport", "số hộ chiếu"])
PLATE_CONTEXT = KeywordSet(["biển số", "biển kiểm soát", "bks", "bsx", "xe", "biển số xe"])
DOB_CONTEXT = KeywordSet(
    ["sinh", "ngày sinh", "sinh ngày", "năm sinh", "ns", "dob", "date of birth", "sinh nhật"]
)

_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)
_MOBILE = re.compile(r"(?<![\d+])(?:\+84|84|0)[\s.\-]?[35789](?:[\s.\-]?\d){8}(?!\d)")
_LANDLINE = re.compile(r"(?<![\d+])(?:\+84|84|0)[\s.\-]?2(?:[\s.\-]?\d){9}(?!\d)")
_NATIONAL_ID_12 = re.compile(r"(?<!\d)\d{12}(?!\d)")
_NATIONAL_ID_9 = re.compile(r"(?<!\d)\d{9}(?!\d)")
_TAX_CODE = re.compile(r"(?<![\d-])\d{10}(?:-\d{3})?(?![\d-])")
_BANK_ACCOUNT = re.compile(r"(?<!\d)\d{6,19}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_PASSPORT = re.compile(r"(?<![A-Za-z0-9])[A-Z]\d{7}(?![A-Za-z0-9])")
_PLATE = re.compile(
    r"(?<![A-Za-z0-9])(?:1[1-9]|[2-9]\d)"
    r"(?:"
    r"[A-Z]{1,2}[\s-]?\d{3}\.?\d{2}"  # car: 51F-123.45, 51LD-123.45
    r"|[A-Z][\s-]?\d{4}"  # older car: 51A-1234
    r"|[\s-]?[A-Z][A-Z0-9][\s-]?\d{3}\.?\d{2}"  # motorbike: 59-X1 123.45
    r"|[\s-]?[A-Z][A-Z0-9][\s-]?\d{4}"  # older motorbike: 59-X1 1234
    r")(?![A-Za-z0-9])"
)
_DOB_NUMERIC = re.compile(
    r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])[/.-](?:0?[1-9]|1[0-2])[/.-](?:19|20)\d{2}(?!\d)"
)
_DOB_TEXT = re.compile(
    r"ng[àa]y\s+\d{1,2}\s+th[áa]ng\s+\d{1,2}\s+n[ăa]m\s+(?:19|20)\d{2}", re.IGNORECASE
)


def default_rules() -> list[PatternRule]:
    return [
        PatternRule(EntityType.EMAIL, _EMAIL, base_score=0.95),
        PatternRule(
            EntityType.PHONE,
            _MOBILE,
            base_score=0.3,
            validator=v.is_valid_mobile,
            validated_score=0.85,
            context=PHONE_CONTEXT,
            context_boost=0.15,
            negative_context=KeywordSet(["mst", "mã số thuế", "stk", "số tài khoản", "tài khoản"]),
            negative_penalty=0.4,
        ),
        PatternRule(
            EntityType.PHONE,
            _LANDLINE,
            base_score=0.45,
            validator=v.is_valid_landline,
            validated_score=0.6,
            context=PHONE_CONTEXT,
            context_boost=0.3,
        ),
        PatternRule(
            EntityType.NATIONAL_ID,
            _NATIONAL_ID_12,
            base_score=0.4,
            validator=v.is_valid_national_id,
            validated_score=0.85,
            context=ID_CONTEXT,
            context_boost=0.3,
            negative_context=BANK_CONTEXT,
            negative_penalty=0.4,
        ),
        PatternRule(
            EntityType.NATIONAL_ID,
            _NATIONAL_ID_9,
            base_score=0.2,
            context=ID_CONTEXT,
            context_boost=0.55,
            require_context=True,
        ),
        PatternRule(
            EntityType.TAX_CODE,
            _TAX_CODE,
            base_score=0.3,
            validator=v.is_valid_tax_code,
            validated_score=0.6,
            context=TAX_CONTEXT,
            context_boost=0.35,
            negative_context=PHONE_CONTEXT,
            negative_penalty=0.3,
        ),
        PatternRule(
            EntityType.BANK_ACCOUNT,
            _BANK_ACCOUNT,
            base_score=0.2,
            context=BANK_CONTEXT,
            context_boost=0.5,
            require_context=True,
        ),
        PatternRule(
            EntityType.CARD_NUMBER,
            _CARD,
            base_score=0.0,
            validator=v.luhn_ok,
            validated_score=0.9,
            reject_invalid=True,
            context=CARD_CONTEXT,
            context_boost=0.1,
        ),
        PatternRule(
            EntityType.PASSPORT,
            _PASSPORT,
            base_score=0.3,
            context=PASSPORT_CONTEXT,
            context_boost=0.5,
        ),
        PatternRule(
            EntityType.LICENSE_PLATE,
            _PLATE,
            base_score=0.6,
            context=PLATE_CONTEXT,
            context_boost=0.3,
        ),
        PatternRule(
            EntityType.DATE_OF_BIRTH,
            _DOB_NUMERIC,
            base_score=0.2,
            validator=v.is_plausible_birth_date,
            reject_invalid=True,
            context=DOB_CONTEXT,
            context_boost=0.6,
            require_context=True,
        ),
        PatternRule(
            EntityType.DATE_OF_BIRTH,
            _DOB_TEXT,
            base_score=0.2,
            validator=v.is_plausible_birth_date,
            reject_invalid=True,
            context=DOB_CONTEXT,
            context_boost=0.6,
            require_context=True,
        ),
    ]


def default_pattern_recognizer() -> PatternRecognizer:
    return PatternRecognizer(default_rules(), name="regex")
