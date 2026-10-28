from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminRole(BasePermission):
    message = "Administrator role is required."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "admin"
        )


class IsAuthenticatedOrReadOnly(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


class IsOwnerOrAdmin(BasePermission):
    owner_field = "created_by"

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(obj, self.owner_field) == user or getattr(user, "role", None) == "admin"


class IsOwner(BasePermission):
    owner_field = "author"

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(obj, self.owner_field) == request.user
        )
