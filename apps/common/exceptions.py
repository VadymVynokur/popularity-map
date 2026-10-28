import logging
from typing import Any

from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class APIError(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "validation_error"
    default_detail = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Any = None,
    ) -> None:
        self.code = code or self.default_code
        self.details = details
        super().__init__(message or self.default_detail, code=self.code)


class InvalidOrdering(APIError):
    default_code = "invalid_ordering"
    default_detail = "The requested ordering is not supported."


class InvalidFilterRange(APIError):
    default_code = "invalid_filter_range"
    default_detail = "The minimum filter boundary cannot exceed the maximum boundary."


class InvalidPagination(APIError):
    default_code = "invalid_pagination"
    default_detail = "Pagination parameters are invalid."


class UnsupportedExportFormat(APIError):
    default_code = "unsupported_export_format"
    default_detail = "The requested export format is not supported."


class AuthenticationRequired(APIError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "authentication_required"
    default_detail = "Authentication is required."


class InvalidCredentials(APIError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "invalid_credentials"
    default_detail = "Invalid credentials."


class InvalidToken(APIError):
    default_code = "validation_error"
    default_detail = "The token is invalid or has expired."


class PermissionDeniedError(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "permission_denied"
    default_detail = "You do not have permission to perform this action."


class ResourceNotFound(APIError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "not_found"
    default_detail = "The requested resource was not found."


class Conflict(APIError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = "The request conflicts with the current state of the resource."


class EmailAlreadyRegistered(Conflict):
    default_code = "email_already_registered"
    default_detail = "An account with this email already exists."


class UsernameAlreadyRegistered(Conflict):
    default_code = "username_already_registered"
    default_detail = "This username is already registered."


class CategoryInUse(Conflict):
    default_code = "category_in_use"
    default_detail = "The category is used by at least one location."


class ReviewAlreadyExists(Conflict):
    default_code = "review_already_exists"
    default_detail = "An active review for this location already exists."


class LocationNotActive(Conflict):
    default_code = "location_not_active"
    default_detail = "This operation requires an active location."


def _error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def _plain_detail(detail: Any) -> Any:
    if isinstance(detail, dict):
        return {key: _plain_detail(value) for key, value in detail.items()}
    if isinstance(detail, list):
        return [_plain_detail(value) for value in detail]
    return str(detail)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API exception", exc_info=exc)
        return Response(
            _error_payload(
                "internal_error",
                "An unexpected internal error occurred.",
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, APIError):
        code = exc.code
        message = str(exc.detail)
        details = exc.details
    elif isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
        message = "The request contains invalid data."
        details = _plain_detail(exc.detail)
        if isinstance(details, list):
            details = {"non_field_errors": details}
    elif isinstance(exc, exceptions.NotAuthenticated):
        code = "authentication_required"
        message = "Authentication is required."
        details = None
    elif isinstance(exc, exceptions.AuthenticationFailed):
        code = "invalid_credentials"
        message = "Invalid credentials."
        details = None
    elif isinstance(exc, exceptions.PermissionDenied):
        code = "permission_denied"
        message = "You do not have permission to perform this action."
        details = None
    elif isinstance(exc, (exceptions.NotFound, Http404)):
        code = "not_found"
        message = "The requested resource was not found."
        details = None
    elif isinstance(exc, exceptions.Throttled):
        code = "rate_limited"
        message = "Too many requests. Please try again later."
        details = None
    elif isinstance(exc, exceptions.ParseError):
        code = "validation_error"
        message = "The request body could not be parsed."
        details = None
    elif isinstance(exc, exceptions.MethodNotAllowed):
        code = "validation_error"
        message = "This HTTP method is not allowed for the endpoint."
        details = None
    elif isinstance(exc, exceptions.UnsupportedMediaType):
        code = "validation_error"
        message = "The request media type is not supported."
        details = None
    else:
        code = getattr(exc, "default_code", "validation_error")
        message = str(getattr(exc, "detail", "The request could not be processed."))
        details = None

    response.data = _error_payload(code, message, details)
    return response
