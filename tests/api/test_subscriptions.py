import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.locations.services import soft_delete_location
from apps.subscriptions.models import LocationSubscription


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
def test_subscription_endpoints_require_authentication(api_client, location):
    url = reverse("location-subscription", args=[location.pk])

    assert api_client.get(url).status_code == 401
    assert api_client.put(url).status_code == 401
    assert api_client.delete(url).status_code == 401


@pytest.mark.django_db
def test_subscribe_is_idempotent_and_allows_own_location(auth_client, location, verified_user):
    url = reverse("location-subscription", args=[location.pk])

    first = auth_client.put(url)
    second = auth_client.put(url)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data["is_active"] is True
    assert second.data["is_active"] is True
    assert first.data["unsubscribed_at"] is None
    assert LocationSubscription.objects.filter(location=location, user=verified_user).count() == 1

    state = auth_client.get(url)
    assert state.status_code == 200
    assert state.data["is_active"] is True
    assert state.data["location"] == location.pk
    assert "email" not in state.data


@pytest.mark.django_db
def test_unsubscribe_preserves_row_and_is_idempotent(auth_client, location, verified_user):
    url = reverse("location-subscription", args=[location.pk])
    auth_client.put(url)

    first = auth_client.delete(url)
    second = auth_client.delete(url)

    assert first.status_code == 204
    assert second.status_code == 204
    subscription = LocationSubscription.objects.get(location=location, user=verified_user)
    assert subscription.is_active is False
    assert subscription.unsubscribed_at is not None

    state = auth_client.get(url)
    assert state.data["is_active"] is False
    assert state.data["unsubscribed_at"] is not None


@pytest.mark.django_db
def test_resubscribe_reactivates_existing_row(auth_client, location, verified_user):
    url = reverse("location-subscription", args=[location.pk])
    auth_client.put(url)
    auth_client.delete(url)
    original = LocationSubscription.objects.get(location=location, user=verified_user)

    response = auth_client.put(url)

    assert response.status_code == 200
    subscription = LocationSubscription.objects.get(location=location, user=verified_user)
    assert subscription.pk == original.pk
    assert subscription.is_active is True
    assert subscription.unsubscribed_at is None


@pytest.mark.django_db
def test_subscription_state_is_private_to_current_user(auth_client, location):
    url = reverse("location-subscription", args=[location.pk])
    auth_client.put(url)

    other = _other_client()
    state = other.get(url)
    assert state.status_code == 200
    assert state.data["is_active"] is False
    assert state.data["created_at"] is None
    assert state.data["unsubscribed_at"] is None


@pytest.mark.django_db
def test_cannot_subscribe_to_deleted_location_but_can_manage_existing(
    auth_client,
    location,
    verified_user,
):
    url = reverse("location-subscription", args=[location.pk])
    auth_client.put(url)
    soft_delete_location(location)

    assert auth_client.put(url).status_code == 404
    state = auth_client.get(url)
    assert state.status_code == 200
    assert state.data["is_active"] is True
    assert auth_client.delete(url).status_code == 204
    assert (
        LocationSubscription.objects.get(location=location, user=verified_user).is_active is False
    )


@pytest.mark.django_db
def test_cannot_subscribe_to_unknown_location(auth_client):
    response = auth_client.put(reverse("location-subscription", args=[99999]))

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"
