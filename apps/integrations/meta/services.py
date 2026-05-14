"""Service layer for Meta webhook normalization and ingestion."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional, Tuple

import httpx
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.crm import selectors as crm_selectors
from apps.crm import services as crm_services
from apps.helpdesk import selectors as helpdesk_selectors
from apps.helpdesk import services as helpdesk_services
from apps.helpdesk.models import Message, Ticket
from apps.integrations.models import ConnectedAccount

from .events import build_meta_ingestion_context
from .models import ProcessedProviderMessage, RawWebhookEvent
from .selectors import get_connection_by_phone_number_id, get_raw_event
from .utils import MetaMessageData, MetaStatusUpdateData, extract_meta_message_data, extract_meta_status_data

logger = logging.getLogger(__name__)


class MetaGraphAPIError(Exception):
    """Raised when the WhatsApp Cloud API returns an error or an unexpected body."""


def _graph_api_version_for_account(account: ConnectedAccount) -> str:
    settings_payload = account.settings or {}
    raw = settings_payload.get("graph_api_version")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().strip("/")
    return (getattr(settings, "META_GRAPH_API_VERSION", None) or "v19.0").strip().strip("/")


def send_whatsapp_text_message_via_account(account: ConnectedAccount, to: str, body: str) -> str:

    if account.access_token == "MOCK_TOKEN_123":
        import time, uuid
        time.sleep(1)  # Simula a demora da internet indo até o Facebook
        return f"wamid.mock.{uuid.uuid4().hex[:10]}"

    """
    Send a text message via Meta Graph API using DB-backed credentials.

    Returns the provider message id (wamid) from the response.
    """
    from apps.integrations.models import IntegrationProvider

    if account.provider != IntegrationProvider.WHATSAPP_CLOUD:
        raise MetaGraphAPIError("Connected account provider is not WhatsApp Cloud API")
    if not account.is_active:
        raise MetaGraphAPIError("Connected account is inactive")

    token = (account.access_token or "").strip()
    if not token:
        raise MetaGraphAPIError(
            "WhatsApp access token is not configured for this connected account"
        )

    version = _graph_api_version_for_account(account)
    url = f"https://graph.facebook.com/{version}/{account.external_id}/messages"

    payload: Dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        raise MetaGraphAPIError(f"Graph API request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise MetaGraphAPIError(
            f"Graph API returned non-JSON (status {response.status_code})"
        ) from exc

    if response.status_code >= 400:
        err = data.get("error", {})
        msg = err.get("message", response.text)
        raise MetaGraphAPIError(f"Graph API HTTP {response.status_code}: {msg}")

    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise MetaGraphAPIError("Graph API response missing messages[0]")
    first = messages[0]
    if not isinstance(first, dict):
        raise MetaGraphAPIError("Graph API messages[0] is not an object")
    wamid = first.get("id")
    if not wamid or not isinstance(wamid, str):
        raise MetaGraphAPIError("Graph API response missing messages[0].id")
    return wamid


class MetaWebhookProcessingError(Exception):
    """Raised when a Meta webhook event cannot be normalized."""


@transaction.atomic
def persist_raw_webhook_event(
    *,
    payload: dict,
    headers: dict,
    correlation_id: uuid.UUID,
    event_type: str,
) -> RawWebhookEvent:
    """Persist the immutable raw Meta payload before async processing."""
    return RawWebhookEvent.objects.create(
        provider="meta",
        event_type=event_type,
        payload=payload,
        headers=headers,
        correlation_id=correlation_id,
        status=RawWebhookEvent.Status.PENDING,
    )


def process_meta_webhook(event_id: uuid.UUID, correlation_id: uuid.UUID) -> int:
    """
    Normalize a persisted Meta raw event into provider-agnostic Helpdesk records.

    The raw payload has already been persisted by the HTTP gateway. This service
    reads it, extracts supported inbound WhatsApp text messages, enforces
    database-level idempotency, resolves tenant/customer/ticket context, then
    delegates domain mutation to Helpdesk services.
    """
    raw_event = get_raw_event(event_id, correlation_id)
    extracted_messages = extract_meta_message_data(raw_event.payload)
    extracted_statuses = extract_meta_status_data(raw_event.payload)

    logger.info(
        "meta_webhook_normalized",
        extra=build_meta_ingestion_context(
            correlation_id=str(correlation_id),
            event_id=str(event_id),
        )
        | {"message_count": len(extracted_messages), "status_count": len(extracted_statuses)},
    )

    processed_count = 0
    for message_data in extracted_messages:
        if _process_message(raw_event, message_data, correlation_id):
            processed_count += 1

    for status_data in extracted_statuses:
        if _process_status_update(status_data, correlation_id):
            processed_count += 1

    return processed_count


def _process_status_update(
    status_data: MetaStatusUpdateData,
    correlation_id: uuid.UUID,
) -> bool:
    """Apply Meta delivery status to helpdesk message if present."""
    try:
        connection = get_connection_by_phone_number_id(status_data.phone_number_id)
    except ConnectedAccount.DoesNotExist:
        logger.warning(
            "meta_status_unknown_phone_number_id",
            extra={
                "phone_number_id": status_data.phone_number_id,
                "correlation_id": str(correlation_id),
            },
        )
        return False
    organization_id = connection.organization_id
    updated = helpdesk_services.update_message_delivery_from_meta_status(
        organization_id=organization_id,
        provider_message_id=status_data.provider_message_id,
        meta_status=status_data.status,
        status_timestamp=status_data.timestamp,
    )
    if updated:
        logger.info(
            "meta_webhook_status_applied",
            extra=build_meta_ingestion_context(
                correlation_id=str(correlation_id),
                organization_id=str(organization_id),
                provider_message_id=status_data.provider_message_id,
            )
            | {"meta_status": status_data.status},
        )
    return updated


@transaction.atomic
def _process_message(
    raw_event: RawWebhookEvent,
    message_data: MetaMessageData,
    correlation_id: uuid.UUID,
) -> bool:
    connection = get_connection_by_phone_number_id(message_data.phone_number_id)
    organization_id = connection.organization_id

    try:
        ProcessedProviderMessage.objects.create(
            organization_id=organization_id,
            provider="meta",
            provider_message_id=message_data.provider_message_id,
            correlation_id=correlation_id,
            processed_at=timezone.now(),
        )
    except IntegrityError:
        logger.info(
            "meta_webhook_duplicate_message_skipped",
            extra=build_meta_ingestion_context(
                correlation_id=str(correlation_id),
                event_id=str(raw_event.id),
                organization_id=str(organization_id),
                provider_message_id=message_data.provider_message_id,
            ),
        )
        return False

    raw_event.organization_id = organization_id
    raw_event.save(update_fields=["organization", "updated_at"])

    customer = _resolve_customer(
        organization_id=organization_id,
        phone=message_data.sender_phone,
        display_name=message_data.contact_name,
        correlation_id=correlation_id,
        connected_account=connection,
    )
    ticket, ticket_was_created = _resolve_ticket(
        organization_id=organization_id,
        customer_id=customer.id,
        title=message_data.text_body,
        correlation_id=correlation_id,
    )

    helpdesk_services.add_message_to_ticket(
        ticket_id=ticket.id,
        organization_id=organization_id,
        sender_type=Message.SenderType.CUSTOMER,
        direction=Message.Direction.INBOUND,
        sender_id=customer.id,
        content=message_data.text_body,
        external_message_id=message_data.provider_message_id,
        correlation_id=correlation_id,
        source_provider="meta",
        event_timestamp=message_data.timestamp,
        metadata={
            **message_data.metadata,
            "raw_webhook_event_id": str(raw_event.id),
            "phone_number_id": message_data.phone_number_id,
            "provider_message_id": message_data.provider_message_id,
        },
    )

    if ticket_was_created:
        greeting = _connected_account_auto_greeting_text(connection)
        if greeting:
            try:
                helpdesk_services.create_whatsapp_auto_greeting_message(
                    ticket_id=ticket.id,
                    organization_id=organization_id,
                    content=greeting,
                    correlation_id=correlation_id,
                )
            except helpdesk_services.HelpdeskValidationError as exc:
                logger.warning(
                    "whatsapp_auto_greeting_skipped",
                    extra=build_meta_ingestion_context(
                        correlation_id=str(correlation_id),
                        event_id=str(raw_event.id),
                        organization_id=str(organization_id),
                        ticket_id=str(ticket.id),
                    )
                    | {"reason": str(exc)},
                )
            except Exception:
                logger.exception(
                    "whatsapp_auto_greeting_failed",
                    extra=build_meta_ingestion_context(
                        correlation_id=str(correlation_id),
                        event_id=str(raw_event.id),
                        organization_id=str(organization_id),
                        ticket_id=str(ticket.id),
                    ),
                )

    logger.info(
        "meta_webhook_message_processed",
        extra=build_meta_ingestion_context(
            correlation_id=str(correlation_id),
            event_id=str(raw_event.id),
            organization_id=str(organization_id),
            provider_message_id=message_data.provider_message_id,
        ),
    )
    return True


def _auto_create_customers_for_account(account: Optional[ConnectedAccount] = None) -> bool:
    if account is not None:
        payload = account.settings or {}
        if "auto_create_customers" in payload:
            return bool(payload["auto_create_customers"])
    return bool(getattr(settings, "META_AUTO_CREATE_CUSTOMERS", True))


def _resolve_customer(
    *,
    organization_id: uuid.UUID,
    phone: str,
    display_name: Optional[str],
    correlation_id: uuid.UUID,
    connected_account: Optional[ConnectedAccount] = None,
):
    customer = crm_selectors.get_customer_by_phone(phone, organization_id)
    if customer:
        return customer

    if not _auto_create_customers_for_account(connected_account):
        raise MetaWebhookProcessingError(f"Customer not found for WhatsApp phone {phone}")

    normalized_digits = "".join(character for character in phone if character.isdigit())
    document_id = normalized_digits[-20:] or str(correlation_id).replace("-", "")[:20]
    email = f"whatsapp-{document_id}@example.invalid"

    return crm_services.create_customer(
        organization_id=organization_id,
        name=display_name or phone,
        email=email,
        phone=phone,
        document_id=document_id,
        status="lead",
        tags=["whatsapp", "meta"],
    )


def _connected_account_auto_greeting_text(account: ConnectedAccount) -> Optional[str]:
    """
    Return greeting body from ConnectedAccount.settings, or None if disabled / empty.

    Expected keys (aligned with the operational settings UI):
    - auto_greeting_enabled: bool (must be exactly True)
    - auto_greeting_message: non-empty str
    """
    payload = account.settings or {}
    if payload.get("auto_greeting_enabled") is not True:
        return None
    raw = payload.get("auto_greeting_message")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    return text or None


def _resolve_ticket(
    *,
    organization_id: uuid.UUID,
    customer_id: uuid.UUID,
    title: str,
    correlation_id: uuid.UUID,
) -> Tuple[Ticket, bool]:
    """
    Return (ticket, created).

    ``created`` is True only when a new ticket row was created for this inbound
    (no existing open WhatsApp ticket for the customer). Used for first-contact
    auto-greeting without replying on every message.
    """
    ticket = helpdesk_selectors.get_open_ticket_for_customer(
        customer_id=customer_id,
        organization_id=organization_id,
        channel=Ticket.Channel.WHATSAPP,
    )
    if ticket:
        return ticket, False

    ticket = helpdesk_services.create_ticket(
        organization_id=organization_id,
        customer_id=customer_id,
        title=title[:255],
        channel=Ticket.Channel.WHATSAPP,
        priority=Ticket.Priority.MEDIUM,
        correlation_id=correlation_id,
        source_provider="meta",
        metadata={"source_provider": "meta", "correlation_id": str(correlation_id)},
    )
    return ticket, True
