from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.services import register_user
from apps.common.exceptions import InvalidCredentials


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "role", "email_verified", "date_joined")
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_username(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        return register_user(**validated_data)


class EmailConfirmationSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class ResendConfirmationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(
            request=request,
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None or not user.is_active or not user.email_verified:
            raise InvalidCredentials()
        attrs["user"] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
