"""Read layer for the Meta integration (delegates to provider-agnostic selectors)."""

from __future__ import annotations

import uuid
from typing import Optional

from apps.integrations.models import ConnectedAccount, IntegrationProvider
from apps.integrations.selectors import (
    ConnectedAccountResolutionError,
    get_account_by_provider_external_id,
    get_account_by_webhook_verify_token,
    get_active_connected_account_for_org,
)


class MetaWhatsAppConnectionError(Exception):
    """Raised when WhatsApp channel cannot be resolved for an organization."""


def get_active_whatsapp_connection_for_org(
    organization_id: uuid.UUID,
) -> ConnectedAccount:
    """
    Return the single active WhatsApp Cloud connected account for outbound sends.

    Raises:
        MetaWhatsAppConnectionError: If zero or multiple active connections exist.
    """
    try:
        return get_active_connected_account_for_org(
            organization_id,
            provider=IntegrationProvider.WHATSAPP_CLOUD,
        )
    except ConnectedAccountResolutionError as exc:
        raise MetaWhatsAppConnectionError(str(exc)) from exc


def get_connection_by_phone_number_id(phone_number_id: str) -> ConnectedAccount:
    """Return the active tenant connection for a Meta phone number ID."""
    return get_account_by_provider_external_id(
        IntegrationProvider.WHATSAPP_CLOUD,
        phone_number_id,
        active_only=True,
    )


def get_connection_by_verify_token(verify_token: str) -> ConnectedAccount:
    """Return the active connection for webhook verification."""
    return get_account_by_webhook_verify_token(
        verify_token,
        provider=IntegrationProvider.WHATSAPP_CLOUD,
        active_only=True,
    )


def has_processed_provider_message(provider: str, provider_message_id: str) -> bool:
    """Check whether a provider message has already been processed."""
    from .models import ProcessedProviderMessage

    return ProcessedProviderMessage.objects.filter(
        provider=provider,
        provider_message_id=provider_message_id,
    ).exists()


def get_raw_event(event_id: uuid.UUID, correlation_id: Optional[uuid.UUID] = None):
    """Return a raw webhook event, optionally scoped by correlation ID."""
    from .models import RawWebhookEvent

    queryset = RawWebhookEvent.objects.select_related("organization")
    if correlation_id:
        queryset = queryset.filter(correlation_id=correlation_id)
    return queryset.get(id=event_id)
