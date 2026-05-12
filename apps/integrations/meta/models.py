"""
Meta integration persistence models.

Inbound provider payloads are saved as immutable raw events before any domain
mutation. This gives us replay, audit, idempotency, and forensic debugging
without leaking provider-specific structures into Helpdesk.
"""

from django.db import models

from apps.common.models import TenantAwareModel


class RawWebhookEvent(TenantAwareModel):
    """Immutable raw webhook event received from Meta."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    provider = models.CharField(max_length=50, default="meta")
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    headers = models.JSONField(default=dict)
    correlation_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Raw Meta Webhook Event"
        verbose_name_plural = "Raw Meta Webhook Events"
        indexes = [
            models.Index(fields=["correlation_id"], name="meta_raw_corr_idx"),
            models.Index(fields=["status"], name="meta_raw_status_idx"),
            models.Index(fields=["created_at"], name="meta_raw_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_type}:{self.correlation_id}"


class ProcessedProviderMessage(TenantAwareModel):
    """Database-enforced idempotency marker for provider messages."""

    provider = models.CharField(max_length=50)
    provider_message_id = models.CharField(max_length=255, unique=True, db_index=True)
    correlation_id = models.UUIDField(db_index=True)
    processed_at = models.DateTimeField()

    class Meta:
        verbose_name = "Processed Provider Message"
        verbose_name_plural = "Processed Provider Messages"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_message_id"],
                name="meta_unique_provider_message",
            )
        ]
        indexes = [
            models.Index(fields=["provider", "provider_message_id"], name="meta_msg_provider_idx"),
            models.Index(fields=["correlation_id"], name="meta_msg_corr_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_message_id}"


class WhatsAppBusinessAccountConnection(TenantAwareModel):
    """Maps Meta phone numbers to tenant organizations."""

    business_account_id = models.CharField(max_length=255)
    phone_number_id = models.CharField(max_length=255, db_index=True)
    display_phone_number = models.CharField(max_length=50)
    webhook_verify_token = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "WhatsApp Business Account Connection"
        verbose_name_plural = "WhatsApp Business Account Connections"
        indexes = [
            models.Index(fields=["organization"], name="meta_conn_org_idx"),
            models.Index(fields=["phone_number_id"], name="meta_conn_phone_idx"),
            models.Index(fields=["organization", "phone_number_id"], name="meta_conn_org_phone_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.display_phone_number} ({self.phone_number_id})"
