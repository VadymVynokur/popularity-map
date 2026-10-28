import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.models import EmailDelivery
from apps.subscriptions.models import LocationSubscription

logger = logging.getLogger(__name__)


def create_review_deliveries(review) -> list[int]:
    recipient_ids = {review.location.created_by_id}
    recipient_ids.update(
        LocationSubscription.objects.filter(
            location=review.location,
            is_active=True,
        ).values_list("user_id", flat=True)
    )
    recipients = User.objects.filter(pk__in=recipient_ids, is_active=True)
    delivery_ids: list[int] = []
    for recipient in recipients:
        delivery, created = EmailDelivery.objects.get_or_create(
            review=review,
            recipient=recipient,
            defaults={
                "recipient_email_snapshot": recipient.email,
                "status": EmailDelivery.Status.PENDING,
            },
        )
        if created:
            delivery_ids.append(delivery.pk)
    return delivery_ids


def enqueue_deliveries(delivery_ids: list[int]) -> None:
    from apps.notifications.tasks import send_email_delivery_task

    for delivery_id in delivery_ids:
        try:
            send_email_delivery_task.delay(delivery_id)
        except Exception:
            logger.exception("Failed to enqueue email delivery %s", delivery_id)


def _email_body(delivery: EmailDelivery) -> tuple[str, str]:
    review = delivery.review
    location = review.location
    subject = f"New review for {location.name}"
    body = (
        f"A new review was published for {location.name}.\n\n"
        f"Rating: {review.rating}/5\n"
        f"Comment: {review.comment or '(no comment)'}\n"
    )
    return subject, body


def send_delivery(delivery_id: int) -> None:
    failure: Exception | None = None
    with transaction.atomic():
        delivery = (
            EmailDelivery.objects.select_for_update()
            .select_related("review", "review__location")
            .filter(pk=delivery_id)
            .first()
        )
        if delivery is None or delivery.status != EmailDelivery.Status.PENDING:
            return
        if delivery.review.location.deleted_at is not None:
            return
        if delivery.attempts >= 5:
            delivery.status = EmailDelivery.Status.FAILED
            delivery.last_error = "Maximum delivery attempts exceeded."
            delivery.save(update_fields=["status", "last_error", "updated_at"])
            return

        subject, body = _email_body(delivery)
        delivery.attempts += 1
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[delivery.recipient_email_snapshot],
            )
        except Exception as exc:
            failure = exc
            delivery.last_error = type(exc).__name__
            if delivery.attempts >= 5:
                delivery.status = EmailDelivery.Status.FAILED
            delivery.save(update_fields=["attempts", "status", "last_error", "updated_at"])
            logger.warning(
                "Email delivery %s failed on attempt %s (%s)",
                delivery.pk,
                delivery.attempts,
                type(exc).__name__,
            )
        else:
            delivery.status = EmailDelivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.last_error = ""
            delivery.save(
                update_fields=["attempts", "status", "sent_at", "last_error", "updated_at"]
            )
    if failure is not None:
        raise failure


def pending_delivery_ids(*, limit: int = 1000) -> list[int]:
    return list(
        EmailDelivery.objects.filter(status=EmailDelivery.Status.PENDING)
        .order_by("created_at")
        .values_list("id", flat=True)[:limit]
    )
