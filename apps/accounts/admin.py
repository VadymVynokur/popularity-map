from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from apps.accounts.models import User


class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "username", "role")


class AdminUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = AdminUserCreationForm
    form = AdminUserChangeForm
    model = User
    ordering = ("email",)
    list_display = ("email", "username", "role", "email_verified", "is_staff", "is_active")
    search_fields = ("email", "username")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "role",
                    "email_verified",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "role", "password1", "password2"),
            },
        ),
    )
