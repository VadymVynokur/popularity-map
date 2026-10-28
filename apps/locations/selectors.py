from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import (
    Avg,
    Case,
    Count,
    DecimalField,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce, Lower, Round
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.common.exceptions import InvalidFilterRange, InvalidOrdering
from apps.locations.models import Location, LocationView
from apps.locations.popularity import (
    RATING_MAX,
    RATING_WEIGHT,
    REVIEWS_SATURATION,
    REVIEWS_WEIGHT,
    SCORE_SCALE,
    VIEWS_SATURATION,
    VIEWS_WEIGHT,
)
from apps.reviews.models import Review

RATING_FIELD = DecimalField(max_digits=2, decimal_places=1)
RATING_AVG_FIELD = DecimalField(max_digits=3, decimal_places=2)


def location_queryset_with_metrics(now=None):
    now = now or timezone.now()
    week_ago = now - timedelta(days=7)

    active_reviews = Review.objects.filter(location=OuterRef("pk"), deleted_at__isnull=True)
    rating_subquery = (
        active_reviews.values("location").annotate(value=Avg("rating")).values("value")[:1]
    )
    count_subquery = (
        active_reviews.values("location").annotate(value=Count("id")).values("value")[:1]
    )
    views_subquery = (
        LocationView.objects.filter(
            location=OuterRef("pk"),
            viewed_at__gte=week_ago,
            viewed_at__lte=now,
        )
        .values("location")
        .annotate(value=Count("id"))
        .values("value")[:1]
    )

    queryset = Location.objects.annotate(
        rating_avg=Subquery(rating_subquery, output_field=RATING_AVG_FIELD),
        review_count=Coalesce(
            Subquery(count_subquery, output_field=IntegerField()),
            Value(0),
        ),
        views_7d=Coalesce(
            Subquery(views_subquery, output_field=IntegerField()),
            Value(0),
        ),
    ).annotate(
        rating=Case(
            When(
                rating_avg__isnull=True,
                then=Value(None, output_field=RATING_FIELD),
            ),
            default=Round(F("rating_avg"), 1, output_field=RATING_FIELD),
            output_field=RATING_FIELD,
        ),
    )

    rating_float = Coalesce(
        Cast(F("rating"), FloatField()),
        Value(0.0),
        output_field=FloatField(),
    )
    reviews_float = Cast(F("review_count"), FloatField())
    views_float = Cast(F("views_7d"), FloatField())
    raw_popularity = SCORE_SCALE * (
        RATING_WEIGHT * rating_float / RATING_MAX
        + REVIEWS_WEIGHT * reviews_float / (reviews_float + REVIEWS_SATURATION)
        + VIEWS_WEIGHT * views_float / (views_float + VIEWS_SATURATION)
    )
    popularity_decimal = Cast(
        raw_popularity,
        output_field=DecimalField(max_digits=12, decimal_places=6),
    )
    queryset = queryset.annotate(
        popularity=Cast(
            Round(popularity_decimal, 2),
            output_field=FloatField(),
        )
    )
    return queryset.select_related("created_by").prefetch_related("categories")


def _parse_bound(
    params,
    key: str,
    *,
    minimum: Decimal,
    maximum: Decimal,
) -> Decimal | None:
    raw = params.get(key)
    if raw is None or raw == "":
        return None
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ValidationError({key: ["A valid number is required."]}) from None
    if not value.is_finite() or not minimum <= value <= maximum:
        raise ValidationError({key: [f"Value must be between {minimum} and {maximum}."]})
    return value


def _parse_bbox(params) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    raw = params.get("bbox")
    if raw is None:
        return None

    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 4:
        raise ValidationError({"bbox": ["bbox must contain exactly four comma-separated numbers."]})

    try:
        west, south, east, north = (Decimal(part) for part in parts)
    except (InvalidOperation, ValueError):
        raise ValidationError({"bbox": ["bbox values must be valid numbers."]}) from None

    if not all(value.is_finite() for value in (west, south, east, north)):
        raise ValidationError({"bbox": ["bbox values must be finite numbers."]})

    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValidationError({"bbox": ["bbox longitudes must be between -180 and 180."]})
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValidationError({"bbox": ["bbox latitudes must be between -90 and 90."]})

    if west >= east or south >= north:
        raise ValidationError({"bbox": ["bbox requires west < east and south < north."]})

    return west, south, east, north


def apply_filters(queryset, params):
    search = (params.get("search") or "").strip()
    if search:
        if len(search) > 100:
            raise ValidationError({"search": ["Search text must be at most 100 characters."]})
        queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

    bbox = _parse_bbox(params)
    if bbox is not None:
        west, south, east, north = bbox
        queryset = queryset.filter(
            latitude__gte=south,
            latitude__lte=north,
            longitude__gte=west,
            longitude__lte=east,
        )

    categories = [value for value in params.getlist("category") if value]
    if categories:
        category_filter = Q()
        for category in categories:
            category_filter |= Q(categories__name__iexact=category)
        queryset = queryset.filter(category_filter).distinct()

    author = params.get("author")
    if author:
        queryset = queryset.filter(created_by__username__iexact=author)

    rating_min = _parse_bound(params, "rating_min", minimum=Decimal("1"), maximum=Decimal("5"))
    rating_max = _parse_bound(params, "rating_max", minimum=Decimal("1"), maximum=Decimal("5"))
    popularity_min = _parse_bound(
        params,
        "popularity_min",
        minimum=Decimal("0"),
        maximum=Decimal("100"),
    )
    popularity_max = _parse_bound(
        params,
        "popularity_max",
        minimum=Decimal("0"),
        maximum=Decimal("100"),
    )

    if rating_min is not None and rating_max is not None and rating_min > rating_max:
        raise InvalidFilterRange()
    if (
        popularity_min is not None
        and popularity_max is not None
        and popularity_min > popularity_max
    ):
        raise InvalidFilterRange()

    if rating_min is not None:
        queryset = queryset.filter(rating__gte=rating_min)
    if rating_max is not None:
        queryset = queryset.filter(rating__lte=rating_max)
    if popularity_min is not None:
        queryset = queryset.filter(popularity__gte=popularity_min)
    if popularity_max is not None:
        queryset = queryset.filter(popularity__lte=popularity_max)

    return queryset


def _tie_breakers(excluded: set[str]):
    ordering = []
    if "popularity" not in excluded:
        ordering.append(F("popularity").desc())
    if "rating" not in excluded:
        ordering.append(F("rating").desc(nulls_last=True))
    if "views_7d" not in excluded:
        ordering.append(F("views_7d").desc())
    ordering.extend([Lower("name").asc(), F("id").asc()])
    return ordering


def apply_ordering(queryset, ordering: str | None):
    ordering = ordering or "-popularity"
    allowed = {
        "created_at",
        "-created_at",
        "rating",
        "-rating",
        "popularity",
        "-popularity",
    }
    if ordering not in allowed:
        raise InvalidOrdering()

    field = ordering.lstrip("-")
    descending = ordering.startswith("-")
    if field == "created_at":
        primary = F("created_at").desc() if descending else F("created_at").asc()
    elif field == "rating":
        primary = (
            F("rating").desc(nulls_last=True) if descending else F("rating").asc(nulls_last=True)
        )
    else:
        primary = F("popularity").desc() if descending else F("popularity").asc()

    return queryset.order_by(primary, *_tie_breakers({field}))


def build_location_queryset(params, *, ordering: str | None = None):
    queryset = location_queryset_with_metrics().active()
    queryset = apply_filters(queryset, params)
    return apply_ordering(queryset, ordering if ordering is not None else params.get("ordering"))
