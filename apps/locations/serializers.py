from decimal import Decimal

from rest_framework import serializers

from apps.categories.models import Category
from apps.categories.serializers import CategorySerializer
from apps.locations.models import Location


class AuthorBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)


class LocationReadSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)
    created_by = AuthorBriefSerializer(read_only=True)
    rating = serializers.DecimalField(
        max_digits=2,
        decimal_places=1,
        allow_null=True,
        coerce_to_string=False,
        read_only=True,
    )
    review_count = serializers.IntegerField(read_only=True)
    views_7d = serializers.IntegerField(read_only=True)
    popularity = serializers.FloatField(read_only=True)

    class Meta:
        model = Location
        fields = (
            "id",
            "name",
            "description",
            "categories",
            "address",
            "latitude",
            "longitude",
            "created_by",
            "created_at",
            "updated_at",
            "rating",
            "review_count",
            "views_7d",
            "popularity",
        )
        read_only_fields = fields


class LocationExportRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    categories = serializers.ListField(child=serializers.CharField())
    address = serializers.CharField()
    latitude = serializers.CharField()
    longitude = serializers.CharField()
    author_username = serializers.CharField()
    created_at = serializers.CharField()
    updated_at = serializers.CharField()
    rating = serializers.FloatField(allow_null=True)
    review_count = serializers.IntegerField()
    views_7d = serializers.IntegerField()
    popularity = serializers.FloatField()


class LocationWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(max_length=5000, allow_blank=False)
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        allow_empty=False,
        write_only=True,
    )
    address = serializers.CharField(max_length=255)
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
    )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_description(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_address(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value
