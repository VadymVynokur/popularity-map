import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.locations.services import restore_location, soft_delete_location
from apps.notifications.models import EmailDelivery
from apps.notifications.services import send_delivery
from apps.notifications.tasks import sweep_pending_email_deliveries
from apps.reviews.models import Review
from apps.subscriptions.models import LocationSubscription


def _review_payload(**overrides):
    data = {"rating": 5, "comment": "Great place."}
    data.update(overrides)
    return data


def _subscriber(location, *, active=True, email="subscriber@example.com") -> User:
    user = User.objects.create_user(
        email=email,
        username=email.split("@")[0],
        password="a-strong-password",
    )
    LocationSubscription.objects.create(location=location, user=user, is_active=active)
    return user


def _create_review(auth_client, location, **overrides):
    return auth_client.post(
        reverse("location-review-list", args=[location.pk]),
        _review_payload(**overrides),
        format="json",
    )


@pytest.mark.django_db
def test_review_creates_delivery_for_owner_and_active_subscribers(
    auth_client,
    location,
    verified_user,
):
    subscriber = _subscriber(location)
    inactive = _subscriber(location, active=False, email="inactive@example.com")

    response = _create_review(auth_client, location)

    assert response.status_code == 201
    deliveries = EmailDelivery.objects.filter(review_id=response.data["id"])
    assert set(deliveries.values_list("recipient_id", flat=True)) == {
        verified_user.pk,
        subscriber.pk,
    }
    assert inactive.pk not in set(deliveries.values_list("recipient_id", flat=True))
    assert all(delivery.status == EmailDelivery.Status.PENDING for delivery in deliveries)
    assert all(
        delivery.recipient_email_snapshot == delivery.recipient.email for delivery in deliveries
    )
    assert mail.outbox == []


@pytest.mark.django_db
def test_owner_who_is_also_subscriber_receives_one_delivery(auth_client, location, verified_user):
    LocationSubscription.objects.create(location=location, user=verified_user, is_active=True)

    response = _create_review(auth_client, location)

    assert response.status_code == 201
    assert EmailDelivery.objects.filter(review_id=response.data["id"]).count() == 1
    assert EmailDelivery.objects.get(review_id=response.data["id"]).recipient_id == verified_user.pk


@pytest.mark.django_db
def test_review_edit_does_not_create_new_delivery(auth_client, location):
    created = _create_review(auth_client, location)
    delivery_count = EmailDelivery.objects.filter(review_id=created.data["id"]).count()

    response = auth_client.patch(
        reverse("review-detail", args=[created.data["id"]]),
        {"rating": 4, "comment": "Edited"},
        format="json",
    )

    assert response.status_code == 200
    assert EmailDelivery.objects.count() == delivery_count
    assert not EmailDelivery.objects.filter(review_id=response.data["id"]).exists()


@pytest.mark.django_db
def test_deleted_location_does_not_create_delivery(auth_client, location):
    soft_delete_location(location)

    response = _create_review(auth_client, location)

    assert response.status_code == 404
    assert EmailDelivery.objects.count() == 0


@pytest.mark.django_db
def test_send_delivery_marks_sent_and_sends_one_email(auth_client, location):
    created = _create_review(auth_client, location)
    delivery = EmailDelivery.objects.get(review_id=created.data["id"])

    send_delivery(delivery.pk)

    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.SENT
    assert delivery.attempts == 1
    assert delivery.sent_at is not None
    assert delivery.last_error == ""
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [delivery.recipient_email_snapshot]
    assert location.name in mail.outbox[0].subject


@pytest.mark.django_db
def test_delivery_is_paused_while_location_is_deleted(auth_client, location):
    created = _create_review(auth_client, location)
    delivery = EmailDelivery.objects.get(review_id=created.data["id"])
    soft_delete_location(location)

    send_delivery(delivery.pk)

    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.PENDING
    assert delivery.attempts == 0
    assert mail.outbox == []

    restore_location(location)
    send_delivery(delivery.pk)

    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.SENT
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_delivery_failure_is_sanitized_and_failed_after_five_attempts(
    auth_client,
    location,
    monkeypatch,
):
    created = _create_review(auth_client, location)
    delivery = EmailDelivery.objects.get(review_id=created.data["id"])

    def fail_send(**kwargs):
        raise RuntimeError("SMTP password=secret at /private/path")

    monkeypatch.setattr("apps.notifications.services.send_mail", fail_send)

    for _ in range(5):
        with pytest.raises(RuntimeError):
            send_delivery(delivery.pk)

    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.FAILED
    assert delivery.attempts == 5
    assert delivery.last_error == "RuntimeError"
    assert "secret" not in delivery.last_error
    assert mail.outbox == []

    send_delivery(delivery.pk)
    delivery.refresh_from_db()
    assert delivery.attempts == 5


@pytest.mark.django_db
def test_sent_delivery_is_not_sent_twice(auth_client, location):
    created = _create_review(auth_client, location)
    delivery = EmailDelivery.objects.get(review_id=created.data["id"])
    send_delivery(delivery.pk)
    send_delivery(delivery.pk)

    delivery.refresh_from_db()
    assert delivery.attempts == 1
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_sweep_reenqueues_only_pending_deliveries(auth_client, location, monkeypatch):
    created = _create_review(auth_client, location)
    delivery = EmailDelivery.objects.get(review_id=created.data["id"])
    sent_recipient = User.objects.create_user(
        email="sent@example.com",
        username="sent_user",
        password="a-strong-password",
    )
    sent = EmailDelivery.objects.create(
        review_id=created.data["id"],
        recipient=sent_recipient,
        recipient_email_snapshot=sent_recipient.email,
        status=EmailDelivery.Status.SENT,
        sent_at=timezone.now(),
    )
    enqueued = []
    monkeypatch.setattr(
        "apps.notifications.tasks.send_email_delivery_task.delay",
        lambda delivery_id: enqueued.append(delivery_id),
    )

    count = sweep_pending_email_deliveries()

    assert count == 1
    assert enqueued == [delivery.pk]
    assert sent.pk not in enqueued


@pytest.mark.django_db
def test_enqueue_failure_leaves_outbox_pending(auth_client, location, monkeypatch):
    from apps.notifications.services import enqueue_deliveries

    created = _create_review(auth_client, location)
    delivery = EmailDelivery.objects.get(review_id=created.data["id"])

    def fail_enqueue(delivery_id):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        "apps.notifications.tasks.send_email_delivery_task.delay",
        fail_enqueue,
    )

    enqueue_deliveries([delivery.pk])

    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.PENDING
    assert EmailDelivery.objects.filter(status=EmailDelivery.Status.PENDING).count() == 1


@pytest.mark.django_db
def test_review_creation_is_not_blocked_by_email_backend_failure(
    auth_client,
    location,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    def fail_send(**kwargs):
        raise RuntimeError("SMTP unavailable")

    monkeypatch.setattr("apps.notifications.services.send_mail", fail_send)

    with django_capture_on_commit_callbacks(execute=True):
        response = _create_review(auth_client, location)

    assert response.status_code == 201
    assert Review.objects.active().count() == 1
    assert EmailDelivery.objects.count() == 1
    assert EmailDelivery.objects.get().status == EmailDelivery.Status.FAILED
