import json

import pytest

from vi_pii_guard.cli import main


def test_redact_prints_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["redact", "SĐT 0912345678"]) == 0
    assert capsys.readouterr().out.strip() == "SĐT [PHONE_1]"


def test_detect_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["detect", "email a@b.vn", "--json"]) == 0
    spans = json.loads(capsys.readouterr().out)
    assert spans[0]["entity_type"] == "EMAIL"


def test_reads_stdin(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("CCCD 079204123456"))
    assert main(["redact", "-", "--strategy", "mask"]) == 0
    assert capsys.readouterr().out.strip() == "CCCD [NATIONAL_ID]"
