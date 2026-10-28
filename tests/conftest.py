import contextlib
from decimal import Decimal

import pytest
import redis
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.categories.models import Category
from apps.locations.models import Location


@pytest.fixture(autouse=True)
def clear_caches():
    cache.clear()
    with contextlib.suppress(Exception):
        redis.Redis.from_url(settings.REDIS_VIEW_COOLDOWN_URL).flushdb()
    yield
    cache.clear()
    with contextlib.suppress(Exception):
        redis.Redis.from_url(settings.REDIS_VIEW_COOLDOWN_URL).flushdb()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        email="user@example.com",
        username="forest_walker",
        password="a-strong-password",
    )


@pytest.fixture
def verified_user(db) -> User:
    user = User.objects.create_user(
        email="verified@example.com",
        username="verified_walker",
        password="a-strong-password",
    )
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return user


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_superuser(
        email="admin@example.com",
        username="admin_user",
        password="a-strong-password",
    )


@pytest.fixture
def auth_client(verified_user) -> APIClient:
    client = APIClient()
    client.force_authenticate(verified_user)
    return client


@pytest.fixture
def admin_client(admin_user) -> APIClient:
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.fixture
def category(db) -> Category:
    return Category.objects.get(name="Cafe")


@pytest.fixture
def location(db, verified_user, category) -> Location:
    location = Location.objects.create(
        name="Riverside Cafe",
        description="A small cafe next to the river.",
        address="12 River Street",
        latitude=Decimal("50.450100"),
        longitude=Decimal("30.523400"),
        created_by=verified_user,
    )
    location.categories.set([category])
    return location
