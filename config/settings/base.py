import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable {name} is not set.")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: tuple[str, ...] = ()) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-development-key-change-me")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ("localhost", "127.0.0.1"))
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
    "apps.categories",
    "apps.locations",
    "apps.reviews",
    "apps.subscriptions",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "popularity_map"),
        "USER": env("POSTGRES_USER", "popularity_map"),
        "PASSWORD": env("POSTGRES_PASSWORD", "popularity_map"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE_SECONDS", 1_209_600)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_CACHE_URL", "redis://localhost:6379/0"),
        "KEY_PREFIX": env("CACHE_KEY_PREFIX", "popularity-map"),
        "TIMEOUT": env_int("LOCATION_LIST_CACHE_TTL_SECONDS", 60),
    }
}
LOCATION_LIST_CACHE_TTL_SECONDS = env_int("LOCATION_LIST_CACHE_TTL_SECONDS", 60)
VIEW_COOLDOWN_SECONDS = env_int("VIEW_COOLDOWN_SECONDS", 3600)
REDIS_VIEW_COOLDOWN_URL = env("REDIS_VIEW_COOLDOWN_URL", "redis://localhost:6379/2")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.common.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "URL_FORMAT_OVERRIDE": None,
    "DEFAULT_THROTTLE_RATES": {
        "login": env("LOGIN_THROTTLE_RATE", "10/min"),
        "password_reset": env("PASSWORD_RESET_THROTTLE_RATE", "5/hour"),
        "email_resend": env("EMAIL_RESEND_THROTTLE_RATE", "3/hour"),
        "email_resend_ip": env("EMAIL_RESEND_IP_THROTTLE_RATE", "3/hour"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Location Popularity Map API",
    "DESCRIPTION": "REST API for locations, reviews, reactions, popularity and subscriptions.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"cookieAuth": []}],
}

API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", False)

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 1025)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@popularity-map.local")
EMAIL_CONFIRMATION_TIMEOUT_SECONDS = env_int("EMAIL_CONFIRMATION_TIMEOUT_SECONDS", 86_400)
EMAIL_CONFIRMATION_URL = env(
    "EMAIL_CONFIRMATION_URL", "http://localhost:8000/api/v1/auth/email/confirm/"
)
PASSWORD_RESET_URL = env(
    "PASSWORD_RESET_URL", "http://localhost:8000/api/v1/auth/password/reset/confirm/"
)

CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = None
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "sweep-pending-email-deliveries": {
        "task": "apps.notifications.tasks.sweep_pending_email_deliveries",
        "schedule": 60.0,
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
