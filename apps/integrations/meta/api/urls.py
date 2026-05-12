"""URL routes for Meta webhook ingestion."""

from django.urls import path

from .views import MetaWebhookView


app_name = "meta_integration"

urlpatterns = [
    path("", MetaWebhookView.as_view(), name="meta-webhook"),
]
