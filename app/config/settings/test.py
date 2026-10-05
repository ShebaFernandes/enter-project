import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
# Publication and tenant boundaries require PostgreSQL, including in tests.
# Django creates a separate test database; it never uses development tables.
os.environ.setdefault("DATABASE_URL", "postgresql://enter:enter@127.0.0.1:5432/enter")

from .base import *  # noqa: E402,F403

DEBUG = False
LOCAL_SYNTHETIC_AUTH_ENABLED = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
AUDIT_CHECKPOINT_REQUIRED = False
