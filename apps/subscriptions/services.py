from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import LocationNotActive
from apps.locations.models import Location
from apps.subscriptions.models import LocationSubscription


def activate_subscription(*, location: Location, user) -> LocationSubscription:
    if location.deleted_at is not None:
        raise LocationNotActive()
    with transaction.atomic():
        subscription, _ = LocationSubscription.objects.update_or_create(
            location=location,
            user=user,
            defaults={"is_active": True, "unsubscribed_at": None},
        )
    return subscription


def deactivate_subscription(*, location: Location, user) -> None:
    subscription = LocationSubscription.objects.filter(location=location, user=user).first()
    if subscription is None or not subscription.is_active:
        return
    with transaction.atomic():
        subscription.is_active = False
        subscription.unsubscribed_at = timezone.now()
        subscription.save(update_fields=["is_active", "unsubscribed_at", "updated_at"])


def subscription_state(*, location: Location, user) -> dict:
    subscription = LocationSubscription.objects.filter(location=location, user=user).first()
    if subscription is None:
        return {
            "location": location.pk,
            "is_active": False,
            "created_at": None,
            "updated_at": None,
            "unsubscribed_at": None,
        }
    return {
        "location": location.pk,
        "is_active": subscription.is_active,
        "created_at": subscription.created_at,
        "updated_at": subscription.updated_at,
        "unsubscribed_at": subscription.unsubscribed_at,
    }
