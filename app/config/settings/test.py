import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.sqlite3")

from .base import *  # noqa: E402,F403

DEBUG = False
LOCAL_SYNTHETIC_AUTH_ENABLED = True
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
AUDIT_CHECKPOINT_REQUIRED = False
