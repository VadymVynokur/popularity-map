from rest_framework import serializers

from apps.reviews.models import Review, ReviewReaction


class ReviewAuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)


class ReviewReadSerializer(serializers.ModelSerializer):
    author = ReviewAuthorSerializer(read_only=True)
    location = serializers.PrimaryKeyRelatedField(read_only=True)
    likes_count = serializers.IntegerField(read_only=True)
    dislikes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "location",
            "author",
            "rating",
            "comment",
            "created_at",
            "updated_at",
            "likes_count",
            "dislikes_count",
        )
        read_only_fields = fields


class ReviewWriteSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(
        max_length=2000,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=False,
    )


class ReactionSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ReviewReaction.Type.choices)


class ReactionStateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ReviewReaction.Type.choices, allow_null=True)
