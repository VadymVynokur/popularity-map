import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("popularity_map")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
