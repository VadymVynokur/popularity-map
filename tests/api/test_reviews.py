import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.common.exceptions import ResourceNotFound
from apps.locations.services import soft_delete_location
from apps.reviews.models import Review, ReviewReaction
from apps.reviews.services import replace_review, soft_delete_review


def _review_payload(**overrides):
    data = {"rating": 5, "comment": "Great place."}
    data.update(overrides)
    return data


def _other_user() -> User:
    return User.objects.create_user(
        email="other@example.com",
        username="other_user",
        password="a-strong-password",
    )


@pytest.mark.django_db
def test_review_list_is_public_and_paginated(api_client, location, verified_user):
    other = _other_user()
    Review.objects.create(location=location, author=verified_user, rating=5, comment="Great")
    Review.objects.create(location=location, author=other, rating=3, comment="Okay")
    Review.objects.create(
        location=location,
        author=User.objects.create_user(
            email="third@example.com",
            username="third_user",
            password="a-strong-password",
        ),
        rating=1,
        comment="Deleted",
        deleted_at=timezone.now(),
    )

    response = api_client.get(
        reverse("location-review-list", args=[location.pk]),
        {"page_size": 1},
    )

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["author"]["username"] in {
        verified_user.username,
        other.username,
    }
    assert response.data["results"][0]["likes_count"] == 0
    assert response.data["results"][0]["dislikes_count"] == 0


@pytest.mark.django_db
def test_review_list_for_deleted_location_returns_404(api_client, location):
    soft_delete_location(location)

    response = api_client.get(reverse("location-review-list", args=[location.pk]))

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_anonymous_cannot_create_review(api_client, location):
    response = api_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(),
        format="json",
    )

    assert response.status_code == 401
    assert response.data["error"]["code"] == "authentication_required"
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_authenticated_user_can_review_own_location(auth_client, location, verified_user):
    response = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(comment=""),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["rating"] == 5
    assert response.data["comment"] == ""
    assert response.data["author"] == {
        "id": verified_user.pk,
        "username": verified_user.username,
    }
    assert response.data["location"] == location.pk
    assert response.data["likes_count"] == 0
    assert response.data["dislikes_count"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize("rating", [0, 6, -1])
def test_review_rating_must_be_between_one_and_five(auth_client, location, rating):
    response = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(rating=rating),
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert "rating" in response.data["error"]["details"]


@pytest.mark.django_db
def test_review_comment_max_length_is_enforced(auth_client, location):
    response = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(comment="x" * 2001),
        format="json",
    )

    assert response.status_code == 400
    assert "comment" in response.data["error"]["details"]


@pytest.mark.django_db
def test_duplicate_active_review_returns_conflict(auth_client, location):
    first = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(),
        format="json",
    )
    second = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(rating=4),
        format="json",
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.data["error"]["code"] == "review_already_exists"
    assert Review.objects.active().count() == 1


@pytest.mark.django_db
def test_review_can_be_created_again_after_soft_delete(auth_client, location, verified_user):
    first = Review.objects.create(
        location=location,
        author=verified_user,
        rating=2,
        comment="Old",
    )
    soft_delete_review(first)

    response = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(rating=5),
        format="json",
    )

    assert response.status_code == 201
    assert Review.objects.active().count() == 1


@pytest.mark.django_db
def test_cannot_review_deleted_location(auth_client, location):
    soft_delete_location(location)

    response = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(),
        format="json",
    )

    assert response.status_code == 404
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_review_detail_only_returns_active_review(api_client, location, verified_user):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=4,
        comment="Good",
    )

    response = api_client.get(reverse("review-detail", args=[review.pk]))
    assert response.status_code == 200
    assert response.data["id"] == review.pk
    assert response.data["likes_count"] == 0
    assert response.data["dislikes_count"] == 0

    soft_delete_review(review)
    response = api_client.get(reverse("review-detail", args=[review.pk]))
    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_owner_replaces_review_and_old_record_becomes_historical(
    api_client,
    auth_client,
    location,
    verified_user,
):
    created = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(rating=5, comment="Original"),
        format="json",
    )
    old_id = created.data["id"]

    updated = auth_client.patch(
        reverse("review-detail", args=[old_id]),
        {"rating": 3, "comment": "Edited"},
        format="json",
    )

    assert updated.status_code == 200
    assert updated.data["id"] != old_id
    assert updated.data["rating"] == 3
    assert updated.data["comment"] == "Edited"

    old = Review.objects.get(pk=old_id)
    assert old.deleted_at is not None
    assert Review.objects.active().count() == 1

    assert api_client.get(reverse("review-detail", args=[old_id])).status_code == 404
    assert api_client.get(reverse("review-detail", args=[updated.data["id"]])).status_code == 200


@pytest.mark.django_db
def test_partial_review_update_preserves_omitted_comment(auth_client, location):
    created = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(rating=5, comment="Original"),
        format="json",
    )

    response = auth_client.patch(
        reverse("review-detail", args=[created.data["id"]]),
        {"rating": 2},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["rating"] == 2
    assert response.data["comment"] == "Original"


@pytest.mark.django_db
def test_replacing_a_soft_deleted_review_raises_not_found(location, verified_user):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Original",
    )
    soft_delete_review(review)

    with pytest.raises(ResourceNotFound):
        replace_review(review, rating=4, comment="Edited")


@pytest.mark.django_db
def test_replacing_a_missing_review_raises_not_found(location, verified_user):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Original",
    )
    Review.objects.filter(pk=review.pk).delete()

    with pytest.raises(ResourceNotFound):
        replace_review(review, rating=4, comment="Edited")


@pytest.mark.django_db
def test_owner_can_replace_with_put(auth_client, location):
    created = auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(rating=2, comment="Original"),
        format="json",
    )

    response = auth_client.put(
        reverse("review-detail", args=[created.data["id"]]),
        {"rating": 4, "comment": "Replaced"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["rating"] == 4
    assert response.data["comment"] == "Replaced"


@pytest.mark.django_db
def test_only_author_can_edit_or_delete_review(auth_client, admin_client, location, verified_user):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Mine",
    )
    other_client = APIClient()
    other_client.force_authenticate(_other_user())

    assert (
        other_client.patch(
            reverse("review-detail", args=[review.pk]),
            {"rating": 1},
            format="json",
        ).status_code
        == 403
    )
    assert other_client.delete(reverse("review-detail", args=[review.pk])).status_code == 403
    assert (
        admin_client.patch(
            reverse("review-detail", args=[review.pk]),
            {"rating": 1},
            format="json",
        ).status_code
        == 403
    )
    assert admin_client.delete(reverse("review-detail", args=[review.pk])).status_code == 403

    review.refresh_from_db()
    assert review.deleted_at is None


@pytest.mark.django_db
def test_owner_can_soft_delete_review_and_aggregates_update(
    api_client,
    auth_client,
    location,
    verified_user,
):
    first = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Five",
    )
    other = _other_user()
    Review.objects.create(location=location, author=other, rating=3, comment="Three")

    detail = api_client.get(reverse("location-detail", args=[location.pk]))
    assert detail.data["rating"] == 4.0
    assert detail.data["review_count"] == 2

    response = auth_client.delete(reverse("review-detail", args=[first.pk]))
    assert response.status_code == 204

    first.refresh_from_db()
    assert first.deleted_at is not None
    detail = api_client.get(reverse("location-detail", args=[location.pk]))
    assert detail.data["rating"] == 3.0
    assert detail.data["review_count"] == 1

    repeated = auth_client.delete(reverse("review-detail", args=[first.pk]))
    assert repeated.status_code == 404


@pytest.mark.django_db
def test_reaction_state_create_switch_and_delete(
    api_client,
    auth_client,
    location,
    verified_user,
):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Great",
    )
    url = reverse("review-reaction", args=[review.pk])

    assert api_client.get(url).status_code == 401
    assert api_client.put(url, {"type": "like"}, format="json").status_code == 401

    state = auth_client.get(url)
    assert state.status_code == 200
    assert state.data == {"type": None}

    liked = auth_client.put(url, {"type": "like"}, format="json")
    assert liked.status_code == 200
    assert liked.data == {"type": "like"}
    assert auth_client.get(url).data == {"type": "like"}

    detail = api_client.get(reverse("review-detail", args=[review.pk]))
    assert detail.data["likes_count"] == 1
    assert detail.data["dislikes_count"] == 0

    disliked = auth_client.put(url, {"type": "dislike"}, format="json")
    assert disliked.data == {"type": "dislike"}
    detail = api_client.get(reverse("review-detail", args=[review.pk]))
    assert detail.data["likes_count"] == 0
    assert detail.data["dislikes_count"] == 1
    assert ReviewReaction.objects.filter(review=review, user=verified_user).count() == 1

    assert auth_client.put(url, {"type": "dislike"}, format="json").status_code == 200
    assert auth_client.delete(url).status_code == 204
    assert auth_client.get(url).data == {"type": None}
    assert auth_client.delete(url).status_code == 204


@pytest.mark.django_db
def test_reaction_on_own_review_is_allowed(auth_client, location, verified_user):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Great",
    )

    response = auth_client.put(
        reverse("review-reaction", args=[review.pk]),
        {"type": "like"},
        format="json",
    )

    assert response.status_code == 200
    assert ReviewReaction.objects.filter(review=review, user=verified_user).exists()


@pytest.mark.django_db
def test_reaction_requires_valid_type(auth_client, location, verified_user):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Great",
    )

    response = auth_client.put(
        reverse("review-reaction", args=[review.pk]),
        {"type": "love"},
        format="json",
    )

    assert response.status_code == 400
    assert "type" in response.data["error"]["details"]


@pytest.mark.django_db
def test_reaction_endpoint_hides_deleted_review(auth_client, location, verified_user):
    review = Review.objects.create(
        location=location,
        author=verified_user,
        rating=5,
        comment="Great",
    )
    soft_delete_review(review)

    url = reverse("review-reaction", args=[review.pk])
    assert auth_client.get(url).status_code == 404
    assert auth_client.put(url, {"type": "like"}, format="json").status_code == 404
    assert auth_client.delete(url).status_code == 404


@pytest.mark.django_db
def test_reaction_counts_are_kept_on_historical_review(
    api_client,
    auth_client,
    location,
    verified_user,
):
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

    replacement = auth_client.patch(
        reverse("review-detail", args=[review.pk]),
        {"rating": 4},
        format="json",
    )

    assert replacement.status_code == 200
    assert (
        api_client.get(reverse("review-detail", args=[replacement.data["id"]])).data["likes_count"]
        == 0
    )
    assert ReviewReaction.objects.filter(review=review, user=verified_user).count() == 1
