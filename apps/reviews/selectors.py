from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from apps.reviews.models import Review, ReviewReaction


def review_queryset_with_counts():
    reactions = ReviewReaction.objects.filter(review=OuterRef("pk"))
    likes = (
        reactions.filter(type=ReviewReaction.Type.LIKE)
        .values("review")
        .annotate(value=Count("id"))
        .values("value")[:1]
    )
    dislikes = (
        reactions.filter(type=ReviewReaction.Type.DISLIKE)
        .values("review")
        .annotate(value=Count("id"))
        .values("value")[:1]
    )
    return Review.objects.select_related("author", "location").annotate(
        likes_count=Coalesce(Subquery(likes, output_field=IntegerField()), Value(0)),
        dislikes_count=Coalesce(Subquery(dislikes, output_field=IntegerField()), Value(0)),
    )
