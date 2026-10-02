import os

from .base import *  # noqa: F403

DEBUG = True
LOCAL_SYNTHETIC_AUTH_ENABLED = True
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_NAME = "enter_local_session"
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_NAME = "enter_local_csrf"
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "mail"
EMAIL_PORT = 1025
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": ENV.valkey_url,  # noqa: F405
    }
}

# Vite writes reviewed development bundles here. Production still serves only
# collected/versioned assets from its deployment image.
STATICFILES_DIRS = [BASE_DIR / "static"]  # noqa: F405

# Local preview flags are explicit process configuration; absence remains safely
# default-off. Production settings do not read this development-only variable.
FRONTEND_REACT_ROUTES = {
    route.strip(): True
    for route in os.environ.get("FRONTEND_REACT_ROUTES", "").split(",")
    if route.strip()
}
