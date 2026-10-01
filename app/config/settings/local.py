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

FRONTEND_REACT_ROUTES = {}
