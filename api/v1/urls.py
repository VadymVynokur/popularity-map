from django.conf import settings
from django.http import Http404
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.views import (
    CsrfView,
    EmailConfirmView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    ResendConfirmationView,
)
from apps.categories.views import CategoryDetailView, CategoryListCreateView
from apps.locations.views import (
    DeletedLocationListView,
    LocationDetailView,
    LocationExportView,
    LocationListCreateView,
    LocationRestoreView,
)
from apps.reviews.views import ReactionView, ReviewDetailView, ReviewListCreateView
from apps.subscriptions.views import SubscriptionView


def _docs_view(view):
    def wrapped(request, *args, **kwargs):
        if not settings.API_DOCS_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped


urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/email/confirm/", EmailConfirmView.as_view(), name="auth-email-confirm"),
    path("auth/email/resend/", ResendConfirmationView.as_view(), name="auth-email-resend"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/password/reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "auth/password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("categories/", CategoryListCreateView.as_view(), name="category-list"),
    path("categories/<int:pk>/", CategoryDetailView.as_view(), name="category-detail"),
    path("locations/", LocationListCreateView.as_view(), name="location-list"),
    path("locations/deleted/", DeletedLocationListView.as_view(), name="location-deleted-list"),
    path("locations/export/", LocationExportView.as_view(), name="location-export"),
    path("locations/<int:pk>/", LocationDetailView.as_view(), name="location-detail"),
    path("locations/<int:pk>/restore/", LocationRestoreView.as_view(), name="location-restore"),
    path(
        "locations/<int:location_id>/reviews/",
        ReviewListCreateView.as_view(),
        name="location-review-list",
    ),
    path(
        "locations/<int:location_id>/subscription/",
        SubscriptionView.as_view(),
        name="location-subscription",
    ),
    path("reviews/<int:pk>/", ReviewDetailView.as_view(), name="review-detail"),
    path("reviews/<int:pk>/reaction/", ReactionView.as_view(), name="review-reaction"),
    path("schema/", _docs_view(SpectacularAPIView.as_view()), name="schema"),
    path(
        "docs/",
        _docs_view(SpectacularSwaggerView.as_view(url_name="schema")),
        name="swagger-ui",
    ),
]
