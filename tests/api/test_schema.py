import os
import subprocess
import sys

import pytest
import yaml
from django.urls import reverse


@pytest.mark.django_db
def test_schema_and_swagger_are_available_when_enabled(api_client):
    schema_response = api_client.get(reverse("schema"))
    docs_response = api_client.get(reverse("swagger-ui"))

    assert schema_response.status_code == 200
    assert docs_response.status_code == 200

    schema = yaml.safe_load(schema_response.content)
    assert {
        "/api/v1/auth/register/",
        "/api/v1/auth/login/",
        "/api/v1/categories/",
        "/api/v1/locations/",
        "/api/v1/locations/export/",
        "/api/v1/locations/{location_id}/reviews/",
        "/api/v1/locations/{location_id}/subscription/",
        "/api/v1/reviews/{id}/reaction/",
    } <= set(schema["paths"])
    assert schema["components"]["securitySchemes"]["cookieAuth"]["name"] == "sessionid"

    location_list = schema["paths"]["/api/v1/locations/"]["get"]
    parameter_names = {parameter["name"] for parameter in location_list["parameters"]}
    assert {
        "search",
        "category",
        "author",
        "rating_min",
        "ordering",
        "page_size",
    } <= parameter_names


@pytest.mark.django_db
def test_schema_and_swagger_are_hidden_when_disabled(api_client, settings):
    settings.API_DOCS_ENABLED = False

    assert api_client.get(reverse("schema")).status_code == 404
    assert api_client.get(reverse("swagger-ui")).status_code == 404


def test_production_settings_fail_closed_without_required_environment():
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "DJANGO_SECRET_KEY",
            "DJANGO_ALLOWED_HOSTS",
            "DJANGO_CSRF_TRUSTED_ORIGINS",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "REDIS_CACHE_URL",
            "REDIS_VIEW_COOLDOWN_URL",
            "CELERY_BROKER_URL",
            "EMAIL_HOST",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "DEFAULT_FROM_EMAIL",
        }
    }
    environment["DJANGO_SETTINGS_MODULE"] = "config.settings.production"

    result = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Required environment variable DJANGO_SECRET_KEY is not set." in result.stderr
