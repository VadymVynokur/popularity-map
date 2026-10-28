from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.locations.models import Location, LocationView
from apps.notifications.models import EmailDelivery
from apps.reviews.models import Review, ReviewReaction
from apps.subscriptions.models import LocationSubscription

FIXTURE_PATH = Path(settings.BASE_DIR) / "fixtures" / "manual_testing.json"


@pytest.mark.django_db
def test_manual_testing_fixture_loads_and_covers_key_scenarios(api_client):
    call_command("loaddata", str(FIXTURE_PATH), verbosity=0)

    assert User.objects.filter(pk__in=range(9001, 9008)).count() == 7
    assert User.objects.get(pk=9001).role == User.Role.ADMIN
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"]):
        assert User.objects.get(pk=9002).check_password("ManualTest123!")
    assert not User.objects.get(pk=9005).email_verified
    assert not User.objects.get(pk=9007).is_active

    assert Location.objects.active().count() == 3
    assert Location.objects.deleted().count() == 1
    assert Location.objects.get(pk=9101).categories.count() == 2
    assert Review.objects.active().count() == 5
    assert Review.objects.deleted().count() == 1
    assert ReviewReaction.objects.count() == 4
    assert LocationSubscription.objects.filter(is_active=True).count() == 3
    assert LocationView.objects.count() == 3
    assert EmailDelivery.objects.count() == 0

    response = api_client.get(reverse("location-list"), {"search": "Manual Riverside"})
    assert response.status_code == 200
    assert response.data["count"] == 1
    row = response.data["results"][0]
    assert row["id"] == 9101
    assert row["rating"] == Decimal("4.7")
    assert row["review_count"] == 3
    assert row["views_7d"] == 0
    assert row["popularity"] == pytest.approx(53.92, abs=0.01)

    deleted_client = APIClient()
    deleted_client.force_authenticate(User.objects.get(pk=9002))
    deleted = deleted_client.get(reverse("location-deleted-list"))
    assert deleted.status_code == 200
    assert [item["id"] for item in deleted.data["results"]] == [9103]
