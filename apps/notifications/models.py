from django.conf import settings
from django.db import models


class EmailDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    review = models.ForeignKey(
        "reviews.Review",
        on_delete=models.CASCADE,
        related_name="email_deliveries",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="email_deliveries",
    )
    recipient_email_snapshot = models.EmailField(max_length=254)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["review", "recipient"],
                name="unique_email_delivery_per_review_recipient",
            )
        ]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Delivery {self.pk} ({self.status})"
