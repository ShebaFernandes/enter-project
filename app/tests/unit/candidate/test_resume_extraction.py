import zipfile
from io import BytesIO
from unittest.mock import patch

import pytest

from modules.candidate.resume_processing import (
    DOCX,
    detected_type,
    extract_facts,
    extract_text,
    scan_bytes,
)


def document(text):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.splitlines())
            + "</w:body></w:document>",
        )
    return buffer.getvalue()


def test_word_extracts_actual_document_text_and_source_backed_facts():
    content = document(
        "Avery Taylor\nSenior Software Engineer\nLocation: Bengaluru\n"
        "5.6 years of experience\nPython, Django, PostgreSQL\nNotice period: 30 days"
    )
    assert detected_type(content) == DOCX
    text = extract_text(content, DOCX)
    facts = {fact["fact_type"]: fact for fact in extract_facts(text)}
    assert facts["full_name"]["value"] == "Avery Taylor"
    assert facts["current_role"]["value"] == "Senior Software Engineer"
    assert facts["experience_years"]["value"] == "5.6"
    assert facts["notice_period"]["value"] == "30 days"
    assert facts["skills"]["value"] == ["Python", "PostgreSQL", "Django"]
    assert all(fact["source_spans"] for fact in facts.values())


def test_missing_details_are_not_invented():
    facts = {fact["fact_type"] for fact in extract_facts("Avery Taylor\nPython developer\nPython")}
    assert "experience_years" not in facts
    assert "current_company" not in facts
    assert "notice_period" not in facts


def test_xml_entity_declarations_are_rejected():
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "word/document.xml", '<!DOCTYPE doc [<!ENTITY test "bad">]><doc>&test;</doc>'
        )
    with pytest.raises(ValueError):
        extract_text(stream.getvalue(), DOCX)


def test_unconfigured_scanner_cannot_mark_content_clean(settings):
    settings.CLAMAV_HOST = ""
    with pytest.raises(RuntimeError):
        scan_bytes(b"test")


@pytest.mark.parametrize(
    "verdict,expected", [(b"stream: OK\0", True), (b"stream: Test FOUND\0", False)]
)
def test_scanner_protocol_requires_explicit_verdict(settings, verdict, expected):
    settings.CLAMAV_HOST = "scanner"
    with patch("modules.candidate.resume_processing.socket.create_connection") as connect:
        sock = connect.return_value.__enter__.return_value
        sock.recv.return_value = verdict
        assert scan_bytes(b"content") is expected
        assert sock.sendall.call_args_list[0].args == (b"zINSTREAM\0",)


def test_scanner_errors_are_not_clean_verdicts(settings):
    settings.CLAMAV_HOST = "scanner"
    with patch("modules.candidate.resume_processing.socket.create_connection") as connect:
        sock = connect.return_value.__enter__.return_value
        sock.recv.return_value = b"stream: ERROR\0"
        with pytest.raises(RuntimeError):
            scan_bytes(b"content")
