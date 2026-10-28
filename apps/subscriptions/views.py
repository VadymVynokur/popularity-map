from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.schema import error_response
from apps.locations.models import Location
from apps.subscriptions.serializers import SubscriptionStateSerializer
from apps.subscriptions.services import (
    activate_subscription,
    deactivate_subscription,
    subscription_state,
)


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_location(self, *, active_only: bool = False) -> Location:
        queryset = Location.objects.all()
        if active_only:
            queryset = queryset.active()
        return get_object_or_404(queryset, pk=self.kwargs["location_id"])

    @extend_schema(
        tags=["subscriptions"],
        summary="Get the current user's subscription state",
        description="Only the current user's state is returned; subscriber lists are private.",
        responses={
            200: SubscriptionStateSerializer,
            401: error_response("Authentication is required."),
            404: error_response("Location not found."),
        },
    )
    def get(self, request, location_id: int):
        location = self.get_location()
        return Response(subscription_state(location=location, user=request.user))

    @extend_schema(
        tags=["subscriptions"],
        summary="Subscribe or reactivate a subscription",
        request=None,
        responses={
            200: SubscriptionStateSerializer,
            401: error_response("Authentication is required."),
            404: error_response("Active location not found."),
        },
    )
    def put(self, request, location_id: int):
        location = self.get_location(active_only=True)
        subscription = activate_subscription(location=location, user=request.user)
        return Response(
            SubscriptionStateSerializer(
                {
                    "location": location.pk,
                    "is_active": subscription.is_active,
                    "created_at": subscription.created_at,
                    "updated_at": subscription.updated_at,
                    "unsubscribed_at": subscription.unsubscribed_at,
                }
            ).data
        )

    @extend_schema(
        tags=["subscriptions"],
        summary="Unsubscribe while keeping the historical row",
        request=None,
        responses={
            204: None,
            401: error_response("Authentication is required."),
            404: error_response("Location not found."),
        },
    )
    def delete(self, request, location_id: int):
        location = self.get_location()
        deactivate_subscription(location=location, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
