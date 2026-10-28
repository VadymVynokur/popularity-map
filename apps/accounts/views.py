from django.conf import settings
from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import (
    EmailConfirmationSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ResendConfirmationSerializer,
    UserProfileSerializer,
)
from apps.accounts.services import (
    confirm_email,
    confirm_password_reset,
    request_password_reset,
    resend_confirmation_email,
)
from apps.common.schema import CsrfResponseSerializer, DetailResponseSerializer, error_response
from apps.common.throttles import (
    EmailResendIPThrottle,
    EmailResendThrottle,
    LoginThrottle,
    PasswordResetThrottle,
)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        tags=["auth"],
        summary="Get a CSRF cookie and token",
        responses={200: CsrfResponseSerializer},
    )
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class RegisterView(APIView):
    @extend_schema(
        tags=["auth"],
        summary="Register a user",
        request=RegisterSerializer,
        responses={
            201: UserProfileSerializer,
            400: error_response("Invalid registration data."),
            409: error_response("Email or username is already registered."),
        },
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)


class EmailConfirmView(APIView):
    @extend_schema(
        tags=["auth"],
        summary="Confirm an email address",
        request=EmailConfirmationSerializer,
        responses={
            200: DetailResponseSerializer,
            400: error_response("The confirmation token is invalid or expired."),
        },
    )
    def post(self, request):
        serializer = EmailConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_email(**serializer.validated_data)
        return Response({"detail": "Email confirmed."})


class ResendConfirmationView(APIView):
    throttle_classes = [EmailResendIPThrottle, EmailResendThrottle]

    @extend_schema(
        tags=["auth"],
        summary="Resend an email confirmation link",
        request=ResendConfirmationSerializer,
        responses={
            200: DetailResponseSerializer,
            400: error_response("Invalid email address."),
            429: error_response("Email resend rate limit exceeded."),
        },
    )
    def post(self, request):
        serializer = ResendConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resend_confirmation_email(serializer.validated_data["email"])
        return Response(
            {
                "detail": (
                    "If an unconfirmed account exists for this address, "
                    "a confirmation email has been sent."
                )
            }
        )


class LoginView(APIView):
    throttle_classes = [LoginThrottle]

    @extend_schema(
        tags=["auth"],
        summary="Log in with email and password",
        request=LoginSerializer,
        responses={
            200: UserProfileSerializer,
            400: error_response("Invalid login payload."),
            401: error_response("Invalid credentials."),
            429: error_response("Login rate limit exceeded."),
        },
    )
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        return Response(UserProfileSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["auth"],
        summary="Log out and invalidate the session",
        request=None,
        responses={204: None, 401: error_response("Authentication is required.")},
    )
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["auth"],
        summary="Get the current user",
        responses={200: UserProfileSerializer, 401: error_response("Authentication is required.")},
    )
    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)


class PasswordResetRequestView(APIView):
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        tags=["auth"],
        summary="Request a password reset email",
        request=PasswordResetRequestSerializer,
        responses={
            200: DetailResponseSerializer,
            400: error_response("Invalid email address."),
            429: error_response("Password reset rate limit exceeded."),
        },
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(serializer.validated_data["email"])
        return Response(
            {
                "detail": (
                    "If an account exists for this address, a password reset email has been sent."
                )
            }
        )


class PasswordResetConfirmView(APIView):
    @extend_schema(
        tags=["auth"],
        summary="Confirm a password reset",
        request=PasswordResetConfirmSerializer,
        responses={
            200: DetailResponseSerializer,
            400: error_response("The reset token or new password is invalid."),
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_password_reset(**serializer.validated_data)
        return Response({"detail": "Password has been reset."})
