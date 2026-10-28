import random

from celery import shared_task

from apps.notifications.models import EmailDelivery
from apps.notifications.services import pending_delivery_ids, send_delivery


@shared_task(bind=True, max_retries=4)
def send_email_delivery_task(self, delivery_id: int) -> None:
    try:
        send_delivery(delivery_id)
    except Exception as exc:
        delivery = EmailDelivery.objects.filter(pk=delivery_id).first()
        if delivery is None or delivery.status == EmailDelivery.Status.FAILED:
            return
        countdown = min(300.0, 5.0 * (2**delivery.attempts)) + random.uniform(0.0, 1.0)
        raise self.retry(exc=exc, countdown=countdown) from exc


@shared_task
def sweep_pending_email_deliveries() -> int:
    delivery_ids = pending_delivery_ids()
    for delivery_id in delivery_ids:
        send_email_delivery_task.delay(delivery_id)
    return len(delivery_ids)
