from .base import *  # noqa: F403
from .base import env_bool, env_int, require_env

DEBUG = False
SECRET_KEY = require_env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [
    host.strip() for host in require_env("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()
]
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must contain explicit production hosts.")

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in require_env("DJANGO_CSRF_TRUSTED_ORIGINS").split(",")
    if origin.strip()
]
if not CSRF_TRUSTED_ORIGINS or any(origin == "*" for origin in CSRF_TRUSTED_ORIGINS):
    raise RuntimeError("DJANGO_CSRF_TRUSTED_ORIGINS must contain explicit origins.")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", False)

DATABASES["default"].update(  # noqa: F405
    {
        "NAME": require_env("POSTGRES_DB"),
        "USER": require_env("POSTGRES_USER"),
        "PASSWORD": require_env("POSTGRES_PASSWORD"),
        "HOST": require_env("POSTGRES_HOST"),
        "PORT": require_env("POSTGRES_PORT"),
    }
)

CACHES["default"]["LOCATION"] = require_env("REDIS_CACHE_URL")  # noqa: F405
REDIS_VIEW_COOLDOWN_URL = require_env("REDIS_VIEW_COOLDOWN_URL")
CELERY_BROKER_URL = require_env("CELERY_BROKER_URL")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = require_env("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = require_env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = require_env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = require_env("DEFAULT_FROM_EMAIL")

SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE_SECONDS", 1_209_600)
