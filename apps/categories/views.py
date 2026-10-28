from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.categories.models import Category
from apps.categories.serializers import CategorySerializer
from apps.categories.services import create_category, delete_category, update_category
from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import IsAdminRole
from apps.common.schema import error_response, paginated_response


class CategoryListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return []

    @extend_schema(
        tags=["categories"],
        summary="List categories",
        operation_id="categories_list",
        responses={200: paginated_response("PaginatedCategory", CategorySerializer)},
    )
    def get(self, request):
        queryset = Category.objects.all()
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = CategorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["categories"],
        summary="Create a category (admin only)",
        request=CategorySerializer,
        responses={
            201: CategorySerializer,
            400: error_response("Invalid category name."),
            401: error_response("Authentication is required."),
            403: error_response("Administrator role is required."),
            409: error_response("A category with this name already exists."),
        },
    )
    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = create_category(**serializer.validated_data)
        return Response(CategorySerializer(category).data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [IsAdminRole()]
        return []

    def get_object(self, pk: int) -> Category:
        return get_object_or_404(Category, pk=pk)

    @extend_schema(
        tags=["categories"],
        summary="Get a category",
        operation_id="categories_retrieve",
        responses={200: CategorySerializer, 404: error_response("Category not found.")},
    )
    def get(self, request, pk: int):
        category = self.get_object(pk)
        return Response(CategorySerializer(category).data)

    @extend_schema(
        tags=["categories"],
        summary="Replace a category (admin only)",
        request=CategorySerializer,
        responses={
            200: CategorySerializer,
            400: error_response("Invalid category name."),
            401: error_response("Authentication is required."),
            403: error_response("Administrator role is required."),
            404: error_response("Category not found."),
        },
    )
    def put(self, request, pk: int):
        category = self.get_object(pk)
        serializer = CategorySerializer(category, data=request.data)
        serializer.is_valid(raise_exception=True)
        category = update_category(category, **serializer.validated_data)
        return Response(CategorySerializer(category).data)

    @extend_schema(
        tags=["categories"],
        summary="Partially update a category (admin only)",
        request=CategorySerializer,
        responses={
            200: CategorySerializer,
            400: error_response("Invalid category name."),
            401: error_response("Authentication is required."),
            403: error_response("Administrator role is required."),
            404: error_response("Category not found."),
        },
    )
    def patch(self, request, pk: int):
        category = self.get_object(pk)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = update_category(category, **serializer.validated_data)
        return Response(CategorySerializer(category).data)

    @extend_schema(
        tags=["categories"],
        summary="Delete an unused category (admin only)",
        responses={
            204: None,
            401: error_response("Authentication is required."),
            403: error_response("Administrator role is required."),
            404: error_response("Category not found."),
            409: error_response("The category is used by at least one location."),
        },
    )
    def delete(self, request, pk: int):
        category = self.get_object(pk)
        delete_category(category)
        return Response(status=status.HTTP_204_NO_CONTENT)
