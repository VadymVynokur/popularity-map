from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"

    def ready(self) -> None:
        # Importing registers the drf-spectacular authentication extension.
        from apps.common import schema  # noqa: F401
