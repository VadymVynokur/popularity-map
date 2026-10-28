from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.categories.models import Category
from apps.locations.models import Location, LocationView
from apps.locations.popularity import calculate_popularity
from apps.locations.services import soft_delete_location
from apps.reviews.models import Review


def _payload(**overrides):
    data = {
        "name": "Riverside Cafe",
        "description": "A small cafe next to the river.",
        "category_ids": [Category.objects.get(name="Cafe").pk],
        "address": "12 River Street",
        "latitude": "50.450100",
        "longitude": "30.523400",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_anonymous_cannot_create_location(api_client):
    response = api_client.post(reverse("location-list"), _payload(), format="json")
    assert response.status_code == 401
    assert response.data["error"]["code"] == "authentication_required"


@pytest.mark.django_db
def test_create_location_assigns_server_fields(auth_client, verified_user):
    response = auth_client.post(reverse("location-list"), _payload(), format="json")

    assert response.status_code == 201
    assert response.data["created_by"] == {
        "id": verified_user.pk,
        "username": verified_user.username,
    }
    assert response.data["categories"] == [
        {"id": Category.objects.get(name="Cafe").pk, "name": "Cafe"}
    ]
    assert response.data["rating"] is None
    assert response.data["review_count"] == 0
    assert response.data["views_7d"] == 0
    assert response.data["popularity"] == 0.0
    assert Location.objects.count() == 1


@pytest.mark.django_db
def test_create_requires_at_least_one_category(auth_client):
    response = auth_client.post(reverse("location-list"), _payload(category_ids=[]), format="json")
    assert response.status_code == 400
    assert "category_ids" in response.data["error"]["details"]


@pytest.mark.django_db
def test_create_rejects_unknown_category(auth_client):
    response = auth_client.post(
        reverse("location-list"), _payload(category_ids=[99999]), format="json"
    )
    assert response.status_code == 400
    assert "category_ids" in response.data["error"]["details"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [("latitude", "90.000001"), ("latitude", "-90.000001"), ("longitude", "180.000001")],
)
def test_coordinate_boundaries_are_validated(auth_client, field, value):
    response = auth_client.post(reverse("location-list"), _payload(**{field: value}), format="json")
    assert response.status_code == 400
    assert field in response.data["error"]["details"]


@pytest.mark.django_db
def test_location_metrics_and_detail(api_client, location, verified_user):
    other = User.objects.create_user(
        email="other@example.com",
        username="other_user",
        password="a-strong-password",
    )
    Review.objects.create(location=location, author=verified_user, rating=5, comment="Great")
    Review.objects.create(location=location, author=other, rating=4, comment="Good")
    now = timezone.now()
    LocationView.objects.create(location=location, identity_hash="a" * 64, viewed_at=now)
    LocationView.objects.create(location=location, identity_hash="b" * 64, viewed_at=now)
    LocationView.objects.create(
        location=location,
        identity_hash="c" * 64,
        viewed_at=now - timedelta(days=8),
    )

    response = api_client.get(reverse("location-detail", args=[location.pk]))

    assert response.status_code == 200
    assert response.data["rating"] == 4.5
    assert response.data["review_count"] == 2
    assert response.data["views_7d"] == 2
    assert response.data["popularity"] == calculate_popularity(
        rating=Decimal("4.5"), review_count=2, views_7d=2
    )


@pytest.mark.django_db
def test_list_search_and_category_filter(api_client, location):
    other_category = Category.objects.get(name="Park")
    second = Location.objects.create(
        name="Green Park",
        description="A quiet green place.",
        address="1 Park Avenue",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=location.created_by,
    )
    second.categories.set([other_category])

    response = api_client.get(reverse("location-list"), {"search": "river"})
    assert response.status_code == 200
    assert [item["id"] for item in response.data["results"]] == [location.pk]

    response = api_client.get(reverse("location-list"), {"category": "park"})
    assert response.status_code == 200
    assert [item["id"] for item in response.data["results"]] == [second.pk]

    response = api_client.get(
        reverse("location-list"),
        {"category": ["Cafe", "Park"]},
    )
    assert response.status_code == 200
    assert {item["id"] for item in response.data["results"]} == {location.pk, second.pk}


@pytest.mark.django_db
def test_ordering_and_pagination_validation(api_client, location):
    assert api_client.get(reverse("location-list"), {"ordering": "unknown"}).status_code == 400
    assert (
        api_client.get(reverse("location-list"), {"ordering": "unknown"}).data["error"]["code"]
        == "invalid_ordering"
    )
    assert api_client.get(reverse("location-list"), {"page": "0"}).status_code == 400
    assert (
        api_client.get(reverse("location-list"), {"page": "0"}).data["error"]["code"]
        == "invalid_pagination"
    )
    assert api_client.get(reverse("location-list"), {"page_size": "101"}).status_code == 400
    assert api_client.get(reverse("location-list"), {"page": "999"}).status_code == 404
    assert (
        api_client.get(reverse("location-list"), {"page": "999"}).data["error"]["code"]
        == "not_found"
    )


@pytest.mark.django_db
def test_invalid_rating_range(api_client, location):
    response = api_client.get(
        reverse("location-list"),
        {"rating_min": "5", "rating_max": "3"},
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "invalid_filter_range"


@pytest.mark.django_db
def test_owner_can_update_and_other_user_cannot(auth_client, location):
    response = auth_client.patch(
        reverse("location-detail", args=[location.pk]),
        {"name": "Updated Cafe"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["name"] == "Updated Cafe"

    other = User.objects.create_user(
        email="other@example.com",
        username="other_user",
        password="a-strong-password",
    )
    from rest_framework.test import APIClient

    other_client = APIClient()
    other_client.force_authenticate(other)
    denied = other_client.patch(
        reverse("location-detail", args=[location.pk]),
        {"name": "Hijacked"},
        format="json",
    )
    assert denied.status_code == 403
    assert denied.data["error"]["code"] == "permission_denied"


@pytest.mark.django_db
def test_admin_can_update_and_delete(auth_client, admin_client, location):
    response = admin_client.patch(
        reverse("location-detail", args=[location.pk]),
        {"name": "Admin Cafe"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["name"] == "Admin Cafe"

    response = admin_client.delete(reverse("location-detail", args=[location.pk]))
    assert response.status_code == 204
    location.refresh_from_db()
    assert location.deleted_at is not None


@pytest.mark.django_db
def test_soft_delete_hides_location_and_deleted_scope(
    api_client, auth_client, admin_client, location
):
    response = auth_client.delete(reverse("location-detail", args=[location.pk]))
    assert response.status_code == 204
    assert api_client.get(reverse("location-detail", args=[location.pk])).status_code == 404
    assert api_client.get(reverse("location-list")).data["count"] == 0

    deleted = auth_client.get(reverse("location-deleted-list"))
    assert deleted.status_code == 200
    assert deleted.data["count"] == 1
    assert deleted.data["results"][0]["id"] == location.pk

    other = User.objects.create_user(
        email="other@example.com",
        username="other_user",
        password="a-strong-password",
    )
    from rest_framework.test import APIClient

    other_client = APIClient()
    other_client.force_authenticate(other)
    assert other_client.get(reverse("location-deleted-list")).data["count"] == 0
    assert admin_client.get(reverse("location-deleted-list")).data["count"] == 1


@pytest.mark.django_db
def test_restore_requires_owner_or_admin_and_preserves_data(
    api_client, auth_client, location, verified_user
):
    Review.objects.create(location=location, author=verified_user, rating=5, comment="Great")
    LocationView.objects.create(location=location, identity_hash="a" * 64, viewed_at=timezone.now())
    soft_delete_location(location)

    other = User.objects.create_user(
        email="other@example.com",
        username="other_user",
        password="a-strong-password",
    )
    from rest_framework.test import APIClient

    other_client = APIClient()
    other_client.force_authenticate(other)
    assert other_client.post(reverse("location-restore", args=[location.pk])).status_code == 404

    restored = auth_client.post(reverse("location-restore", args=[location.pk]))
    assert restored.status_code == 200
    assert restored.data["review_count"] == 1
    assert restored.data["views_7d"] == 1
    assert api_client.get(reverse("location-detail", args=[location.pk])).status_code == 200


@pytest.mark.django_db
def test_export_requires_supported_format_and_returns_attachment(api_client, location):
    assert api_client.get(reverse("location-export")).status_code == 400
    assert (
        api_client.get(reverse("location-export")).data["error"]["code"]
        == "unsupported_export_format"
    )

    response = api_client.get(reverse("location-export"), {"format": "json"})
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('attachment; filename="locations-')
    assert response["Content-Disposition"].endswith('.json"')
    assert response.json()[0]["name"] == location.name

    response = api_client.get(reverse("location-export"), {"format": "csv"})
    assert response.status_code == 200
    content = b"".join(response.streaming_content).decode()
    assert "id,name,description,categories,address" in content
    assert location.name in content


@pytest.mark.django_db
def test_server_controlled_fields_cannot_be_overridden(auth_client, verified_user):
    response = auth_client.post(
        reverse("location-list"),
        _payload(
            id=99999,
            created_by=99999,
            created_at="2020-01-01T00:00:00Z",
            updated_at="2020-01-01T00:00:00Z",
            deleted_at="2020-01-01T00:00:00Z",
        ),
        format="json",
    )

    assert response.status_code == 201
    created = Location.objects.get(pk=response.data["id"])
    assert created.created_by == verified_user
    assert created.deleted_at is None
    assert created.created_at.year == timezone.now().year


@pytest.mark.django_db
def test_multiple_categories_are_supported(auth_client):
    cafe = Category.objects.get(name="Cafe")
    park = Category.objects.get(name="Park")

    response = auth_client.post(
        reverse("location-list"),
        _payload(category_ids=[cafe.pk, park.pk]),
        format="json",
    )

    assert response.status_code == 201
    assert {item["name"] for item in response.data["categories"]} == {"Cafe", "Park"}


@pytest.mark.django_db
def test_author_and_rating_filters(api_client, location, verified_user):
    other = User.objects.create_user(
        email="other@example.com",
        username="other_user",
        password="a-strong-password",
    )
    other_location = Location.objects.create(
        name="Other Cafe",
        description="Another cafe.",
        address="2 Other Street",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=other,
    )
    other_location.categories.set([Category.objects.get(name="Cafe")])
    Review.objects.create(location=location, author=verified_user, rating=5, comment="Great")

    by_author = api_client.get(reverse("location-list"), {"author": "OTHER_USER"})
    assert [item["id"] for item in by_author.data["results"]] == [other_location.pk]

    by_rating = api_client.get(reverse("location-list"), {"rating_min": 4})
    assert [item["id"] for item in by_rating.data["results"]] == [location.pk]

    no_rating = api_client.get(reverse("location-list"), {"rating_max": 5})
    assert [item["id"] for item in no_rating.data["results"]] == [location.pk]


@pytest.mark.django_db
def test_popularity_filters_and_ordering_tiebreaks(api_client, location, verified_user):
    low = Location.objects.create(
        name="Zulu",
        description="Low popularity.",
        address="1 Z Street",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=verified_user,
    )
    low.categories.set([Category.objects.get(name="Park")])
    alpha = Location.objects.create(
        name="alpha",
        description="Alpha.",
        address="2 A Street",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=verified_user,
    )
    alpha.categories.set([Category.objects.get(name="Park")])
    alpha_upper = Location.objects.create(
        name="Alpha",
        description="Alpha uppercase.",
        address="3 A Street",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=verified_user,
    )
    alpha_upper.categories.set([Category.objects.get(name="Park")])

    response = api_client.get(reverse("location-list"), {"popularity_max": 0})
    assert response.data["count"] == 4

    ordered = api_client.get(reverse("location-list"), {"ordering": "-popularity"})
    ids = [item["id"] for item in ordered.data["results"]]
    assert ids == [alpha.pk, alpha_upper.pk, location.pk, low.pk]

    by_rating = api_client.get(reverse("location-list"), {"ordering": "rating"})
    assert by_rating.status_code == 200
    assert all(item["rating"] is None for item in by_rating.data["results"])


@pytest.mark.django_db
def test_rating_filter_excludes_locations_without_reviews(api_client, location, verified_user):
    other = Location.objects.create(
        name="No Reviews",
        description="No reviews yet.",
        address="1 Empty Street",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=verified_user,
    )
    other.categories.set([Category.objects.get(name="Park")])
    Review.objects.create(location=location, author=verified_user, rating=5, comment="Great")

    response = api_client.get(reverse("location-list"), {"rating_min": 1})

    assert [item["id"] for item in response.data["results"]] == [location.pk]


@pytest.mark.django_db
def test_search_length_and_numeric_validation(api_client, location):
    too_long = api_client.get(reverse("location-list"), {"search": "x" * 101})
    assert too_long.status_code == 400
    assert too_long.data["error"]["code"] == "validation_error"

    invalid = api_client.get(reverse("location-list"), {"rating_min": "not-a-number"})
    assert invalid.status_code == 400
    assert "rating_min" in invalid.data["error"]["details"]

    invalid_popularity = api_client.get(reverse("location-list"), {"popularity_max": "101"})
    assert invalid_popularity.status_code == 400
    assert "popularity_max" in invalid_popularity.data["error"]["details"]


@pytest.mark.django_db
def test_whitespace_only_search_is_ignored(api_client, location):
    response = api_client.get(reverse("location-list"), {"search": "   "})

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == location.pk


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["rating_min", "rating_max", "popularity_min", "popularity_max"])
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numeric_filters_are_rejected(api_client, location, field, value):
    response = api_client.get(reverse("location-list"), {field: value})

    assert response.status_code == 400
    assert field in response.data["error"]["details"]


@pytest.mark.django_db
def test_description_max_length_is_enforced(auth_client):
    too_long = auth_client.post(
        reverse("location-list"),
        _payload(description="x" * 5001),
        format="json",
    )
    assert too_long.status_code == 400
    assert "description" in too_long.data["error"]["details"]

    allowed = auth_client.post(
        reverse("location-list"),
        _payload(description="x" * 5000),
        format="json",
    )
    assert allowed.status_code == 201
    assert len(allowed.data["description"]) == 5000


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["abc", "-1", "0", "101"])
def test_invalid_page_size_returns_standard_error(api_client, location, value):
    response = api_client.get(reverse("location-list"), {"page_size": value})

    assert response.status_code == 400
    assert response.data["error"]["code"] == "invalid_pagination"


@pytest.mark.django_db
def test_export_applies_filters_ignores_pagination_and_excludes_deleted(
    api_client,
    location,
    verified_user,
):
    deleted = Location.objects.create(
        name="Deleted Cafe",
        description="Gone.",
        address="1 Gone Street",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=verified_user,
    )
    deleted.categories.set([Category.objects.get(name="Cafe")])
    soft_delete_location(deleted)
    park = Category.objects.get(name="Park")
    park_location = Location.objects.create(
        name="Park Place",
        description="A park.",
        address="2 Park Street",
        latitude=Decimal("50.000000"),
        longitude=Decimal("30.000000"),
        created_by=verified_user,
    )
    park_location.categories.set([park])

    response = api_client.get(
        reverse("location-export"),
        {"format": "json", "category": "Cafe", "page": 999, "page_size": 1},
    )

    assert response.status_code == 200
    rows = response.json()
    assert [row["name"] for row in rows] == [location.name]
    assert rows[0]["categories"] == ["Cafe"]
    assert "email" not in rows[0]
    assert rows[0]["author_username"] == verified_user.username


@pytest.mark.django_db
def test_csv_export_escapes_commas_quotes_and_newlines(api_client, location):
    location.name = 'Cafe, "Riverside"\nBranch'
    location.description = "Line one, line two"
    location.save()

    response = api_client.get(reverse("location-export"), {"format": "csv"})
    content = b"".join(response.streaming_content).decode()

    assert response.status_code == 200
    assert '"Cafe, ""Riverside""\nBranch"' in content
    assert '"Line one, line two"' in content


@pytest.mark.django_db
def test_list_query_count_does_not_grow_with_page_size(api_client, verified_user):
    category = Category.objects.get(name="Cafe")
    for index in range(20):
        location = Location.objects.create(
            name=f"Cafe {index}",
            description="A cafe.",
            address=f"{index} Street",
            latitude=Decimal("50.000000"),
            longitude=Decimal("30.000000"),
            created_by=verified_user,
        )
        location.categories.set([category])
        Review.objects.create(location=location, author=verified_user, rating=5, comment="Great")

    with CaptureQueriesContext(connection) as queries:
        response = api_client.get(reverse("location-list"), {"page_size": 20})

    assert response.status_code == 200
    assert len(response.data["results"]) == 20
    assert len(queries) <= 6
