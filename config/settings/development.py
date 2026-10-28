from .base import *  # noqa: F403
from .base import env, env_bool, env_list

DEBUG = True
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ("localhost", "127.0.0.1", "0.0.0.0", "web"))
API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", True)

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
