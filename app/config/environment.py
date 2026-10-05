from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured


def _required(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if not value:
        raise ImproperlyConfigured(f"Missing required configuration: {name}")
    return value


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Environment:
    app_env: str
    secret_key: str
    canonical_origin: str
    csrf_trusted_origins: tuple[str, ...]
    database_url: str
    database_require_tls: bool
    valkey_url: str
    aws_region: str
    allowed_aws_regions: tuple[str, ...]
    s3_endpoint_url: str | None
    resume_quarantine_bucket: str
    cognito_issuer: str
    cognito_domain: str
    cognito_client_id: str
    cognito_client_secret: str
    cognito_callback_url: str
    email_lookup_key: bytes
    field_encryption_keys: tuple[tuple[str, bytes], ...]
    audit_checkpoint_required: bool
    whatsapp_enabled: bool

    @classmethod
    def load(cls) -> Environment:
        app_env = os.getenv("APP_ENV", "local")
        production = app_env == "production"
        secret_key = _required("DJANGO_SECRET_KEY", None if production else "unsafe-test-key")
        region = os.getenv("AWS_REGION", "ap-south-1")
        allowed = tuple(
            x.strip()
            for x in os.getenv("ALLOWED_AWS_REGIONS", "ap-south-1,ap-south-2").split(",")
            if x.strip()
        )
        if production and region not in allowed:
            raise ImproperlyConfigured("AWS_REGION must be in the India launch allowlist")
        key_entries: list[tuple[str, bytes]] = []
        for entry in _required(
            "FIELD_ENCRYPTION_KEYS", "v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        ).split(","):
            version, encoded = entry.split(":", 1)
            key = base64.urlsafe_b64decode(encoded)
            if len(key) != 32:
                raise ImproperlyConfigured("Each field encryption key must decode to 32 bytes")
            key_entries.append((version, key))
        return cls(
            app_env=app_env,
            secret_key=secret_key,
            canonical_origin=os.getenv("CANONICAL_ORIGIN", "http://localhost:8000"),
            csrf_trusted_origins=tuple(
                x.strip()
                for x in os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:8000").split(",")
                if x.strip()
            ),
            database_url=os.getenv("DATABASE_URL", "sqlite:///db.sqlite3"),
            database_require_tls=_bool("DATABASE_REQUIRE_TLS", production),
            valkey_url=os.getenv("VALKEY_URL", "redis://localhost:6379/0"),
            aws_region=region,
            allowed_aws_regions=allowed,
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            resume_quarantine_bucket=os.getenv(
                "RESUME_QUARANTINE_BUCKET", "enter-resume-quarantine"
            ),
            cognito_issuer=os.getenv("COGNITO_ISSUER", "https://example.invalid/local"),
            cognito_domain=_required(
                "COGNITO_DOMAIN", None if production else "https://example.invalid"
            ).rstrip("/"),
            cognito_client_id=os.getenv("COGNITO_CLIENT_ID", "local-client"),
            cognito_client_secret=os.getenv("COGNITO_CLIENT_SECRET", "local-secret"),
            cognito_callback_url=os.getenv(
                "COGNITO_CALLBACK_URL", "http://localhost:8000/api/v1/auth/callback"
            ),
            email_lookup_key=_required("EMAIL_LOOKUP_KEY", "unsafe-local-hmac-key").encode(),
            field_encryption_keys=tuple(key_entries),
            audit_checkpoint_required=_bool("AUDIT_CHECKPOINT_REQUIRED", production),
            whatsapp_enabled=_bool("WHATSAPP_ENABLED", False),
        )

    def database_config(self) -> dict[str, object]:
        parsed = urlparse(self.database_url)
        if parsed.scheme == "sqlite":
            path = parsed.path or "/db.sqlite3"
            return {"ENGINE": "django.db.backends.sqlite3", "NAME": path.lstrip("/")}
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ImproperlyConfigured("DATABASE_URL must be sqlite or PostgreSQL")
        options: dict[str, str] = {}
        if self.database_require_tls:
            options["sslmode"] = "require"
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": parsed.port or 5432,
            "CONN_MAX_AGE": 60,
            "OPTIONS": options,
        }
