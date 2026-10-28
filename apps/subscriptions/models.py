from django.conf import settings
from django.db import models


class LocationSubscription(models.Model):
    location = models.ForeignKey(
        "locations.Location",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_subscriptions",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["location", "user"],
                name="unique_location_subscription_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["location", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.location_id}"
