"""
URL patterns for Organizations API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('', views.OrganizationViewSet, basename='organizations')

urlpatterns = [
    path('', include(router.urls)),
]