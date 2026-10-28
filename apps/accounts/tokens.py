from django.conf import settings
from django.core import signing
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

EMAIL_CONFIRMATION_SALT = "popularity-map.accounts.email-confirmation"


def encode_uid(user_id: int) -> str:
    return urlsafe_base64_encode(force_bytes(user_id))


def decode_uid(uid: str) -> int | None:
    try:
        return int(urlsafe_base64_decode(uid).decode())
    except (TypeError, ValueError, UnicodeDecodeError):
        return None


def make_email_confirmation_token(user) -> str:
    return signing.dumps(
        {"uid": user.pk, "email": user.email, "verified": user.email_verified},
        salt=EMAIL_CONFIRMATION_SALT,
        compress=True,
    )


def read_email_confirmation_token(token: str, *, user_id: int) -> dict | None:
    try:
        payload = signing.loads(
            token,
            salt=EMAIL_CONFIRMATION_SALT,
            max_age=settings.EMAIL_CONFIRMATION_TIMEOUT_SECONDS,
        )
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict) or payload.get("uid") != user_id:
        return None
    return payload
