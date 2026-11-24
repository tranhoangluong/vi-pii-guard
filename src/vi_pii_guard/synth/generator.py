"""Template-based synthetic data with exact character-level labels.

No real personal data is ever needed: values are random but structurally
valid (correct ID layout, tax checksum, Luhn digit, carrier prefixes), so
the rule validators see realistic inputs. Hard negatives (order ids, prices,
hotlines) are included on purpose to measure false positives.
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Literal

from vi_pii_guard.domain import EntityType
from vi_pii_guard.normalize import strip_diacritics
from vi_pii_guard.synth import lexicon as lx
from vi_pii_guard.validators import MOBILE_PREFIXES, PROVINCE_CODES, tax_check_digit

AddressFormat = Literal["pre_2025", "post_2025", "mixed"]


@dataclass(frozen=True)
class GoldSpan:
    start: int
    end: int
    label: str


@dataclass(frozen=True)
class Example:
    id: str
    text: str
    spans: tuple[GoldSpan, ...]
    meta: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        payload = asdict(self)
        payload["spans"] = [asdict(s) for s in self.spans]
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> Example:
        data = json.loads(line)
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            spans=tuple(
                GoldSpan(int(s["start"]), int(s["end"]), str(s["label"])) for s in data["spans"]
            ),
            meta={str(k): str(v) for k, v in data.get("meta", {}).items()},
        )


# (template id, domain, template). Placeholders in braces are filled below.
TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (
        "cs01",
        "customer_support",
        "Chào shop, tôi tên là {PERSON}, số điện thoại {PHONE}, nhờ kiểm tra giúp đơn hàng {ORDER_ID}.",
    ),
    (
        "cs02",
        "customer_support",
        "Giao hàng đến địa chỉ: {ADDRESS}. Người nhận: {PERSON}, SĐT {PHONE}.",
    ),
    (
        "cs03",
        "customer_support",
        "Em muốn đổi email đăng nhập từ {EMAIL} sang email mới, em là {PERSON} ạ.",
    ),
    ("cs04", "customer_support", "Nhờ anh {GIVEN} gọi lại cho em qua số {PHONE} nhé."),
    (
        "cs05",
        "customer_support",
        "Đơn {ORDER_ID} của chị {PERSON} giao tới {ADDRESS} bị trễ 3 ngày rồi.",
    ),
    ("cs06", "customer_support", "Liên hệ {PERSON} qua zalo {PHONE} hoặc email {EMAIL}."),
    ("cs07", "customer_support", "{PERSON} - {PHONE} - {ADDRESS}"),
    (
        "bk01",
        "banking",
        "Khách hàng {PERSON}, CCCD số {NATIONAL_ID}, yêu cầu mở thẻ ghi nợ tại chi nhánh.",
    ),
    (
        "bk02",
        "banking",
        "Vui lòng chuyển khoản vào STK {BANK_ACCOUNT} {BANK}, chủ tài khoản {PERSON}, nội dung thanh toán đơn {ORDER_ID}.",
    ),
    ("bk03", "banking", "Thẻ {CARD_NUMBER} của tôi bị trừ tiền 2 lần, số tiền {PRICE}."),
    (
        "bk04",
        "banking",
        "Tôi là {PERSON}, sinh ngày {DATE_OF_BIRTH}, số căn cước {NATIONAL_ID}, cần cập nhật thông tin tài khoản.",
    ),
    (
        "bk05",
        "banking",
        "Họ tên: {PERSON}\nNgày sinh: {DATE_OF_BIRTH}\nCMND: {NATIONAL_ID_OLD}\nĐịa chỉ thường trú: {ADDRESS}",
    ),
    (
        "tx01",
        "tax",
        "Xuất hóa đơn VAT cho công ty, mã số thuế {TAX_CODE}, email nhận hóa đơn {EMAIL}.",
    ),
    ("tx02", "tax", "MST cá nhân của tôi là {NATIONAL_ID}, nhờ kế toán kiểm tra giúp."),
    ("lg01", "logistics", "Xe biển số {LICENSE_PLATE} đã đến kho, tài xế {PERSON} (SĐT {PHONE})."),
    (
        "lg02",
        "logistics",
        "Tài xế {PERSON}, biển kiểm soát {LICENSE_PLATE}, sẽ giao hàng trong hôm nay.",
    ),
    (
        "tv01",
        "travel",
        "Đặt vé cho hành khách {PERSON}, hộ chiếu {PASSPORT}, ngày sinh {DATE_OF_BIRTH}.",
    ),
    (
        "hc01",
        "healthcare",
        "Bệnh nhân {PERSON}, {AGE} tuổi, địa chỉ {ADDRESS}, tái khám ngày {VISIT_DATE}.",
    ),
    ("hr01", "hr", "Ứng viên {PERSON} gửi CV qua {EMAIL}, số điện thoại liên hệ {PHONE}."),
    ("nd01", "no_diacritics", "toi ten {PERSON_PLAIN}, sdt {PHONE}, dia chi {ADDRESS_PLAIN}"),
    ("nd02", "no_diacritics", "ib minh qua {EMAIL} hoac goi {PHONE} nha"),
)
NEGATIVE_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    ("ng01", "negative", "Cho mình hỏi sản phẩm {PRODUCT_CODE} giá {PRICE} còn hàng không ạ?"),
    ("ng02", "negative", "Đơn hàng {ORDER_ID} đã được giao thành công lúc {TIME}."),
    ("ng03", "negative", "Hotline hỗ trợ {HOTLINE} hoạt động từ 8h đến 21h."),
    ("ng04", "negative", "Shop ở Hà Nội có giao ra TP. Hồ Chí Minh không ạ?"),
    ("ng05", "negative", "Mua {QTY} sản phẩm được giảm {PERCENT}% đúng không shop?"),
    ("ng06", "negative", "Mã giảm giá {PROMO} còn hạn đến {VISIT_DATE} nhé."),
    ("ng07", "negative", "Chi nhánh {BANK} gần nhất mở cửa mấy giờ?"),
    ("ng08", "negative", "Lãi suất tiết kiệm kỳ hạn 12 tháng năm 2026 là bao nhiêu?"),
)

_PLACEHOLDER = re.compile(r"\{([A-Z_]+)\}")


class SyntheticGenerator:
    def __init__(self, seed: int = 13, address_format: AddressFormat = "mixed") -> None:
        self._rng = random.Random(seed)
        self._address_format = address_format
        self._fillers: dict[str, tuple[EntityType | None, Callable[[], str]]] = {
            "PERSON": (EntityType.PERSON, self.person),
            "PERSON_PLAIN": (EntityType.PERSON, self.person_plain),
            "GIVEN": (EntityType.PERSON, self.given_name),
            "ADDRESS": (EntityType.ADDRESS, self.address),
            "ADDRESS_PLAIN": (EntityType.ADDRESS, lambda: strip_diacritics(self.address()).lower()),
            "PHONE": (EntityType.PHONE, self.phone),
            "EMAIL": (EntityType.EMAIL, self.email),
            "NATIONAL_ID": (EntityType.NATIONAL_ID, self.national_id),
            "NATIONAL_ID_OLD": (EntityType.NATIONAL_ID, lambda: self._digits(9)),
            "PASSPORT": (EntityType.PASSPORT, self.passport),
            "TAX_CODE": (EntityType.TAX_CODE, self.tax_code),
            "BANK_ACCOUNT": (
                EntityType.BANK_ACCOUNT,
                lambda: self._digits(self._rng.randint(9, 14)),
            ),
            "CARD_NUMBER": (EntityType.CARD_NUMBER, self.card_number),
            "LICENSE_PLATE": (EntityType.LICENSE_PLATE, self.license_plate),
            "DATE_OF_BIRTH": (EntityType.DATE_OF_BIRTH, self.date_of_birth),
            # Unlabeled fillers (hard negatives).
            "ORDER_ID": (
                None,
                lambda: (
                    "DH" + self._digits(8) if self._rng.random() < 0.5 else "2026" + self._digits(8)
                ),
            ),
            "PRICE": (
                None,
                lambda: f"{self._rng.randint(50, 9_999) * 1000:,}".replace(",", ".") + "đ",
            ),
            "HOTLINE": (None, lambda: self._rng.choice(["1900 ", "1800 "]) + self._digits(4)),
            "PRODUCT_CODE": (None, lambda: "SP-" + self._digits(5)),
            "TIME": (None, lambda: f"{self._rng.randint(7, 21)}:{self._rng.randint(0, 59):02d}"),
            "QTY": (None, lambda: str(self._rng.randint(2, 10))),
            "PERCENT": (None, lambda: str(self._rng.choice([5, 10, 15, 20, 30]))),
            "PROMO": (None, lambda: "SALE" + self._digits(3)),
            "VISIT_DATE": (
                None,
                lambda: f"{self._rng.randint(1, 28)}/{self._rng.randint(1, 12)}/2026",
            ),
            "BANK": (None, lambda: self._rng.choice(lx.BANKS)),
            "AGE": (None, lambda: str(self._rng.randint(18, 85))),
        }

    # ----- value generators -------------------------------------------------
    def _digits(self, n: int) -> str:
        return "".join(self._rng.choice("0123456789") for _ in range(n))

    def given_name(self) -> str:
        return self._rng.choice(lx.GIVEN_MALE + lx.GIVEN_FEMALE)

    def person(self) -> str:
        female = self._rng.random() < 0.5
        middle = self._rng.choice(lx.MIDDLE_FEMALE if female else lx.MIDDLE_MALE)
        given = self._rng.choice(lx.GIVEN_FEMALE if female else lx.GIVEN_MALE)
        parts = [self._rng.choice(lx.SURNAMES), middle, given]
        if self._rng.random() < 0.15:
            parts.insert(2, self._rng.choice(lx.MIDDLE_FEMALE if female else lx.MIDDLE_MALE))
        name = " ".join(parts)
        return name.upper() if self._rng.random() < 0.1 else name

    def person_plain(self) -> str:
        name = strip_diacritics(self.person())
        return name.lower() if self._rng.random() < 0.6 else name

    def address(self) -> str:
        fmt = self._address_format
        if fmt == "mixed":
            fmt = "post_2025" if self._rng.random() < 0.5 else "pre_2025"
        number = str(self._rng.randint(1, 450))
        if self._rng.random() < 0.3:
            number += f"/{self._rng.randint(1, 60)}"
        street = f"{'số ' if self._rng.random() < 0.5 else ''}{number} {'đường ' if self._rng.random() < 0.4 else ''}{self._rng.choice(lx.STREETS)}"
        if fmt == "post_2025":
            ward, province = self._rng.choice(lx.WARDS_POST_2025)
            return f"{street}, {ward}, {province}"
        ward, district, province = self._rng.choice(lx.WARDS_PRE_2025)
        return f"{street}, {ward}, {district}, {province}"

    def phone(self) -> str:
        national = self._rng.choice(sorted(MOBILE_PREFIXES)) + self._digits(7)
        style = self._rng.random()
        if style < 0.45:
            return national
        if style < 0.65:
            return f"{national[:4]} {national[4:7]} {national[7:]}"
        if style < 0.8:
            return f"{national[:4]}.{national[4:7]}.{national[7:]}"
        return f"+84 {national[1:4]} {national[4:7]} {national[7:]}"

    def email(self) -> str:
        given = strip_diacritics(self.given_name()).lower()
        surname = strip_diacritics(self._rng.choice(lx.SURNAMES)).lower()
        sep = self._rng.choice([".", "", "_"])
        return f"{given}{sep}{surname}{self._rng.randint(1, 2005)}@{self._rng.choice(lx.EMAIL_DOMAINS)}"

    def national_id(self) -> str:
        province = self._rng.choice(sorted(PROVINCE_CODES))
        year = self._rng.randint(1950, 2008)
        century_gender = (0 if year < 2000 else 2) + self._rng.randint(0, 1)
        return f"{province}{century_gender}{year % 100:02d}{self._digits(6)}"

    def passport(self) -> str:
        return self._rng.choice(lx.PASSPORT_LETTERS) + self._digits(7)

    def tax_code(self) -> str:
        while True:
            first_nine = self._digits(9)
            check = tax_check_digit(first_nine)
            if check is not None:
                code = f"{first_nine}{check}"
                if self._rng.random() < 0.15:
                    code += f"-{self._rng.randint(1, 999):03d}"
                return code

    def card_number(self) -> str:
        body = self._rng.choice("45") + self._digits(14)
        total = 0
        for index, char in enumerate(reversed(body)):
            digit = int(char)
            if index % 2 == 0:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        number = body + str((10 - total % 10) % 10)
        if self._rng.random() < 0.5:
            return " ".join(number[i : i + 4] for i in range(0, 16, 4))
        return number

    def license_plate(self) -> str:
        province = self._rng.randint(11, 99)
        tail = f"{self._digits(3)}.{self._digits(2)}"
        if self._rng.random() < 0.6:
            return f"{province}{self._rng.choice(lx.PLATE_SERIES_CAR)}-{tail}"
        return f"{province}-{self._rng.choice(lx.PLATE_SERIES_BIKE)} {tail}"

    def date_of_birth(self) -> str:
        day, month, year = (
            self._rng.randint(1, 28),
            self._rng.randint(1, 12),
            self._rng.randint(1950, 2008),
        )
        style = self._rng.random()
        if style < 0.6:
            return f"{day:02d}/{month:02d}/{year}"
        if style < 0.8:
            return f"{day}/{month}/{year}"
        return f"ngày {day} tháng {month} năm {year}"

    # ----- examples -----------------------------------------------------------
    def fill(self, template_id: str, domain: str, template: str, index: int) -> Example:
        pieces: list[str] = []
        spans: list[GoldSpan] = []
        cursor = 0
        length = 0
        for match in _PLACEHOLDER.finditer(template):
            literal = template[cursor : match.start()]
            pieces.append(literal)
            length += len(literal)
            entity_type, make = self._fillers[match.group(1)]
            value = make()
            if entity_type is not None:
                spans.append(GoldSpan(length, length + len(value), entity_type.value))
            pieces.append(value)
            length += len(value)
            cursor = match.end()
        pieces.append(template[cursor:])
        return Example(
            id=f"{template_id}-{index:06d}",
            text="".join(pieces),
            spans=tuple(spans),
            meta={
                "template_id": template_id,
                "domain": domain,
                "address_format": self._address_format,
            },
        )

    def generate(self, n: int, *, negative_ratio: float = 0.2) -> Iterator[Example]:
        for index in range(n):
            pool = NEGATIVE_TEMPLATES if self._rng.random() < negative_ratio else TEMPLATES
            template_id, domain, template = self._rng.choice(pool)
            yield self.fill(template_id, domain, template, index)
