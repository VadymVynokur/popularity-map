from .base import *  # noqa: F403
from .base import env, env_bool

DEBUG = False
API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", True)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Tests use isolated Redis logical databases supplied by CI/local compose.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("TEST_REDIS_CACHE_URL", "redis://localhost:6379/15"),
        "KEY_PREFIX": "popularity-map-test",
        "TIMEOUT": 60,
    }
}
REDIS_VIEW_COOLDOWN_URL = env("TEST_REDIS_VIEW_COOLDOWN_URL", "redis://localhost:6379/14")
CELERY_BROKER_URL = env("TEST_CELERY_BROKER_URL", "redis://localhost:6379/13")
