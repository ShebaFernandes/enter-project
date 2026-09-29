from .base import *  # noqa: F403

DEBUG = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "mail"
EMAIL_PORT = 1025
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": ENV.valkey_url,  # noqa: F405
    }
}
