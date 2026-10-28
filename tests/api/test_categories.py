import pytest
from django.urls import reverse

from apps.categories.models import Category
from apps.locations.services import soft_delete_location


@pytest.mark.django_db
def test_seed_categories_exist(api_client):
    response = api_client.get(reverse("category-list"))
    assert response.status_code == 200
    assert response.data["count"] >= 12
    names = {item["name"] for item in response.data["results"]}
    assert {"Cafe", "Coffee shop", "Park", "Other"} <= names


@pytest.mark.django_db
def test_public_can_read_category_detail(api_client, category):
    response = api_client.get(reverse("category-detail", args=[category.pk]))
    assert response.status_code == 200
    assert response.data == {"id": category.pk, "name": "Cafe"}


@pytest.mark.django_db
def test_non_admin_cannot_create_or_change_categories(auth_client):
    response = auth_client.post(reverse("category-list"), {"name": "Rooftop"}, format="json")
    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"


@pytest.mark.django_db
def test_anonymous_cannot_create_category(api_client):
    response = api_client.post(reverse("category-list"), {"name": "Rooftop"}, format="json")
    assert response.status_code == 401
    assert response.data["error"]["code"] == "authentication_required"


@pytest.mark.django_db
def test_admin_can_create_and_update_category(admin_client):
    created = admin_client.post(reverse("category-list"), {"name": "Rooftop"}, format="json")
    assert created.status_code == 201
    category_id = created.data["id"]

    updated = admin_client.patch(
        reverse("category-detail", args=[category_id]),
        {"name": "Rooftop bar"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["name"] == "Rooftop bar"


@pytest.mark.django_db
def test_category_name_is_case_insensitive_unique(admin_client):
    response = admin_client.post(reverse("category-list"), {"name": "cafe"}, format="json")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert "name" in response.data["error"]["details"]


@pytest.mark.django_db
def test_category_in_use_cannot_be_deleted(admin_client, location):
    category_id = location.categories.first().pk
    response = admin_client.delete(reverse("category-detail", args=[category_id]))
    assert response.status_code == 409
    assert response.data["error"]["code"] == "category_in_use"
    assert Category.objects.filter(pk=category_id).exists()


@pytest.mark.django_db
def test_soft_deleted_location_still_blocks_category_delete(admin_client, location):
    soft_delete_location(location)
    category_id = location.categories.first().pk
    response = admin_client.delete(reverse("category-detail", args=[category_id]))
    assert response.status_code == 409
    assert response.data["error"]["code"] == "category_in_use"


@pytest.mark.django_db
def test_unused_category_can_be_deleted(admin_client):
    category = Category.objects.create(name="Temporary")
    response = admin_client.delete(reverse("category-detail", args=[category.pk]))
    assert response.status_code == 204
    assert not Category.objects.filter(pk=category.pk).exists()
