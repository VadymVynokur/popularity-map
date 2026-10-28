import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import User
from apps.accounts.tasks import send_confirmation_email_task
from apps.accounts.tokens import (
    decode_uid,
    make_email_confirmation_token,
    read_email_confirmation_token,
)
from apps.common.exceptions import (
    EmailAlreadyRegistered,
    InvalidToken,
    UsernameAlreadyRegistered,
)

logger = logging.getLogger(__name__)


def _normalized_email(email: str) -> str:
    return email.strip().lower()


def register_user(*, username: str, email: str, password: str) -> User:
    email = _normalized_email(email)
    username = username.strip()
    if User.objects.filter(email__iexact=email).exists():
        raise EmailAlreadyRegistered()
    if User.objects.filter(username=username).exists():
        raise UsernameAlreadyRegistered()
    try:
        with transaction.atomic():
            user = User.objects.create_user(email=email, username=username, password=password)
    except IntegrityError as exc:
        if User.objects.filter(email__iexact=email).exists():
            raise EmailAlreadyRegistered() from exc
        if User.objects.filter(username=username).exists():
            raise UsernameAlreadyRegistered() from exc
        raise
    queue_confirmation_email(user.pk)
    return user


def queue_confirmation_email(user_id: int) -> None:
    def enqueue() -> None:
        try:
            send_confirmation_email_task.delay(user_id)
        except Exception:
            logger.exception("Failed to enqueue email confirmation for user %s", user_id)

    transaction.on_commit(enqueue)


def send_confirmation_email(user_id: int) -> None:
    user = User.objects.filter(pk=user_id, is_active=True, email_verified=False).first()
    if user is None:
        return
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = make_email_confirmation_token(user)
    url = f"{settings.EMAIL_CONFIRMATION_URL}?uid={uid}&token={token}"
    send_mail(
        subject="Confirm your email address",
        message=(
            "Please confirm your email address for Location Popularity Map.\n\n"
            f"{url}\n\n"
            "This link expires in 24 hours."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def confirm_email(*, uid: str, token: str) -> User:
    user_id = decode_uid(uid)
    if user_id is None:
        raise InvalidToken("The confirmation link is invalid or has expired.")
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None or user.email_verified:
        raise InvalidToken("The confirmation link is invalid or has expired.")
    payload = read_email_confirmation_token(token, user_id=user.pk)
    if (
        payload is None
        or payload.get("email") != user.email
        or payload.get("verified") is not False
    ):
        raise InvalidToken("The confirmation link is invalid or has expired.")
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return user


def resend_confirmation_email(email: str) -> None:
    user = User.objects.filter(email__iexact=_normalized_email(email), is_active=True).first()
    if user is not None and not user.email_verified:
        queue_confirmation_email(user.pk)


def send_password_reset_email(user: User) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = f"{settings.PASSWORD_RESET_URL}?uid={uid}&token={token}"
    send_mail(
        subject="Reset your password",
        message=(
            "A password reset was requested for your Location Popularity Map account.\n\n"
            f"{url}\n\n"
            "If you did not request it, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def request_password_reset(email: str) -> None:
    user = User.objects.filter(
        email__iexact=_normalized_email(email),
        is_active=True,
    ).first()
    if user is not None and user.has_usable_password():
        try:
            send_password_reset_email(user)
        except Exception:
            logger.exception("Failed to send password reset email for user %s", user.pk)


def confirm_password_reset(*, uid: str, token: str, new_password: str) -> User:
    user_id = decode_uid(uid)
    user = User.objects.filter(pk=user_id, is_active=True).first() if user_id else None
    if user is None or not default_token_generator.check_token(user, token):
        raise InvalidToken("The password reset link is invalid or has expired.")
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise InvalidToken("The new password does not meet password requirements.") from exc
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user
