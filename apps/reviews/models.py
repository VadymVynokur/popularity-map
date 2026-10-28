from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class ReviewQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class Review(models.Model):
    location = models.ForeignKey(
        "locations.Location",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ReviewQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name="review_rating_range",
            ),
            models.UniqueConstraint(
                fields=["location", "author"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_review_per_user_location",
            ),
        ]
        indexes = [
            models.Index(fields=["location", "deleted_at"]),
            models.Index(fields=["author", "deleted_at"]),
        ]

    def __str__(self) -> str:
        return f"Review {self.pk} for location {self.location_id}"


class ReviewReaction(models.Model):
    class Type(models.TextChoices):
        LIKE = "like", "Like"
        DISLIKE = "dislike", "Dislike"

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_reactions",
    )
    type = models.CharField(max_length=7, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["review", "user"],
                name="unique_reaction_per_user_review",
            )
        ]
        indexes = [
            models.Index(fields=["review", "type"]),
        ]
