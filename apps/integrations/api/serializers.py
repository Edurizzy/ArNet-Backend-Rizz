"""Serializers for connected accounts (no raw secrets on read)."""

from __future__ import annotations

from rest_framework import serializers

from apps.integrations.models import ConnectedAccount, IntegrationProvider


def _mask_tail(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "********"
    return f"********{value[-4:]}"


class ConnectedAccountSerializer(serializers.ModelSerializer):
    """Read/update connected account without exposing full tokens."""

    access_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    refresh_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    access_token_hint = serializers.SerializerMethodField(read_only=True)
    refresh_token_hint = serializers.SerializerMethodField(read_only=True)
    webhook_verify_token_hint = serializers.SerializerMethodField(read_only=True)
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ConnectedAccount
        fields = [
            "id",
            "organization_id",
            "provider",
            "external_id",
            "display_name",
            "settings",
            "webhook_verify_token",
            "webhook_verify_token_hint",
            "is_active",
            "last_sync_at",
            "access_token",
            "refresh_token",
            "access_token_hint",
            "refresh_token_hint",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization_id",
            "created_at",
            "updated_at",
            "access_token_hint",
            "refresh_token_hint",
            "webhook_verify_token_hint",
        ]

    def get_access_token_hint(self, obj: ConnectedAccount) -> str:
        return _mask_tail(obj.access_token) if (obj.access_token or "").strip() else ""

    def get_refresh_token_hint(self, obj: ConnectedAccount) -> str:
        return _mask_tail(obj.refresh_token) if (obj.refresh_token or "").strip() else ""

    def get_webhook_verify_token_hint(self, obj: ConnectedAccount) -> str:
        return _mask_tail(obj.webhook_verify_token)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop("webhook_verify_token", None)
        return data

    def validate_provider(self, value: str) -> str:
        valid = {c[0] for c in IntegrationProvider.choices}
        if value not in valid:
            raise serializers.ValidationError("Unsupported provider.")
        return value

    def update(self, instance, validated_data):
        access_token = validated_data.pop("access_token", serializers.empty)
        refresh_token = validated_data.pop("refresh_token", serializers.empty)
        instance = super().update(instance, validated_data)
        if access_token is not serializers.empty and str(access_token).strip():
            instance.access_token = str(access_token).strip()
        if refresh_token is not serializers.empty:
            instance.refresh_token = str(refresh_token).strip() or None
        if access_token is not serializers.empty or refresh_token is not serializers.empty:
            instance.save(update_fields=["access_token", "refresh_token", "updated_at"])
        return instance
