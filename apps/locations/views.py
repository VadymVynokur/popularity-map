import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import UnsupportedExportFormat
from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import IsOwnerOrAdmin
from apps.common.schema import error_response, paginated_response
from apps.locations.cache import get_cached_list, set_cached_list
from apps.locations.export import csv_export_response, json_export_response
from apps.locations.selectors import build_location_queryset, location_queryset_with_metrics
from apps.locations.serializers import (
    LocationExportRowSerializer,
    LocationReadSerializer,
    LocationWriteSerializer,
)
from apps.locations.services import (
    create_location,
    restore_location,
    soft_delete_location,
    update_location,
)
from apps.locations.view_tracking import identity_for_request, track_location_view

logger = logging.getLogger(__name__)

LOCATION_FILTER_PARAMETERS = [
    OpenApiParameter(
        "search",
        OpenApiTypes.STR,
        OpenApiParameter.QUERY,
        description="Case-insensitive substring search in name or description.",
    ),
    OpenApiParameter(
        "category",
        OpenApiTypes.STR,
        OpenApiParameter.QUERY,
        many=True,
        description="Category name, case-insensitive exact match. Repeat for OR semantics.",
    ),
    OpenApiParameter(
        "author",
        OpenApiTypes.STR,
        OpenApiParameter.QUERY,
        description="Author username, case-insensitive exact match.",
    ),
    OpenApiParameter(
        "bbox",
        OpenApiTypes.STR,
        OpenApiParameter.QUERY,
        description=(
            "Optional bounding box as exactly four comma-separated numbers in "
            "west,south,east,north order (longitude, latitude). Coordinates are inclusive. "
            "Longitudes must be within -180..180, latitudes within -90..90, with "
            "west < east and south < north. Example: 30.40,50.40,30.70,50.60. "
            "Invalid values return HTTP 400 validation_error."
        ),
        examples=[OpenApiExample("Kyiv center", value="30.40,50.40,30.70,50.60")],
    ),
    OpenApiParameter("rating_min", OpenApiTypes.NUMBER, OpenApiParameter.QUERY),
    OpenApiParameter("rating_max", OpenApiTypes.NUMBER, OpenApiParameter.QUERY),
    OpenApiParameter("popularity_min", OpenApiTypes.NUMBER, OpenApiParameter.QUERY),
    OpenApiParameter("popularity_max", OpenApiTypes.NUMBER, OpenApiParameter.QUERY),
    OpenApiParameter(
        "ordering",
        OpenApiTypes.STR,
        OpenApiParameter.QUERY,
        enum=["created_at", "-created_at", "rating", "-rating", "popularity", "-popularity"],
        description="Default is -popularity with deterministic tie-breakers.",
    ),
    OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY),
    OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY),
]


def _read_serializer(location) -> LocationReadSerializer:
    return LocationReadSerializer(location)


def _location_read(pk: int):
    return get_object_or_404(location_queryset_with_metrics(), pk=pk)


class LocationListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return []

    @extend_schema(
        tags=["locations"],
        summary="List active locations",
        operation_id="locations_list",
        parameters=LOCATION_FILTER_PARAMETERS,
        responses={
            200: paginated_response("PaginatedLocation", LocationReadSerializer),
            400: error_response("Invalid search, filter, ordering, or pagination parameter."),
            404: error_response("Requested page does not exist."),
        },
    )
    def get(self, request):
        cached = get_cached_list(request)
        if cached is not None:
            return Response(cached)

        queryset = build_location_queryset(request.query_params)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = LocationReadSerializer(page, many=True)
        data = paginator.get_paginated_response(serializer.data).data
        set_cached_list(request, data)
        return Response(data)

    @extend_schema(
        tags=["locations"],
        summary="Create a location",
        request=LocationWriteSerializer,
        responses={
            201: LocationReadSerializer,
            400: error_response("Invalid location data."),
            401: error_response("Authentication is required."),
        },
    )
    def post(self, request):
        serializer = LocationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = create_location(data=serializer.validated_data, user=request.user)
        return Response(
            _read_serializer(_location_read(location.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class LocationDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return []
        return [IsAuthenticated(), IsOwnerOrAdmin()]

    def get_object(self):
        return get_object_or_404(
            location_queryset_with_metrics().active(),
            pk=self.kwargs["pk"],
        )

    @extend_schema(
        tags=["locations"],
        summary="Get an active location",
        operation_id="locations_retrieve",
        description="A successful request records at most one view event per identity per hour.",
        responses={200: LocationReadSerializer, 404: error_response("Location not found.")},
    )
    def get(self, request, pk: int):
        location = self.get_object()
        response = Response(_read_serializer(location).data)
        try:
            track_location_view(location, identity_for_request(request))
        except Exception:
            logger.exception("Failed to record location view for location %s", location.pk)
        return response

    @extend_schema(
        tags=["locations"],
        summary="Replace a location",
        request=LocationWriteSerializer,
        responses={
            200: LocationReadSerializer,
            400: error_response("Invalid location data."),
            401: error_response("Authentication is required."),
            403: error_response("Only the author or an administrator may change this location."),
            404: error_response("Location not found."),
        },
    )
    def put(self, request, pk: int):
        location = self.get_object()
        self.check_object_permissions(request, location)
        serializer = LocationWriteSerializer(location, data=request.data)
        serializer.is_valid(raise_exception=True)
        location = update_location(location, data=serializer.validated_data)
        return Response(_read_serializer(_location_read(location.pk)).data)

    @extend_schema(
        tags=["locations"],
        summary="Partially update a location",
        request=LocationWriteSerializer,
        responses={
            200: LocationReadSerializer,
            400: error_response("Invalid location data."),
            401: error_response("Authentication is required."),
            403: error_response("Only the author or an administrator may change this location."),
            404: error_response("Location not found."),
        },
    )
    def patch(self, request, pk: int):
        location = self.get_object()
        self.check_object_permissions(request, location)
        serializer = LocationWriteSerializer(location, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        location = update_location(location, data=serializer.validated_data)
        return Response(_read_serializer(_location_read(location.pk)).data)

    @extend_schema(
        tags=["locations"],
        summary="Soft delete a location",
        responses={
            204: None,
            401: error_response("Authentication is required."),
            403: error_response("Only the author or an administrator may delete this location."),
            404: error_response("Location not found."),
        },
    )
    def delete(self, request, pk: int):
        location = self.get_object()
        self.check_object_permissions(request, location)
        soft_delete_location(location)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeletedLocationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["locations"],
        summary="List soft-deleted locations",
        description="Administrators see all deleted locations; other users see only their own.",
        parameters=[
            OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY),
        ],
        responses={
            200: paginated_response("PaginatedDeletedLocation", LocationReadSerializer),
            401: error_response("Authentication is required."),
        },
    )
    def get(self, request):
        queryset = location_queryset_with_metrics().deleted()
        if getattr(request.user, "role", None) != "admin":
            queryset = queryset.filter(created_by=request.user)
        queryset = queryset.order_by("-deleted_at", "-id")
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = LocationReadSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class LocationRestoreView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_object(self):
        queryset = location_queryset_with_metrics().deleted()
        if getattr(self.request.user, "role", None) != "admin":
            queryset = queryset.filter(created_by=self.request.user)
        return get_object_or_404(queryset, pk=self.kwargs["pk"])

    @extend_schema(
        tags=["locations"],
        summary="Restore a soft-deleted location",
        request=None,
        responses={
            200: LocationReadSerializer,
            401: error_response("Authentication is required."),
            403: error_response("Only the author or an administrator may restore this location."),
            404: error_response("Deleted location not found in the allowed scope."),
        },
    )
    def post(self, request, pk: int):
        location = self.get_object()
        self.check_object_permissions(request, location)
        location = restore_location(location)
        return Response(_read_serializer(_location_read(location.pk)).data)


class LocationExportView(APIView):
    @extend_schema(
        tags=["locations"],
        summary="Export active locations as JSON or CSV",
        description=(
            "Applies the same search, filters, and ordering as the list endpoint, ignores "
            "pagination, and returns all matching active locations."
        ),
        parameters=[
            OpenApiParameter(
                "format",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=True,
                enum=["json", "csv"],
                description="Export format. Missing or unsupported values return 400.",
            ),
            *LOCATION_FILTER_PARAMETERS,
        ],
        responses={
            (200, "application/json"): OpenApiResponse(
                response=LocationExportRowSerializer(many=True),
                description="JSON attachment.",
            ),
            (200, "text/csv"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="CSV attachment generated with pandas.",
            ),
            400: error_response("Unsupported export format or invalid filter parameter."),
        },
    )
    def get(self, request):
        export_format = request.query_params.get("format")
        if export_format not in {"json", "csv"}:
            raise UnsupportedExportFormat()
        queryset = build_location_queryset(request.query_params)
        if export_format == "json":
            return json_export_response(queryset)
        return csv_export_response(queryset)
