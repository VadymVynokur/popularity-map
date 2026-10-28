from decimal import Decimal

import pytest
import redis
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.categories.models import Category
from apps.locations import cache as location_cache
from apps.locations import views as location_views
from apps.locations.models import Location, LocationView, LocationViewThrottle
from apps.locations.services import create_location, soft_delete_location
from apps.locations.view_tracking import track_location_view
from apps.reviews.models import Review


def _payload(**overrides):
    data = {
        "name": "Riverside Cafe",
        "description": "A small cafe next to the river.",
        "category_ids": [Category.objects.get(name="Cafe").pk],
        "address": "12 River Street",
        "latitude": "50.450100",
        "longitude": "30.523400",
    }
    data.update(overrides)
    return data


def _other_location(owner, name="Green Park") -> Location:
    location = Location.objects.create(
        name=name,
        description="A quiet green place.",
        address="1 Park Avenue",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=owner,
    )
    location.categories.set([Category.objects.get(name="Park")])
    return location


def _other_client() -> APIClient:
    user = User.objects.create_user(
        email="other@example.com",
        username="other_user",
        password="a-strong-password",
    )
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_successful_detail_records_one_view_per_identity_and_location(
    api_client,
    location,
    verified_user,
):
    second = _other_location(verified_user)

    first = api_client.get(reverse("location-detail", args=[location.pk]))
    second_request = api_client.get(reverse("location-detail", args=[location.pk]))
    other_location = api_client.get(reverse("location-detail", args=[second.pk]))

    assert first.status_code == second_request.status_code == other_location.status_code == 200
    assert first.data["views_7d"] == 0
    assert second_request.data["views_7d"] == 1
    assert LocationView.objects.filter(location=location).count() == 1
    assert LocationView.objects.filter(location=second).count() == 1
    assert LocationViewThrottle.objects.filter(location=location).count() == 1
    assert LocationViewThrottle.objects.filter(location=second).count() == 1


@pytest.mark.django_db
def test_authenticated_identity_has_independent_cooldown(auth_client, location):
    other = _other_client()

    auth_client.get(reverse("location-detail", args=[location.pk]))
    auth_client.get(reverse("location-detail", args=[location.pk]))
    other.get(reverse("location-detail", args=[location.pk]))

    assert LocationView.objects.filter(location=location).count() == 2


@pytest.mark.django_db
def test_view_cooldown_expires_after_configured_window(api_client, location):
    api_client.get(reverse("location-detail", args=[location.pk]))
    throttle = LocationViewThrottle.objects.get(location=location)
    throttle.last_counted_at = throttle.last_counted_at.replace(year=2020)
    throttle.save(update_fields=["last_counted_at"])
    redis.Redis.from_url(settings.REDIS_VIEW_COOLDOWN_URL).flushdb()

    api_client.get(reverse("location-detail", args=[location.pk]))

    assert LocationView.objects.filter(location=location).count() == 2


@pytest.mark.django_db
def test_only_successful_active_detail_requests_create_views(api_client, location, verified_user):
    second = _other_location(verified_user)
    soft_delete_location(second)

    api_client.get(reverse("location-list"))
    api_client.get(reverse("location-export"), {"format": "json"})
    api_client.get(reverse("location-review-list", args=[location.pk]))
    api_client.get(reverse("location-detail", args=[99999]))
    api_client.get(reverse("location-detail", args=[second.pk]))

    assert LocationView.objects.count() == 0


@pytest.mark.django_db
def test_redis_unavailable_falls_back_to_database_cooldown(api_client, location, monkeypatch):
    monkeypatch.setattr("apps.locations.view_tracking._claim_redis", lambda key: None)
    monkeypatch.setattr("apps.locations.view_tracking._set_redis", lambda key, ttl: None)

    api_client.get(reverse("location-detail", args=[location.pk]))
    api_client.get(reverse("location-detail", args=[location.pk]))

    assert LocationView.objects.filter(location=location).count() == 1
    assert LocationViewThrottle.objects.filter(location=location).count() == 1


@pytest.mark.django_db
def test_failed_view_insert_does_not_leave_redis_cooldown(location, monkeypatch):
    monkeypatch.setattr(
        "apps.locations.view_tracking.LocationView.objects.create",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    with pytest.raises(RuntimeError):
        track_location_view(location, "user:123")

    client = redis.Redis.from_url(settings.REDIS_VIEW_COOLDOWN_URL)
    assert client.keys("*") == []


@pytest.mark.django_db
def test_list_cache_hit_and_location_write_invalidation(
    api_client,
    auth_client,
    location,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    calls = []
    original = location_views.build_location_queryset

    def counted(params):
        calls.append(1)
        return original(params)

    monkeypatch.setattr(location_views, "build_location_queryset", counted)

    first = api_client.get(reverse("location-list"))
    second = api_client.get(reverse("location-list"))
    assert first.data["count"] == second.data["count"] == 1
    assert len(calls) == 1

    with django_capture_on_commit_callbacks(execute=True):
        created = auth_client.post(
            reverse("location-list"),
            _payload(name="New Cafe"),
            format="json",
        )
    assert created.status_code == 201

    third = api_client.get(reverse("location-list"))
    assert third.data["count"] == 2
    assert len(calls) == 2


@pytest.mark.django_db
def test_category_rename_invalidates_list_cache(
    api_client,
    admin_client,
    location,
    django_capture_on_commit_callbacks,
):
    assert (
        api_client.get(reverse("location-list")).data["results"][0]["categories"][0]["name"]
        == "Cafe"
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.patch(
            reverse("category-detail", args=[location.categories.first().pk]),
            {"name": "Coffee house"},
            format="json",
        )
    assert response.status_code == 200

    result = api_client.get(reverse("location-list")).data["results"][0]
    assert result["categories"][0]["name"] == "Coffee house"


@pytest.mark.django_db
def test_review_write_invalidates_list_cache(
    api_client,
    auth_client,
    location,
    django_capture_on_commit_callbacks,
):
    assert api_client.get(reverse("location-list")).data["results"][0]["rating"] is None

    with django_capture_on_commit_callbacks(execute=True):
        created = auth_client.post(
            reverse("location-review-list", args=[location.pk]),
            {"rating": 4, "comment": "Good"},
            format="json",
        )
    assert created.status_code == 201

    result = api_client.get(reverse("location-list")).data["results"][0]
    assert result["rating"] == 4.0
    assert result["review_count"] == 1


@pytest.mark.django_db
def test_view_and_reaction_do_not_invalidate_list_cache(
    api_client,
    auth_client,
    location,
    verified_user,
    monkeypatch,
):
    calls = []
    original = location_views.build_location_queryset

    def counted(params):
        calls.append(1)
        return original(params)

    monkeypatch.setattr(location_views, "build_location_queryset", counted)
    api_client.get(reverse("location-list"))
    assert len(calls) == 1

    api_client.get(reverse("location-detail", args=[location.pk]))
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Great",
    )
    auth_client.put(
        reverse("review-reaction", args=[review.pk]),
        {"type": "like"},
        format="json",
    )
    api_client.get(reverse("location-list"))

    assert len(calls) == 1


@pytest.mark.django_db
def test_cache_key_is_canonical_for_query_parameter_order(
    api_client,
    location,
    monkeypatch,
):
    calls = []
    original = location_views.build_location_queryset

    def counted(params):
        calls.append(1)
        return original(params)

    monkeypatch.setattr(location_views, "build_location_queryset", counted)

    first = api_client.get(
        reverse("location-list"),
        {"category": "Cafe", "ordering": "rating", "page_size": "10"},
    )
    second = api_client.get(
        reverse("location-list"),
        {"page_size": "10", "ordering": "rating", "category": "Cafe"},
    )

    assert first.status_code == second.status_code == 200
    assert len(calls) == 1


@pytest.mark.django_db
def test_cache_outage_falls_back_to_database(api_client, location, monkeypatch):
    def fail_get(key, default=None):
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr(location_cache.cache, "get", fail_get)

    response = api_client.get(reverse("location-list"))

    assert response.status_code == 200
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_rollback_does_not_invalidate_cache(location, category):
    generation_before = location_cache._generation()

    with pytest.raises(RuntimeError), transaction.atomic():
        create_location(
            data={
                "name": "Rolled Back",
                "description": "Should not exist.",
                "address": "1 Nowhere",
                "latitude": Decimal("50.000000"),
                "longitude": Decimal("30.000000"),
                "category_ids": [category.pk],
            },
            user=location.created_by,
        )
        raise RuntimeError("rollback")

    assert location_cache._generation() == generation_before
    assert not Location.objects.filter(name="Rolled Back").exists()
