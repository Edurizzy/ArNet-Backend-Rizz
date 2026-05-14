"""Django admin for Meta integration observability."""

from django.contrib import admin

from .models import ProcessedProviderMessage, RawWebhookEvent


@admin.register(RawWebhookEvent)
class RawWebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "provider",
        "event_type",
        "status",
        "organization",
        "correlation_id",
        "created_at",
        "processed_at",
    ]
    list_filter = ["provider", "event_type", "status", "created_at", "processed_at"]
    search_fields = ["correlation_id", "id", "error_message"]
    readonly_fields = [
        "id",
        "provider",
        "event_type",
        "payload",
        "headers",
        "correlation_id",
        "created_at",
        "updated_at",
        "processed_at",
    ]
    ordering = ["-created_at"]


@admin.register(ProcessedProviderMessage)
class ProcessedProviderMessageAdmin(admin.ModelAdmin):
    list_display = [
        "provider",
        "provider_message_id",
        "organization",
        "correlation_id",
        "processed_at",
    ]
    list_filter = ["provider", "processed_at"]
    search_fields = ["provider_message_id", "correlation_id"]
    readonly_fields = [
        "id",
        "provider",
        "provider_message_id",
        "organization",
        "correlation_id",
        "processed_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-processed_at"]
