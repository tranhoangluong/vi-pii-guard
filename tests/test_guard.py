from vi_pii_guard import Guard
from vi_pii_guard.vault import InMemoryVault, RedactionSession


def test_redact_and_restore_round_trip() -> None:
    guard = Guard.default()
    result = guard.redact("Tôi tên là Nguyễn Văn An, SĐT 0912345678, email an@example.vn")
    assert result.text == "Tôi tên là [PERSON_1], SĐT [PHONE_1], email [EMAIL_1]"
    assert result.session_id is not None
    answer = "Chào [PERSON_1], chúng tôi sẽ gọi [PHONE_1]."
    assert (
        guard.restore(answer, result.session_id)
        == "Chào Nguyễn Văn An, chúng tôi sẽ gọi 0912345678."
    )


def test_same_value_same_placeholder_across_turns() -> None:
    guard = Guard.default()
    first = guard.redact("SĐT 0912 345 678")
    second = guard.redact("Gọi lại số 0912345678 nhé, hoặc 0987654321", session_id=first.session_id)
    assert second.session_id == first.session_id
    assert second.text == "Gọi lại số [PHONE_1] nhé, hoặc [PHONE_2]"


def test_restore_tolerates_reformatted_placeholders() -> None:
    guard = Guard.default()
    result = guard.redact("Họ tên: Trần Thị Mai")
    assert result.session_id
    assert guard.restore("Xin chào [ PERSON_1 ] và PERSON_1!", result.session_id) == (
        "Xin chào Trần Thị Mai và Trần Thị Mai!"
    )
    assert (
        guard.restore("[PERSON_9] không tồn tại", result.session_id) == "[PERSON_9] không tồn tại"
    )


def test_unknown_session_id_gets_a_fresh_random_id() -> None:
    guard = Guard.default()
    result = guard.redact("SĐT 0912345678", session_id="attacker-chosen-id")
    assert result.session_id != "attacker-chosen-id"


def test_mask_strategy_is_irreversible() -> None:
    result = Guard.default().redact("SĐT 0912345678", strategy="mask")
    assert result.text == "SĐT [PHONE]"
    assert result.session_id is None


def test_nfd_input_is_normalized() -> None:
    nfd = "Họ tên: Nguyễn Văn An"  # "Họ tên: Nguyễn Văn An" in NFD
    assert Guard.default().redact(nfd).text == "Họ tên: [PERSON_1]"


def test_forget_deletes_mapping() -> None:
    guard = Guard.default()
    result = guard.redact("SĐT 0912345678")
    assert result.session_id
    guard.forget(result.session_id)
    assert guard.restore("[PHONE_1]", result.session_id) == "[PHONE_1]"


def test_vault_ttl_and_lru() -> None:
    now = [0.0]
    vault = InMemoryVault(ttl_seconds=10, max_sessions=2, clock=lambda: now[0])
    for name in ("a", "b", "c"):
        vault.save(RedactionSession(name))
    assert vault.load("a") is None  # evicted (LRU)
    assert vault.load("b") is not None
    now[0] = 11.0
    assert vault.load("c") is None  # expired
    assert len(vault) == 0
