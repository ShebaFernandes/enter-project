from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

ALLOWED_HOSTS = [ENV.canonical_origin.split("://", 1)[-1].split("/", 1)[0]]  # noqa: F405
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CACHES: dict[str, dict[str, object]] = {  # type: ignore[no-redef]
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": ENV.valkey_url,  # noqa: F405
        "OPTIONS": {"socket_timeout": 1, "socket_connect_timeout": 1},
    }
}
if not ENV.database_require_tls:  # noqa: F405
    raise ImproperlyConfigured("Production database TLS is mandatory")
