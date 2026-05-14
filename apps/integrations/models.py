"""Provider-agnostic connected accounts (channels) per organization."""

from __future__ import annotations

from django.db import models

from apps.common.models import TenantAwareModel


class IntegrationProvider(models.TextChoices):
    WHATSAPP_CLOUD = "whatsapp_cloud", "WhatsApp Cloud API"
    INSTAGRAM = "instagram", "Instagram"
    TELEGRAM = "telegram", "Telegram"
    EMAIL = "email", "Email"
    WEBCHAT = "webchat", "Webchat"
    SMS = "sms", "SMS"
    INTERNAL_AUTOMATION = "internal_automation", "Internal automation"


class ConnectedAccount(TenantAwareModel):
    """
    One logical connection to an external provider for an organization.

    * external_id — provider routing id (e.g. Meta phone_number_id).
    * access_token / refresh_token — never exposed via API serializers or logs.
    """

    provider = models.CharField(max_length=64, choices=IntegrationProvider.choices, db_index=True)
    external_id = models.CharField(max_length=255, db_index=True)
    display_name = models.CharField(max_length=255)
    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, null=True)
    settings = models.JSONField(default=dict, blank=True)
    webhook_verify_token = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Connected account"
        verbose_name_plural = "Connected accounts"
        indexes = [
            models.Index(fields=["organization", "provider", "is_active"], name="integ_conn_org_prov_act_idx"),
            models.Index(fields=["provider", "external_id"], name="integ_conn_prov_ext_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"],
                name="integ_unique_provider_external_id",
            ),
            models.UniqueConstraint(
                fields=["webhook_verify_token"],
                condition=models.Q(is_active=True),
                name="integ_unique_active_webhook_verify_token",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_provider_display()} — {self.display_name} ({self.external_id})"
