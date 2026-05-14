"""Read layer for provider-agnostic connected accounts."""

from __future__ import annotations

import uuid
from typing import Optional

from .models import ConnectedAccount, IntegrationProvider


class ConnectedAccountResolutionError(Exception):
    """Raised when no unique active connected account exists for the query."""


def get_active_connected_account_for_org(
    organization_id: uuid.UUID,
    *,
    provider: str = IntegrationProvider.WHATSAPP_CLOUD,
) -> ConnectedAccount:
    """
    Return the single active connected account for outbound sends.

    Raises:
        ConnectedAccountResolutionError: If zero or multiple active accounts exist.
    """
    qs = ConnectedAccount.objects.filter(
        organization_id=organization_id,
        provider=provider,
        is_active=True,
    ).select_related("organization")
    count = qs.count()
    if count == 0:
        raise ConnectedAccountResolutionError(
            f"No active connected account for organization {organization_id} and provider {provider}"
        )
    if count > 1:
        raise ConnectedAccountResolutionError(
            f"Multiple active connected accounts for organization {organization_id} and provider {provider}; "
            "disambiguation is not implemented"
        )
    return qs.get()


def get_account_by_provider_external_id(
    provider: str,
    external_id: str,
    *,
    active_only: bool = True,
) -> ConnectedAccount:
    """Resolve a connected account by provider routing id (e.g. Meta phone_number_id)."""
    qs = ConnectedAccount.objects.select_related("organization").filter(
        provider=provider,
        external_id=external_id,
    )
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.get()


def get_account_by_webhook_verify_token(
    verify_token: str,
    *,
    provider: Optional[str] = None,
    active_only: bool = True,
) -> ConnectedAccount:
    """Resolve an active account used for Meta (or other) webhook subscription verification."""
    qs = ConnectedAccount.objects.select_related("organization").filter(
        webhook_verify_token=verify_token,
    )
    if provider is not None:
        qs = qs.filter(provider=provider)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.get()
