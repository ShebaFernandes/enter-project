"""Private resume scanning and bounded, source-backed text extraction."""

from __future__ import annotations

import hashlib
import re
import socket
import struct
import subprocess  # nosec B404 -- bounded local document utilities, without a shell
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from defusedxml import ElementTree  # type: ignore[import-untyped]
from django.conf import settings
from django.db import connection, transaction

from .models import ResumeAsset
from .resume_service import MAX_SIZE, record_parse_result, record_scan_result

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def storage_client():
    kwargs = {"region_name": settings.AWS_REGION, "config": Config(signature_version="s3v4")}
    if settings.S3_INTERNAL_ENDPOINT_URL:
        kwargs.update(
            endpoint_url=settings.S3_INTERNAL_ENDPOINT_URL,
            aws_access_key_id="test",
            aws_secret_access_key="test",  # noqa: S106  # nosec B106 -- LocalStack only
        )
    return boto3.client("s3", **kwargs)


def scan_bytes(content: bytes) -> bool:
    if not settings.CLAMAV_HOST:
        raise RuntimeError("Scanner is not configured")
    with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=30) as sock:
        sock.sendall(b"zINSTREAM\0")
        for offset in range(0, len(content), 65536):
            chunk = content[offset : offset + 65536]
            sock.sendall(struct.pack("!I", len(chunk)) + chunk)
        sock.sendall(struct.pack("!I", 0))
        response = b""
        while b"\0" not in response and len(response) < 4096:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
    if response.rstrip(b"\0\n").endswith(b": OK"):
        return True
    if response.rstrip(b"\0\n").endswith(b" FOUND"):
        return False
    raise RuntimeError("Scanner did not return a verdict")


def detected_type(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        return "application/msword"
    if content.startswith(b"PK"):
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if "word/document.xml" in archive.namelist():
                return DOCX
    return "application/octet-stream"


def run_tool(arguments: list[str], timeout: int = 30) -> str:
    result = subprocess.run(  # noqa: S603  # nosec B603 -- fixed tools, generated paths, no shell
        arguments,
        capture_output=True,
        check=True,
        timeout=timeout,
    )
    return result.stdout.decode("utf-8", errors="replace")


def extract_text(content: bytes, mime: str) -> str:
    if mime == DOCX:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = [
                item
                for item in archive.infolist()
                if re.fullmatch(r"word/(?:document|header\d+|footer\d+)\.xml", item.filename)
            ]
            if sum(item.file_size for item in entries) > 20_000_000:
                raise ValueError("Document expands beyond the extraction limit")
            paragraphs = []
            for item in entries:
                xml = archive.read(item)
                if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                    raise ValueError("Unsupported XML declarations")
                root = ElementTree.fromstring(xml)
                for paragraph in root.iter(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                ):
                    paragraphs.append("".join(paragraph.itertext()))
            return "\n".join(paragraphs)
    with tempfile.TemporaryDirectory(prefix="resume-") as folder:
        path = Path(folder) / ("resume.pdf" if mime == "application/pdf" else "resume.doc")
        path.write_bytes(content)
        if mime == "application/msword":
            return run_tool(["antiword", str(path)])
        info = run_tool(["pdfinfo", str(path)])
        pages = re.search(r"^Pages:\s+(\d+)", info, re.M)
        if not pages or int(pages[1]) > 30:
            raise ValueError("PDF exceeds the 30-page extraction limit")
        if re.search(r"^Encrypted:\s+yes", info, re.M):
            raise ValueError("Password-protected PDF")
        text = run_tool(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"])
        # OCR image-only pages, including scans mixed with text pages.
        chunks = text.split("\f")[: int(pages[1])]
        for number in range(1, int(pages[1]) + 1):
            existing = chunks[number - 1] if number <= len(chunks) else ""
            if len(re.sub(r"\W", "", existing)) >= 40:
                continue
            prefix = str(Path(folder) / f"page-{number}")
            run_tool(
                [
                    "pdftoppm",
                    "-f",
                    str(number),
                    "-l",
                    str(number),
                    "-scale-to",
                    "2200",
                    "-singlefile",
                    "-png",
                    str(path),
                    prefix,
                ]
            )
            ocr = run_tool(["tesseract", prefix + ".png", "stdout", "--psm", "3"])
            while len(chunks) < number:
                chunks.append("")
            chunks[number - 1] = ocr
        return "\n".join(chunks)


SKILLS = (
    "Python",
    "JavaScript",
    "TypeScript",
    "Java",
    "C++",
    "C#",
    "Go",
    "Golang",
    "Rust",
    "Ruby",
    "PHP",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "React",
    "Next.js",
    "Node.js",
    "Django",
    "Flask",
    "FastAPI",
    "Spring Boot",
    "Kafka",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "GCP",
    "Git",
    "GitHub",
    "HTML",
    "CSS",
    "Tailwind",
    "TensorFlow",
    "PyTorch",
    "Pandas",
    "NumPy",
    "Scikit-learn",
    "LangChain",
    "LangGraph",
    "LLM",
    "RAG",
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "Computer Vision",
    "Microservices",
    "Distributed Systems",
    "REST",
    "GraphQL",
    "Figma",
    "Excel",
    "Power BI",
    "Tableau",
    "Salesforce",
    "SAP",
    "Project Management",
    "Product Management",
    "Recruitment",
    "SEO",
    "Marketing",
)
ROLE_WORDS = (
    r"engineer|developer|designer|manager|analyst|scientist|consultant|recruiter|"
    r"architect|lead|specialist|intern|director|founder|accountant"
)


def extract_facts(text: str) -> list[dict]:
    text = text[:200_000]
    lines = [
        (m.group().strip(), m.start(), m.end())
        for m in re.finditer(r"[^\n\r\f]+", text)
        if m.group().strip()
    ]
    facts = []

    def add(kind, value, start, end, confidence=0.85):
        facts.append(
            {
                "fact_type": kind,
                "value": value,
                "confidence": confidence,
                "source_spans": [{"start_offset": start, "end_offset": end}],
            }
        )

    for line, start, end in lines[:8]:
        name = re.sub(r"^(?:name\s*[:\-]\s*)", "", line, flags=re.I).split("|")[0].strip()
        if (
            2 <= len(name.split()) <= 5
            and len(name) < 70
            and all(c.isalpha() or c in " .'-" for c in name)
            and not re.search(
                ROLE_WORDS + r"|resume|curriculum|summary|profile|skills|experience|education",
                name,
                re.I,
            )
        ):
            add("full_name", name.title() if name.isupper() else name, start, end, 0.9)
            break
    for line, start, end in lines[:15]:
        if (
            re.search(ROLE_WORDS, line, re.I)
            and len(line) < 120
            and not re.search(r"@|https?://|\d{4}", line)
        ):
            role = re.split(r"\s+at\s+|\s+[|–—]\s+", line, maxsplit=1, flags=re.I)
            add("current_role", role[0].strip(), start, end, 0.8)
            if len(role) == 2:
                add("current_company", role[1].strip(), start, end, 0.75)
            break
    skill_matches = [
        (skill, re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", text, re.I))
        for skill in SKILLS
    ]
    found = [(skill, match) for skill, match in skill_matches if match]
    if found:
        add(
            "skills",
            [skill for skill, _ in found],
            min(m.start() for _, m in found),
            max(m.end() for _, m in found),
            0.95,
        )
    # Explicitly labelled arbitrary locations, with common cities as a fallback.
    location = re.search(r"(?:location|based in|address)\s*[:\-]\s*([^\n|;]+)", text, re.I)
    if not location:
        location = re.search(
            r"\b(Bengaluru|Bangalore|Mumbai|Pune|Delhi|Hyderabad|Chennai|Kolkata|Noida|"
            r"Gurugram|Gurgaon|London|New York|San Francisco|Remote)\b",
            text[:2000],
            re.I,
        )
    if location:
        add("location", location[1].strip(), location.start(), location.end(), 0.85)
    experience = re.search(
        r"\b(\d{1,2}(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:(?:of|professional|total|work|industry|relevant)\s+){0,3}experience\b",
        text,
        re.I,
    )
    if experience:
        add("experience_years", experience[1], experience.start(), experience.end(), 0.95)
    notice = re.search(
        r"(?:notice\s*(?:period)?|availability)\s*[:\-]\s*(immediate|\d+\s*(?:days?|months?|weeks?))",
        text,
        re.I,
    )
    if notice:
        add("notice_period", notice[1], notice.start(), notice.end(), 0.95)
    links = list(
        re.finditer(r"https?://(?:www\.)?(?:linkedin\.com|github\.com)/[^\s<>]+", text, re.I)
    )
    if links:
        add(
            "professional_links",
            [m.group().rstrip(".,)") for m in links],
            links[0].start(),
            links[-1].end(),
            0.95,
        )
    # Keep full readable text as a reviewable source; no invented dates or employers.
    if text.strip():
        add("resume_text", text.strip(), 0, len(text), 1)
    return facts


def process_resume(resume_id: str, actor_id: str) -> None:
    # Actor is from the trusted server-created event, never supplied by a client.
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.identity_id', %s, true)", [actor_id])
        resume = (
            ResumeAsset.objects.select_for_update()
            .filter(
                pk=resume_id,
                profile__identity_id=actor_id,
                deleted_at__isnull=True,
                scan_status=ResumeAsset.ScanStatus.SCANNING,
            )
            .first()
        )
        if resume is None:
            return
        try:
            client = storage_client()
            response = client.get_object(
                Bucket=settings.RESUME_QUARANTINE_BUCKET, Key=resume.quarantine_key
            )
            with response["Body"] as body:
                content = body.read(MAX_SIZE + 1)
            if (
                len(content) != resume.size_bytes
                or hashlib.sha256(content).hexdigest() != resume.sha256
            ):
                record_scan_result(
                    resume=resume,
                    clean=False,
                    detected_mime="application/octet-stream",
                    provider_reference="integrity-check",
                )
                return
            mime = detected_type(content)
            clean = scan_bytes(content)
            record_scan_result(
                resume=resume,
                clean=clean,
                detected_mime=mime,
                provider_reference="clamav-instream",
                observed_size=len(content),
            )
            if resume.scan_status != ResumeAsset.ScanStatus.CLEAN:
                return
            client.put_object(
                Bucket=settings.RESUME_QUARANTINE_BUCKET,
                Key=resume.clean_key,
                Body=content,
                ContentType=mime,
            )
        except Exception:
            # Never log file bytes or parser output; fail closed if scanning is unavailable.
            resume.scan_status = ResumeAsset.ScanStatus.SCAN_FAILED
            resume.clean_key = ""
            resume.parse_status = ResumeAsset.ParseStatus.NOT_STARTED
            resume.save(update_fields=["scan_status", "clean_key", "parse_status"])
            return
        try:
            text = extract_text(content, mime)
            if len(re.sub(r"\W", "", text)) < 20:
                raise ValueError("No readable resume text")
            record_parse_result(resume=resume, suggestions=extract_facts(text))
        except Exception:
            record_parse_result(resume=resume, suggestions=None, failed=True)
