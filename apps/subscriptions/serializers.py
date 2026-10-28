from rest_framework import serializers


class SubscriptionStateSerializer(serializers.Serializer):
    location = serializers.IntegerField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)
    unsubscribed_at = serializers.DateTimeField(allow_null=True)
