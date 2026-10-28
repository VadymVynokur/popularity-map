from datetime import UTC

import pandas as pd
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone

EXPORT_FIELDS = [
    "id",
    "name",
    "description",
    "categories",
    "address",
    "latitude",
    "longitude",
    "author_username",
    "created_at",
    "updated_at",
    "rating",
    "review_count",
    "views_7d",
    "popularity",
]


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def serialize_export_row(location) -> dict:
    return {
        "id": location.id,
        "name": location.name,
        "description": location.description,
        "categories": [category.name for category in location.categories.all()],
        "address": location.address,
        "latitude": str(location.latitude),
        "longitude": str(location.longitude),
        "author_username": location.created_by.username,
        "created_at": _iso(location.created_at),
        "updated_at": _iso(location.updated_at),
        "rating": float(location.rating) if location.rating is not None else None,
        "review_count": location.review_count,
        "views_7d": location.views_7d,
        "popularity": float(location.popularity),
    }


def _filename(extension: str) -> str:
    return f"locations-{timezone.now().strftime('%Y%m%d')}.{extension}"


def json_export_response(queryset) -> JsonResponse:
    rows = [serialize_export_row(location) for location in queryset]
    response = JsonResponse(rows, safe=False, json_dumps_params={"ensure_ascii": False})
    response["Content-Disposition"] = f'attachment; filename="{_filename("json")}"'
    return response


def _csv_rows(queryset):
    first = True
    columns = EXPORT_FIELDS
    for location in queryset.iterator(chunk_size=500):
        row = serialize_export_row(location)
        row["categories"] = "|".join(row["categories"])
        frame = pd.DataFrame([row], columns=columns)
        yield frame.to_csv(index=False, header=first)
        first = False
    if first:
        yield pd.DataFrame(columns=columns).to_csv(index=False)


def csv_export_response(queryset) -> StreamingHttpResponse:
    response = StreamingHttpResponse(_csv_rows(queryset), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename("csv")}"'
    return response
