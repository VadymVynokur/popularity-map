from django.contrib import admin

from apps.notifications.models import EmailDelivery


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "review",
        "recipient",
        "status",
        "attempts",
        "created_at",
        "sent_at",
    )
    list_filter = ("status",)
    search_fields = ("recipient__username", "recipient__email", "review__location__name")
    readonly_fields = ("created_at", "updated_at", "sent_at")
