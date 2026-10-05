# ruff: noqa: E501
import hashlib
import os
import zipfile
from io import BytesIO
from unittest.mock import patch

import pytest

from modules.candidate.resume_processing import process_resume
from modules.candidate.resume_service import create_upload
from modules.operations.models import OutboxEvent

pytestmark = pytest.mark.django_db


def new_upload(profile, content):
    return create_upload(
        identity=profile.identity,
        profile=profile,
        values={
            "filename": "resume.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    )


def test_authenticated_content_upload_queues_only_once(api_client, profile_factory):
    profile = profile_factory()
    api_client.force_authenticate(profile.identity)
    data = b"%PDF-test content"
    resume = new_upload(profile, data)
    with patch("modules.candidate.resume_processing.storage_client") as storage:
        for _ in range(2):
            response = api_client.put(
                f"/api/v1/candidate/resumes/{resume.pk}/content",
                data,
                content_type="application/pdf",
                HTTP_CONTENT_DISPOSITION='attachment; filename="resume.pdf"',
            )
            assert response.status_code == 202, response.content
        assert storage.return_value.put_object.call_count == 1
    assert OutboxEvent.objects.filter(event_type="resume.processing_requested.v1").count() == 1


def test_upload_rejects_other_candidates_and_mismatched_bytes(api_client, profile_factory):
    owner, other = profile_factory(), profile_factory()
    resume = new_upload(owner, b"%PDF-data")
    api_client.force_authenticate(other.identity)
    path = f"/api/v1/candidate/resumes/{resume.pk}/content"
    assert api_client.put(path, b"%PDF-data", content_type="application/pdf").status_code == 404
    api_client.force_authenticate(owner.identity)
    response = api_client.put(
        path,
        b"incorrect",
        content_type="application/pdf",
        HTTP_CONTENT_DISPOSITION='attachment; filename="resume.pdf"',
    )
    assert response.status_code == 400
    assert not OutboxEvent.objects.filter(event_type="resume.processing_requested.v1").exists()


def test_scanner_outage_never_runs_parser(profile_factory):
    data = b"%PDF-data"
    resume = new_upload(profile_factory(), data)
    resume.scan_status = "SCANNING"
    resume.save()
    with (
        patch("modules.candidate.resume_processing.storage_client") as storage,
        patch("modules.candidate.resume_processing.scan_bytes", side_effect=OSError("offline")),
        patch("modules.candidate.resume_processing.extract_text") as parser,
    ):
        storage.return_value.get_object.return_value = {"Body": BytesIO(data)}
        process_resume(str(resume.pk), str(resume.profile.identity_id))
    parser.assert_not_called()
    resume.refresh_from_db()
    assert resume.scan_status == "SCAN_FAILED"
    assert not resume.clean_key
    assert not resume.facts.exists()


def pdf_document():
    stream = b"BT /F1 18 Tf 60 750 Td (Avery Taylor) Tj 0 -30 Td (Senior Software Engineer) Tj 0 -30 Td (Location: Bengaluru) Tj 0 -30 Td (5.6 years of experience) Tj 0 -30 Td (Python, Django, PostgreSQL) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    return pdf_objects(objects)


def pdf_objects(objects):
    content = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(content)
    content += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    content += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return (
        content
        + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )


@pytest.mark.skipif(
    os.environ.get("RUN_RESUME_LIVE") != "1", reason="Requires private S3 and ClamAV"
)
@pytest.mark.parametrize("kind", ["pdf", "docx", "scanned"])
def test_real_storage_scanner_and_extraction(profile_factory, api_client, settings, tmp_path, kind):
    import subprocess
    import zlib

    from modules.candidate.resume_processing import DOCX, storage_client

    settings.S3_INTERNAL_ENDPOINT_URL = "http://s3-local:4566"
    settings.CLAMAV_HOST = "resume-scanner"
    content = pdf_document()
    mime = "application/pdf"
    if kind == "docx":
        stream = BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Avery Taylor</w:t></w:r></w:p><w:p><w:r><w:t>Senior Software Engineer</w:t></w:r></w:p><w:p><w:r><w:t>Python, Django</w:t></w:r></w:p></w:body></w:document>',
            )
        content = stream.getvalue()
        mime = DOCX
    elif kind == "scanned":
        source = tmp_path / "source.pdf"
        source.write_bytes(content)
        subprocess.run(  # noqa: S603 -- fixed fixture conversion command
            [
                "/usr/bin/pdftoppm",
                "-scale-to",
                "1400",
                "-singlefile",
                str(source),
                str(tmp_path / "scan"),
            ],
            check=True,
            capture_output=True,
        )
        ppm = (tmp_path / "scan.ppm").read_bytes()
        _, dimensions, _, pixels = ppm.split(b"\n", 3)
        width, height = dimensions.split()
        image = zlib.compress(pixels)
        draw = b"q 612 0 0 792 0 0 cm /Im0 Do Q"
        content = pdf_objects(
            [
                b"<< /Type /Catalog /Pages 2 0 R >>",
                b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
                b"<< /Type /XObject /Subtype /Image /Width "
                + width
                + b" /Height "
                + height
                + b" /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length "
                + str(len(image)).encode()
                + b" >>\nstream\n"
                + image
                + b"\nendstream",
                b"<< /Length " + str(len(draw)).encode() + b" >>\nstream\n" + draw + b"\nendstream",
            ]
        )
    profile = profile_factory()
    resume = create_upload(
        identity=profile.identity,
        profile=profile,
        values={
            "filename": f"synthetic.{kind}",
            "content_type": mime,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    )
    client = storage_client()
    try:
        from django.core.management import call_command

        api_client.force_authenticate(profile.identity)
        response = api_client.put(
            f"/api/v1/candidate/resumes/{resume.pk}/content",
            content,
            content_type=mime,
            HTTP_CONTENT_DISPOSITION='attachment; filename="resume"',
        )
        assert response.status_code == 202, response.content
        call_command("run_outbox_worker", once=True, stdout=__import__("io").StringIO())
        resume.refresh_from_db()
        assert resume.scan_status == "CLEAN"
        assert resume.parse_status == "REVIEW_REQUIRED"
        facts = {fact.fact_type: fact.normalized_value for fact in resume.facts.all()}
        assert facts["full_name"] == "Avery Taylor"
        assert isinstance(facts["skills"], list)
        assert "Python" in facts["skills"]
    finally:
        for key in (resume.quarantine_key, f"clean/{profile.pk}/{resume.pk}"):
            client.delete_object(Bucket=settings.RESUME_QUARANTINE_BUCKET, Key=key)
