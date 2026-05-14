"""URL routes for integrations API."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ConnectedAccountViewSet

router = DefaultRouter()
router.register("connected-accounts", ConnectedAccountViewSet, basename="connected-accounts")

urlpatterns = [
    path("", include(router.urls)),
]
