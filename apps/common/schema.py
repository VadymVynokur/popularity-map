from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import OpenApiResponse, inline_serializer
from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField(allow_null=True)


class ErrorResponseSerializer(serializers.Serializer):
    error = ErrorDetailSerializer()


class DetailResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class CsrfResponseSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()


def paginated_response(name: str, item_serializer) -> type[serializers.Serializer]:
    return inline_serializer(
        name=name,
        fields={
            "count": serializers.IntegerField(),
            "next": serializers.CharField(allow_null=True),
            "previous": serializers.CharField(allow_null=True),
            "results": item_serializer(many=True),
        },
    )


def error_response(description: str) -> OpenApiResponse:
    return OpenApiResponse(response=ErrorResponseSerializer, description=description)


class SessionAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.common.authentication.SessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "sessionid",
            "description": (
                "Django session cookie. Unsafe session-authenticated requests also require "
                "the X-CSRFToken header matching the csrftoken cookie."
            ),
        }
