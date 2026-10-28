from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.categories.models import Category
from apps.common.exceptions import CategoryInUse
from apps.locations.cache import invalidate_location_lists


def create_category(*, name: str) -> Category:
    try:
        with transaction.atomic():
            category = Category.objects.create(name=name)
    except IntegrityError:
        raise ValidationError({"name": ["A category with this name already exists."]}) from None
    transaction.on_commit(invalidate_location_lists)
    return category


def update_category(category: Category, *, name: str) -> Category:
    try:
        with transaction.atomic():
            category.name = name
            category.save()
    except IntegrityError:
        raise ValidationError({"name": ["A category with this name already exists."]}) from None
    transaction.on_commit(invalidate_location_lists)
    return category


def delete_category(category: Category) -> None:
    if category.locations.exists():
        raise CategoryInUse()
    with transaction.atomic():
        category.delete()
    transaction.on_commit(invalidate_location_lists)
