import re
from urllib.parse import parse_qs, urlparse

import pytest
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User


def _csrf_client() -> APIClient:
    client = APIClient(enforce_csrf_checks=True)
    response = client.get(reverse("auth-csrf"))
    assert response.status_code == 200
    return client


def _csrf_headers(client: APIClient) -> dict[str, str]:
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _confirmation_params(message_body: str) -> dict[str, str]:
    match = re.search(r"https?://\S+", message_body)
    assert match
    return {key: values[0] for key, values in parse_qs(urlparse(match.group(0)).query).items()}


@pytest.mark.django_db
def test_register_creates_unverified_user_without_password(api_client):
    response = api_client.post(
        reverse("auth-register"),
        {
            "username": "new_walker",
            "email": "NEW@Example.com",
            "password": "a-strong-password",
            "role": "admin",
            "is_staff": True,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["email"] == "new@example.com"
    assert response.data["role"] == "user"
    assert response.data["email_verified"] is False
    assert "password" not in response.data
    user = User.objects.get(email="new@example.com")
    assert user.role == User.Role.USER
    assert user.is_staff is False


@pytest.mark.django_db
def test_register_rejects_duplicate_email_case_insensitively(api_client, user):
    response = api_client.post(
        reverse("auth-register"),
        {
            "username": "another_walker",
            "email": "USER@example.com",
            "password": "a-strong-password",
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "email_already_registered"


@pytest.mark.django_db
def test_register_rejects_duplicate_username(api_client, user):
    response = api_client.post(
        reverse("auth-register"),
        {
            "username": "forest_walker",
            "email": "another@example.com",
            "password": "a-strong-password",
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "username_already_registered"


@pytest.mark.django_db
def test_confirmation_email_confirms_account_once(api_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse("auth-register"),
            {
                "username": "confirm_me",
                "email": "confirm@example.com",
                "password": "a-strong-password",
            },
            format="json",
        )
    assert response.status_code == 201
    assert len(mail.outbox) == 1
    params = _confirmation_params(mail.outbox[0].body)

    confirm = api_client.post(reverse("auth-email-confirm"), params, format="json")
    assert confirm.status_code == 200
    assert User.objects.get(email="confirm@example.com").email_verified is True

    repeated = api_client.post(reverse("auth-email-confirm"), params, format="json")
    assert repeated.status_code == 400
    assert repeated.data["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_unverified_user_cannot_login(api_client, user):
    client = _csrf_client()
    response = client.post(
        reverse("auth-login"),
        {"email": user.email, "password": "a-strong-password"},
        format="json",
        **_csrf_headers(client),
    )
    assert response.status_code == 401
    assert response.data["error"]["code"] == "invalid_credentials"


@pytest.mark.django_db
def test_login_creates_session_and_logout_invalidates_it(verified_user):
    client = _csrf_client()
    response = client.post(
        reverse("auth-login"),
        {"email": verified_user.email, "password": "a-strong-password"},
        format="json",
        **_csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.data["email"] == verified_user.email

    me = client.get(reverse("auth-me"))
    assert me.status_code == 200
    assert me.data["username"] == verified_user.username

    logout = client.post(reverse("auth-logout"), **_csrf_headers(client))
    assert logout.status_code == 204
    assert client.get(reverse("auth-me")).status_code == 401


@pytest.mark.django_db
def test_login_requires_csrf(verified_user):
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        reverse("auth-login"),
        {"email": verified_user.email, "password": "a-strong-password"},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"


@pytest.mark.django_db
def test_invalid_login_does_not_reveal_account_state(api_client, user):
    response = api_client.post(
        reverse("auth-login"),
        {"email": "missing@example.com", "password": "wrong-password"},
        format="json",
    )
    assert response.status_code == 401
    assert response.data["error"]["code"] == "invalid_credentials"

    response = api_client.post(
        reverse("auth-login"),
        {"email": user.email, "password": "wrong-password"},
        format="json",
    )
    assert response.status_code == 401
    assert response.data["error"]["code"] == "invalid_credentials"


@pytest.mark.django_db
def test_password_reset_is_enumeration_safe_and_changes_password(api_client, verified_user):
    known = api_client.post(
        reverse("auth-password-reset"),
        {"email": verified_user.email},
        format="json",
    )
    unknown = api_client.post(
        reverse("auth-password-reset"),
        {"email": "missing@example.com"},
        format="json",
    )
    assert known.status_code == unknown.status_code == 200
    assert known.data == unknown.data
    assert len(mail.outbox) == 1
    params = _confirmation_params(mail.outbox[0].body)

    confirm = api_client.post(
        reverse("auth-password-reset-confirm"),
        {**params, "new_password": "a-new-strong-password"},
        format="json",
    )
    assert confirm.status_code == 200

    assert (
        api_client.post(
            reverse("auth-login"),
            {"email": verified_user.email, "password": "a-strong-password"},
            format="json",
        ).status_code
        == 401
    )
    login = api_client.post(
        reverse("auth-login"),
        {"email": verified_user.email, "password": "a-new-strong-password"},
        format="json",
    )
    assert login.status_code == 200


@pytest.mark.django_db
def test_password_reset_rejects_weak_password(api_client, verified_user):
    api_client.post(
        reverse("auth-password-reset"),
        {"email": verified_user.email},
        format="json",
    )
    params = _confirmation_params(mail.outbox[0].body)
    response = api_client.post(
        reverse("auth-password-reset-confirm"),
        {**params, "new_password": "short"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_login_is_rate_limited(verified_user):
    client = _csrf_client()
    headers = _csrf_headers(client)
    for _ in range(10):
        response = client.post(
            reverse("auth-login"),
            {"email": verified_user.email, "password": "wrong-password"},
            format="json",
            **headers,
        )
        assert response.status_code == 401
    limited = client.post(
        reverse("auth-login"),
        {"email": verified_user.email, "password": "wrong-password"},
        format="json",
        **headers,
    )
    assert limited.status_code == 429
    assert limited.data["error"]["code"] == "rate_limited"


@pytest.mark.django_db
def test_create_superuser_has_admin_role_and_flags():
    user = User.objects.create_superuser(
        email="root@example.com",
        username="root",
        password="a-strong-password",
    )
    assert user.role == User.Role.ADMIN
    assert user.is_staff is True
    assert user.is_superuser is True
