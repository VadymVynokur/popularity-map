from celery import shared_task


@shared_task(bind=True, max_retries=5)
def send_confirmation_email_task(self, user_id: int) -> None:
    from apps.accounts.services import send_confirmation_email

    try:
        send_confirmation_email(user_id)
    except Exception as exc:  # pragma: no cover - retry path depends on SMTP
        raise self.retry(exc=exc, countdown=min(300, 5 * (2**self.request.retries))) from exc
