from django.db import transaction
from django.utils import timezone

from apps.locations.cache import invalidate_location_lists
from apps.locations.models import Location


def _category_ids(data: dict) -> list:
    return data.pop("category_ids", [])


def create_location(*, data: dict, user) -> Location:
    data = dict(data)
    category_ids = _category_ids(data)
    with transaction.atomic():
        location = Location.objects.create(created_by=user, **data)
        location.categories.set(category_ids)
    transaction.on_commit(invalidate_location_lists)
    return location


def update_location(location: Location, *, data: dict) -> Location:
    data = dict(data)
    category_ids = data.pop("category_ids", None)
    with transaction.atomic():
        for field, value in data.items():
            setattr(location, field, value)
        location.save()
        if category_ids is not None:
            location.categories.set(category_ids)
    transaction.on_commit(invalidate_location_lists)
    return location


def soft_delete_location(location: Location) -> Location:
    if location.deleted_at is None:
        with transaction.atomic():
            location.deleted_at = timezone.now()
            location.save(update_fields=["deleted_at", "updated_at"])
        transaction.on_commit(invalidate_location_lists)
    return location


def restore_location(location: Location) -> Location:
    with transaction.atomic():
        location.deleted_at = None
        location.save(update_fields=["deleted_at", "updated_at"])
    transaction.on_commit(invalidate_location_lists)
    return location
