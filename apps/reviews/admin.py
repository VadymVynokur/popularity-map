from django.contrib import admin

from apps.reviews.models import Review, ReviewReaction


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "author", "rating", "deleted_at")
    list_filter = ("rating", "deleted_at")
    search_fields = ("location__name", "author__username", "comment")


@admin.register(ReviewReaction)
class ReviewReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "user", "type")
    list_filter = ("type",)
