from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.exceptions import LocationNotActive, ResourceNotFound, ReviewAlreadyExists
from apps.locations.cache import invalidate_location_lists
from apps.locations.models import Location
from apps.notifications.services import create_review_deliveries, enqueue_deliveries
from apps.reviews.models import Review, ReviewReaction


def _ensure_active(location: Location) -> None:
    if location.deleted_at is not None:
        raise LocationNotActive()


def create_review(*, location: Location, author, rating: int, comment: str = "") -> Review:
    _ensure_active(location)
    if Review.objects.filter(
        location=location,
        author=author,
        deleted_at__isnull=True,
    ).exists():
        raise ReviewAlreadyExists()
    try:
        with transaction.atomic():
            review = Review.objects.create(
                location=location,
                author=author,
                rating=rating,
                comment=comment,
            )
            delivery_ids = create_review_deliveries(review)
    except IntegrityError as exc:
        raise ReviewAlreadyExists() from exc
    transaction.on_commit(invalidate_location_lists)
    transaction.on_commit(lambda: enqueue_deliveries(delivery_ids))
    return review


def replace_review(review: Review, *, rating: int, comment: str) -> Review:
    _ensure_active(review.location)
    try:
        with transaction.atomic():
            try:
                locked = Review.objects.select_for_update().get(pk=review.pk)
            except Review.DoesNotExist as exc:
                raise ResourceNotFound() from exc
            if locked.deleted_at is not None:
                raise ResourceNotFound()
            now = timezone.now()
            locked.deleted_at = now
            locked.save(update_fields=["deleted_at", "updated_at"])
            replacement = Review.objects.create(
                location=locked.location,
                author=locked.author,
                rating=rating,
                comment=comment,
            )
    except IntegrityError as exc:
        raise ReviewAlreadyExists() from exc
    transaction.on_commit(invalidate_location_lists)
    return replacement


def soft_delete_review(review: Review) -> Review:
    if review.deleted_at is None:
        with transaction.atomic():
            review.deleted_at = timezone.now()
            review.save(update_fields=["deleted_at", "updated_at"])
        transaction.on_commit(invalidate_location_lists)
    return review


def set_reaction(*, review: Review, user, reaction_type: str) -> ReviewReaction:
    with transaction.atomic():
        reaction, _ = ReviewReaction.objects.update_or_create(
            review=review,
            user=user,
            defaults={"type": reaction_type},
        )
    return reaction


def delete_reaction(*, review: Review, user) -> None:
    ReviewReaction.objects.filter(review=review, user=user).delete()
