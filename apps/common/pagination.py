from django.core.paginator import InvalidPage
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.common.exceptions import InvalidPagination, ResourceNotFound


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_size(self, request) -> int | None:
        raw_size = request.query_params.get(self.page_size_query_param)
        if raw_size is None:
            return self.page_size
        if not raw_size.isdigit() or not 1 <= int(raw_size) <= self.max_page_size:
            raise InvalidPagination()
        return int(raw_size)

    def paginate_queryset(self, queryset, request, view=None):
        raw_page = request.query_params.get(self.page_query_param)
        if raw_page is not None and (not raw_page.isdigit() or int(raw_page) < 1):
            raise InvalidPagination()

        try:
            return super().paginate_queryset(queryset, request, view)
        except InvalidPage as exc:
            raise ResourceNotFound() from exc

    def get_paginated_response(self, data) -> Response:
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            },
            status=status.HTTP_200_OK,
        )
