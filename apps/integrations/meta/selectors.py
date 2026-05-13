"""Read layer for the Meta integration."""

from __future__ import annotations

import uuid
from typing import Optional

from .models import (
    ProcessedProviderMessage,
    RawWebhookEvent,
    WhatsAppBusinessAccountConnection,
)


class MetaWhatsAppConnectionError(Exception):
    """Raised when WhatsApp connection cannot be resolved for an organization."""


def get_active_whatsapp_connection_for_org(
    organization_id: uuid.UUID,
) -> WhatsAppBusinessAccountConnection:
    """
    Return the single active WhatsApp Business connection for outbound sends.

    Raises:
        MetaWhatsAppConnectionError: If zero or multiple active connections exist.
    """
    qs = WhatsAppBusinessAccountConnection.objects.filter(
        organization_id=organization_id,
        is_active=True,
    ).select_related("organization")
    count = qs.count()
    if count == 0:
        raise MetaWhatsAppConnectionError(
            f"No active WhatsApp connection for organization {organization_id}"
        )
    if count > 1:
        raise MetaWhatsAppConnectionError(
            f"Multiple active WhatsApp connections for organization {organization_id}; "
            "disambiguation by ticket is not implemented"
        )
    return qs.get()


def get_connection_by_phone_number_id(phone_number_id: str) -> WhatsAppBusinessAccountConnection:
    """Return the active tenant connection for a Meta phone number ID."""
    return WhatsAppBusinessAccountConnection.objects.select_related("organization").get(
        phone_number_id=phone_number_id,
        is_active=True,
    )


def get_connection_by_verify_token(verify_token: str) -> WhatsAppBusinessAccountConnection:
    """Return the active connection for webhook verification."""
    return WhatsAppBusinessAccountConnection.objects.select_related("organization").get(
        webhook_verify_token=verify_token,
        is_active=True,
    )


def has_processed_provider_message(provider: str, provider_message_id: str) -> bool:
    """Check whether a provider message has already been processed."""
    return ProcessedProviderMessage.objects.filter(
        provider=provider,
        provider_message_id=provider_message_id,
    ).exists()


def get_raw_event(event_id: uuid.UUID, correlation_id: Optional[uuid.UUID] = None) -> RawWebhookEvent:
    """Return a raw webhook event, optionally scoped by correlation ID."""
    queryset = RawWebhookEvent.objects.select_related("organization")
    if correlation_id:
        queryset = queryset.filter(correlation_id=correlation_id)
    return queryset.get(id=event_id)
