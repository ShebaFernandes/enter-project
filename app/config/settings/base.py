from pathlib import Path

from config.environment import Environment

BASE_DIR = Path(__file__).resolve().parents[2]
ENV = Environment.load()
SECRET_KEY = ENV.secret_key
DEBUG = False
LOCAL_SYNTHETIC_AUTH_ENABLED = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = list(ENV.csrf_trusted_origins)
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "modules.operations",
    "modules.identity",
    "modules.tenancy",
    "modules.recruiting",
    "modules.candidate",
    "modules.privacy",
    "modules.communications",
    "modules.audit",
    "modules.abuse",
    "modules.search",
    "modules.ai",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "modules.operations.middleware.CorrelationIdMiddleware",
    "modules.operations.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "modules.candidate.rls.CandidateIdentityRLSMiddleware",
    "modules.identity.services.IdentityStatusMiddleware",
    "modules.tenancy.context.TenantContextMiddleware",
    "modules.abuse.service.RateLimitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "frontend" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": ENV.database_config()}
AUTH_USER_MODEL = "identity.Identity"
AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
AWS_REGION = ENV.aws_region
S3_ENDPOINT_URL = ENV.s3_endpoint_url
RESUME_QUARANTINE_BUCKET = ENV.resume_quarantine_bucket
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_NAME = "__Host-enter_session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_NAME = "__Host-enter_csrf"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "modules.operations.problems.problem_exception_handler",
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "enter-foundation",
    }
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact": {"()": "modules.operations.middleware.RedactionFilter"}},
    "formatters": {"json": {"format": '{"level":"%(levelname)s","message":"%(message)s"}'}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json", "filters": ["redact"]}
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
