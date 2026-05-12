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


def build_new_message_event(
    message: Message,
    *,
    correlation_id: Optional[str] = None,
    provider: Optional[str] = None,
    event_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the versioned event emitted when a message is created."""
    ticket = message.ticket

    return _base_event(
        event_type="new_message",
        organization_id=str(message.organization_id),
        correlation_id=correlation_id,
        payload={
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
        },
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
