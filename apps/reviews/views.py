from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import IsOwner
from apps.common.schema import error_response, paginated_response
from apps.locations.models import Location
from apps.reviews.models import Review, ReviewReaction
from apps.reviews.selectors import review_queryset_with_counts
from apps.reviews.serializers import (
    ReactionSerializer,
    ReactionStateSerializer,
    ReviewReadSerializer,
    ReviewWriteSerializer,
)
from apps.reviews.services import (
    create_review,
    delete_reaction,
    replace_review,
    set_reaction,
    soft_delete_review,
)


def _review_read(pk: int):
    return get_object_or_404(review_queryset_with_counts().active(), pk=pk)


class ReviewListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return []

    def get_location(self) -> Location:
        return get_object_or_404(Location.objects.active(), pk=self.kwargs["location_id"])

    @extend_schema(
        tags=["reviews"],
        summary="List active reviews for a location",
        responses={
            200: paginated_response("PaginatedReview", ReviewReadSerializer),
            404: error_response("Active location not found."),
        },
    )
    def get(self, request, location_id: int):
        location = self.get_location()
        queryset = review_queryset_with_counts().filter(location=location).active()
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ReviewReadSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["reviews"],
        summary="Create a review for a location",
        request=ReviewWriteSerializer,
        responses={
            201: ReviewReadSerializer,
            400: error_response("Invalid rating or comment."),
            401: error_response("Authentication is required."),
            404: error_response("Active location not found."),
            409: error_response("An active review for this location already exists."),
        },
    )
    def post(self, request, location_id: int):
        location = self.get_location()
        serializer = ReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = create_review(location=location, author=request.user, **serializer.validated_data)
        return Response(
            ReviewReadSerializer(_review_read(review.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class ReviewDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return []
        return [IsAuthenticated(), IsOwner()]

    def get_object(self):
        return get_object_or_404(
            review_queryset_with_counts().active(),
            pk=self.kwargs["pk"],
        )

    @extend_schema(
        tags=["reviews"],
        summary="Get an active review",
        responses={200: ReviewReadSerializer, 404: error_response("Review not found.")},
    )
    def get(self, request, pk: int):
        review = self.get_object()
        return Response(ReviewReadSerializer(review).data)

    @extend_schema(
        tags=["reviews"],
        summary="Replace a review",
        description="Soft deletes the old review and creates a replacement in one transaction.",
        request=ReviewWriteSerializer,
        responses={
            200: ReviewReadSerializer,
            400: error_response("Invalid rating or comment."),
            401: error_response("Authentication is required."),
            403: error_response("Only the review author may edit this review."),
            404: error_response("Review not found."),
        },
    )
    def put(self, request, pk: int):
        review = self.get_object()
        self.check_object_permissions(request, review)
        serializer = ReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        replacement = replace_review(review, **serializer.validated_data)
        return Response(ReviewReadSerializer(_review_read(replacement.pk)).data)

    @extend_schema(
        tags=["reviews"],
        summary="Partially replace a review",
        description="Soft deletes the old review and creates a replacement in one transaction.",
        request=ReviewWriteSerializer,
        responses={
            200: ReviewReadSerializer,
            400: error_response("Invalid rating or comment."),
            401: error_response("Authentication is required."),
            403: error_response("Only the review author may edit this review."),
            404: error_response("Review not found."),
        },
    )
    def patch(self, request, pk: int):
        review = self.get_object()
        self.check_object_permissions(request, review)
        serializer = ReviewWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = {
            "rating": serializer.validated_data.get("rating", review.rating),
            "comment": serializer.validated_data.get("comment", review.comment),
        }
        replacement = replace_review(review, **data)
        return Response(ReviewReadSerializer(_review_read(replacement.pk)).data)

    @extend_schema(
        tags=["reviews"],
        summary="Soft delete a review",
        responses={
            204: None,
            401: error_response("Authentication is required."),
            403: error_response("Only the review author may delete this review."),
            404: error_response("Review not found."),
        },
    )
    def delete(self, request, pk: int):
        review = self.get_object()
        self.check_object_permissions(request, review)
        soft_delete_review(review)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReactionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_review(self) -> Review:
        return get_object_or_404(Review.objects.active(), pk=self.kwargs["pk"])

    @extend_schema(
        tags=["reactions"],
        summary="Get the current user's reaction",
        responses={
            200: ReactionStateSerializer,
            401: error_response("Authentication is required."),
            404: error_response("Review not found."),
        },
    )
    def get(self, request, pk: int):
        review = self.get_review()
        reaction = ReviewReaction.objects.filter(review=review, user=request.user).first()
        return Response({"type": reaction.type if reaction else None})

    @extend_schema(
        tags=["reactions"],
        summary="Set or replace the current user's reaction",
        request=ReactionSerializer,
        responses={
            200: ReactionSerializer,
            400: error_response("Reaction type must be like or dislike."),
            401: error_response("Authentication is required."),
            404: error_response("Review not found."),
        },
    )
    def put(self, request, pk: int):
        review = self.get_review()
        serializer = ReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reaction = set_reaction(
            review=review,
            user=request.user,
            reaction_type=serializer.validated_data["type"],
        )
        return Response({"type": reaction.type})

    @extend_schema(
        tags=["reactions"],
        summary="Delete the current user's reaction",
        responses={
            204: None,
            401: error_response("Authentication is required."),
            404: error_response("Review not found."),
        },
    )
    def delete(self, request, pk: int):
        review = self.get_review()
        delete_reaction(review=review, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
