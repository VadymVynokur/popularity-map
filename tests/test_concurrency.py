from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connections

from apps.accounts.services import register_user
from apps.categories.models import Category
from apps.common.exceptions import EmailAlreadyRegistered, ReviewAlreadyExists
from apps.locations.models import Location, LocationView
from apps.locations.view_tracking import track_location_view
from apps.reviews.models import Review, ReviewReaction
from apps.reviews.services import create_review, set_reaction

SEED_CATEGORIES = [
    "Cafe",
    "Coffee shop",
    "Bar",
    "Restaurant",
    "Park",
    "Museum",
    "Gallery",
    "Historical place",
    "Nature",
    "Entertainment",
    "Shopping",
    "Other",
]


@pytest.fixture(autouse=True)
def seed_categories(db):
    for name in SEED_CATEGORIES:
        Category.objects.get_or_create(name=name)


def _run_concurrently(first, second):
    barrier = Barrier(2)

    def wrapped(function):
        def run():
            connections.close_all()
            try:
                barrier.wait()
                return function()
            except Exception as exc:
                return exc
            finally:
                connections.close_all()

        return run

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(wrapped(first)), executor.submit(wrapped(second))]
        return [future.result() for future in futures]


@pytest.mark.django_db(transaction=True)
def test_concurrent_view_tracking_creates_one_event(location, monkeypatch):
    monkeypatch.setattr("apps.locations.view_tracking._claim_redis", lambda key: None)
    monkeypatch.setattr("apps.locations.view_tracking._set_redis", lambda key, ttl: None)
    monkeypatch.setattr("apps.locations.view_tracking._delete_redis", lambda key: None)
    location_id = location.pk

    def track():
        return track_location_view(Location.objects.get(pk=location_id), "user:concurrent")

    results = _run_concurrently(track, track)

    assert sorted(results) == [False, True]
    assert LocationView.objects.filter(location_id=location_id).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_review_is_rejected(location, verified_user, monkeypatch):
    monkeypatch.setattr(
        "apps.reviews.services.create_review_deliveries",
        lambda review: [],
    )
    monkeypatch.setattr("apps.reviews.services.enqueue_deliveries", lambda delivery_ids: None)
    location_id = location.pk
    user_id = verified_user.pk

    def create():
        from apps.accounts.models import User

        return create_review(
            location=Location.objects.get(pk=location_id),
            author=User.objects.get(pk=user_id),
            rating=5,
            comment="Concurrent",
        )

    results = _run_concurrently(create, create)

    assert sum(isinstance(result, ReviewAlreadyExists) for result in results) == 1
    assert Review.objects.filter(location_id=location_id, author_id=user_id).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_reaction_upsert_keeps_one_row(location, verified_user):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Concurrent",
    )
    review_id = review.pk
    user_id = verified_user.pk

    def react(reaction_type):
        from apps.accounts.models import User

        return set_reaction(
            review=Review.objects.get(pk=review_id),
            user=User.objects.get(pk=user_id),
            reaction_type=reaction_type,
        )

    _run_concurrently(lambda: react("like"), lambda: react("dislike"))

    assert ReviewReaction.objects.filter(review_id=review_id, user_id=user_id).count() == 1
    assert ReviewReaction.objects.get(review_id=review_id, user_id=user_id).type in {
        "like",
        "dislike",
    }


@pytest.mark.django_db(transaction=True)
def test_concurrent_registration_creates_one_user(monkeypatch):
    monkeypatch.setattr("apps.accounts.services.queue_confirmation_email", lambda user_id: None)

    def register(username):
        return register_user(
            username=username,
            email="race@example.com",
            password="a-strong-password",
        )

    results = _run_concurrently(lambda: register("first_user"), lambda: register("second_user"))

    assert sum(isinstance(result, EmailAlreadyRegistered) for result in results) == 1
    from apps.accounts.models import User

    assert User.objects.filter(email="race@example.com").count() == 1
