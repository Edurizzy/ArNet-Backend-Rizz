"""
Stable realtime event payload builders for the helpdesk domain.

Consumers must not serialize models directly. Services build these payloads
after domain mutations and broadcast them after the surrounding transaction
commits successfully.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from django.utils import timezone

from .models import Message, Ticket

EVENT_VERSION = 1


def _format_dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _message_payload(
    message: Message,
    *,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    ticket = message.ticket
    return {
        "message": {
            "id": str(message.id),
            "ticket_id": str(message.ticket_id),
            "sender_type": message.sender_type,
            "direction": message.direction,
            "sender_id": str(message.sender_id) if message.sender_id else None,
            "content": message.content,
            "is_internal": message.is_internal,
            "external_message_id": message.external_message_id,
            "metadata": message.metadata,
            "provider": provider,
            "delivery_status": message.delivery_status,
            "provider_message_id": message.provider_message_id,
            "correlation_id": str(message.correlation_id) if message.correlation_id else None,
            "queued_at": _format_dt(message.queued_at),
            "sent_at": _format_dt(message.sent_at),
            "delivered_at": _format_dt(message.delivered_at),
            "failed_at": _format_dt(message.failed_at),
            "created_at": message.created_at.isoformat(),
            "updated_at": message.updated_at.isoformat(),
        },
        "ticket": {
            "id": str(ticket.id),
            "status": ticket.status,
            "priority": ticket.priority,
            "assigned_to_id": str(ticket.assigned_to_id) if ticket.assigned_to_id else None,
            "updated_at": ticket.updated_at.isoformat(),
        },
    }


def build_new_message_event(
    message: Message,
    *,
    correlation_id: Optional[str] = None,
    provider: Optional[str] = None,
    event_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the versioned event emitted when a message is created or delivery changes."""
    payload = _message_payload(message, provider=provider)
    return _base_event(
        event_type="new_message",
        organization_id=str(message.organization_id),
        correlation_id=correlation_id,
        payload=payload,
        provider=provider,
        event_timestamp=event_timestamp,
    )


def build_message_delivery_updated_event(
    message: Message,
    *,
    correlation_id: Optional[str] = None,
    provider: Optional[str] = None,
    event_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Same payload shape as new_message for consistent client handling."""
    return build_new_message_event(
        message,
        correlation_id=correlation_id,
        provider=provider,
        event_timestamp=event_timestamp,
    )


def build_ticket_updated_event(
    ticket: Ticket,
    *,
    correlation_id: Optional[str] = None,
    provider: Optional[str] = None,
    event_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the versioned event emitted when ticket state changes."""
    return _base_event(
        event_type="ticket_updated",
        organization_id=str(ticket.organization_id),
        correlation_id=correlation_id,
        payload={
            "ticket": {
                "id": str(ticket.id),
                "customer_id": str(ticket.customer_id),
                "assigned_to_id": str(ticket.assigned_to_id) if ticket.assigned_to_id else None,
                "title": ticket.title,
                "channel": ticket.channel,
                "status": ticket.status,
                "priority": ticket.priority,
                "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None,
                "metadata": ticket.metadata,
                "provider": provider,
                "created_at": ticket.created_at.isoformat(),
                "updated_at": ticket.updated_at.isoformat(),
            }
        },
        provider=provider,
        event_timestamp=event_timestamp,
    )


def _base_event(
    *,
    event_type: str,
    organization_id: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
    provider: Optional[str] = None,
    event_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "type": event_type,
        "event_version": EVENT_VERSION,
        "timestamp": timezone.now().isoformat(),
        "organization_id": organization_id,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "provider": provider,
        "event_timestamp": event_timestamp,
        "payload": payload,
    }
