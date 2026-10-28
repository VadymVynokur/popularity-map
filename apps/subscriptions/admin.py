from django.contrib import admin

from apps.subscriptions.models import LocationSubscription


@admin.register(LocationSubscription)
class LocationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "user", "is_active", "created_at", "unsubscribed_at")
    list_filter = ("is_active",)
    search_fields = ("location__name", "user__username", "user__email")
