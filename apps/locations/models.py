from django.conf import settings
from django.db import models
from django.db.models import Q


class LocationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class Location(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(max_length=5000)
    categories = models.ManyToManyField("categories.Category", related_name="locations")
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="locations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = LocationQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(latitude__gte=-90, latitude__lte=90),
                name="location_latitude_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__gte=-180, longitude__lte=180),
                name="location_longitude_range",
            ),
        ]
        indexes = [
            models.Index(fields=["deleted_at"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return self.name


class LocationView(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="views")
    identity_hash = models.CharField(max_length=64)
    viewed_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["location", "viewed_at"]),
        ]


class LocationViewThrottle(models.Model):
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="view_throttles",
    )
    identity_hash = models.CharField(max_length=64)
    last_counted_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["location", "identity_hash"],
                name="unique_location_view_throttle",
            )
        ]
