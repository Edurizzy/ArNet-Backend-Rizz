"""Django admin for connected integration accounts (secrets masked)."""

from django.contrib import admin

from .models import ConnectedAccount


def _mask_secret(value: str | None) -> str:
    if not value:
        return "—"
    if len(value) <= 8:
        return "••••••••"
    return f"••••••••{value[-4:]}"


@admin.register(ConnectedAccount)
class ConnectedAccountAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "organization",
        "provider",
        "external_id",
        "display_name",
        "is_active",
        "created_at",
    ]
    list_filter = ["provider", "is_active", "created_at"]
    search_fields = ["external_id", "display_name", "organization__name"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "access_token_masked",
        "refresh_token_masked",
    ]
    ordering = ["organization", "provider", "display_name"]

    fieldsets = (
        (None, {"fields": ("organization", "provider", "external_id", "display_name", "is_active")}),
        (
            "Credentials (leave access token blank on save to keep existing)",
            {
                "fields": (
                    "access_token",
                    "refresh_token",
                    "access_token_masked",
                    "refresh_token_masked",
                    "webhook_verify_token",
                ),
            },
        ),
        ("Settings", {"fields": ("settings", "last_sync_at")}),
        ("Timestamps", {"fields": ("id", "created_at", "updated_at")}),
    )

    def access_token_masked(self, obj: ConnectedAccount) -> str:
        return _mask_secret(obj.access_token)

    access_token_masked.short_description = "Access token (masked)"

    def refresh_token_masked(self, obj: ConnectedAccount) -> str:
        return _mask_secret(obj.refresh_token)

    refresh_token_masked.short_description = "Refresh token (masked)"

    def save_model(self, request, obj, form, change):
        if change:
            prev = ConnectedAccount.objects.get(pk=obj.pk)
            if not (obj.access_token or "").strip():
                obj.access_token = prev.access_token
            if obj.refresh_token is not None and not str(obj.refresh_token).strip():
                obj.refresh_token = prev.refresh_token
        super().save_model(request, obj, form, change)
