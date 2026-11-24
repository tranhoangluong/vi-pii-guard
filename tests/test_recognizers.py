import pytest

from vi_pii_guard import EntityType, Guard
from vi_pii_guard.domain import Span
from vi_pii_guard.recognizers.address import TriggerAddressRecognizer
from vi_pii_guard.recognizers.names import TriggerNameRecognizer
from vi_pii_guard.resolver import resolve_overlaps


@pytest.fixture(scope="module")
def guard() -> Guard:
    return Guard.default()


def found(guard: Guard, text: str) -> list[tuple[str, str]]:
    return [(s.entity_type.value, s.text) for s in guard.detect(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("SĐT 0912 345 678", ("PHONE", "0912 345 678")),
        ("so dien thoai 0987654321 nha", ("PHONE", "0987654321")),
        ("gọi +84 912 345 678", ("PHONE", "+84 912 345 678")),
        ("email: an.nguyen99@gmail.com.", ("EMAIL", "an.nguyen99@gmail.com")),
        ("CCCD 079204123456", ("NATIONAL_ID", "079204123456")),
        ("CMND: 123456789", ("NATIONAL_ID", "123456789")),
        ("hộ chiếu C1234567", ("PASSPORT", "C1234567")),
        ("biển số 51F-123.45", ("LICENSE_PLATE", "51F-123.45")),
        ("xe 59-X1 123.45 đỗ trước cửa", ("LICENSE_PLATE", "59-X1 123.45")),
        ("thẻ 4111 1111 1111 1111", ("CARD_NUMBER", "4111 1111 1111 1111")),
        ("sinh ngày 12/05/1990", ("DATE_OF_BIRTH", "12/05/1990")),
    ],
)
def test_structured_entities(guard: Guard, text: str, expected: tuple[str, str]) -> None:
    assert expected in found(guard, text)


def test_context_disambiguates_phone_and_tax_code(guard: Guard) -> None:
    from vi_pii_guard.validators import tax_check_digit

    code = "031234567" + str(tax_check_digit("031234567"))
    assert found(guard, f"MST: {code}") == [("TAX_CODE", code)]


def test_bank_account_needs_context(guard: Guard) -> None:
    assert found(guard, "STK 19034567890123 Techcombank") == [("BANK_ACCOUNT", "19034567890123")]
    assert found(guard, "Mã đơn 19034567890123") == []


@pytest.mark.parametrize(
    "text",
    [
        "Đơn hàng 202611230045 đã giao lúc 10:30.",
        "Giá 1.250.000đ, mua 2 tặng 1.",
        "Hotline 1900 6789 hỗ trợ 24/7.",
        "Shop ở Hà Nội có giao ra TP. Hồ Chí Minh không?",
    ],
)
def test_hard_negatives(guard: Guard, text: str) -> None:
    assert found(guard, text) == []


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("Tôi tên là Nguyễn Văn An, SĐT 0912345678", "Nguyễn Văn An"),
        ("Họ tên: NGUYỄN THỊ HOA", "NGUYỄN THỊ HOA"),
        ("nhờ anh Minh gọi lại", "Minh"),
        ("Chị Lan ơi", "Lan"),
        ("Tôi là Lê Văn Nam, cần hỗ trợ", "Lê Văn Nam"),
    ],
)
def test_trigger_names(text: str, name: str) -> None:
    assert name in [s.text for s in TriggerNameRecognizer().recognize(text)]


def test_names_skip_acronyms_and_lowercase() -> None:
    assert TriggerNameRecognizer().recognize("khách hàng VIP") == []
    assert TriggerNameRecognizer().recognize("tôi là sinh viên") == []
    assert TriggerNameRecognizer().recognize("Tôi là Giám đốc chi nhánh") == []


@pytest.mark.parametrize(
    ("text", "address"),
    [
        (
            "Giao hàng đến địa chỉ: số 12 đường Lê Lợi, phường Bến Thành, TP. Hồ Chí Minh. Cảm ơn!",
            "số 12 đường Lê Lợi, phường Bến Thành, TP. Hồ Chí Minh",
        ),
        (
            "Địa chỉ: 5 Lê Duẩn, phường 6, quận 3, TP.HCM, SĐT 0912345678",
            "5 Lê Duẩn, phường 6, quận 3, TP.HCM",
        ),
        (
            "giao tới 276 Nguyễn Huệ, phường Thạch Thang, quận Hải Châu, Đà Nẵng bị trễ rồi",
            "276 Nguyễn Huệ, phường Thạch Thang, quận Hải Châu, Đà Nẵng",
        ),
        (
            "dia chi 12 le loi, phuong ben thanh, tp. ho chi minh",
            "12 le loi, phuong ben thanh, tp. ho chi minh",
        ),
    ],
)
def test_trigger_address(text: str, address: str) -> None:
    assert [s.text for s in TriggerAddressRecognizer().recognize(text)][:1] == [address]


def test_resolver_prefers_score_then_length() -> None:
    low = Span(0, 10, EntityType.TAX_CODE, "x" * 10, 0.6, "a")
    high = Span(0, 10, EntityType.PHONE, "x" * 10, 0.9, "b")
    inner = Span(2, 5, EntityType.PERSON, "xxx", 0.9, "c")
    assert resolve_overlaps([low, high, inner]) == [high]


def test_entity_filter_and_threshold() -> None:
    only_email = Guard.default(entities=[EntityType.EMAIL])
    assert found(only_email, "SĐT 0912345678, email a@b.vn") == [("EMAIL", "a@b.vn")]
    strict = Guard.default(min_score=0.99)
    assert found(strict, "0912345678") == []
