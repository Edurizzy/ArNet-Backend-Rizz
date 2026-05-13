"""
Helpdesk Services (Event-Driven Write Operations & Business Logic) for ArNet Platform.

Services handle ALL write operations and business logic for the helpdesk domain with
special focus on event-driven architecture preparation.

Key Principles:
1. ALL write operations use @transaction.atomic for data consistency
2. Prepare for future domain events (websockets, AI, automation)
3. Handle complex business rules (SLA, status transitions, assignments)
4. Maintain audit trails and operational context
5. Enable real-time system integration

This module is designed to be the source of domain events for:
- Real-time WebSocket notifications
- AI agent triggers and automation
- Customer notification delivery
- SLA monitoring and escalation
- Analytics and reporting events
- Audit logging and compliance

Future Architecture:
Each service function is structured to easily emit domain events
when the event-driven infrastructure is implemented.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Ticket, Message
from . import selectors
from .events import (
    build_message_delivery_updated_event,
    build_new_message_event,
    build_ticket_updated_event,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class HelpdeskValidationError(ValidationError):
    """Custom exception for helpdesk-specific validation errors."""
    pass


class TicketTransitionError(HelpdeskValidationError):
    """Exception for invalid ticket status transitions."""
    pass


class AssignmentError(HelpdeskValidationError):
    """Exception for ticket assignment validation errors."""
    pass


# =============================================================================
# TICKET SERVICES
# =============================================================================

@transaction.atomic
def create_ticket(
    organization_id: uuid.UUID,
    customer_id: uuid.UUID,
    title: str,
    channel: str,
    priority: str = Ticket.Priority.MEDIUM,
    correlation_id: Optional[uuid.UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
    source_provider: Optional[str] = None,
    **kwargs
) -> Ticket:
    """
    Create a new support ticket with full business logic and event preparation.
    
    This service handles the complete ticket creation workflow:
    1. Validate customer and business rules
    2. Calculate SLA due date based on priority
    3. Create ticket with audit context
    4. Prepare for future domain event emission
    
    Args:
        organization_id: UUID of the organization (tenant context)
        customer_id: UUID of the customer creating the ticket
        title: Brief description of the issue
        channel: Communication channel ('whatsapp', 'email', etc.)
        priority: Ticket priority (defaults to 'medium')
        **kwargs: Additional ticket data (metadata, assigned_to, etc.)
    
    Returns:
        Created Ticket instance
        
    Raises:
        HelpdeskValidationError: If validation fails
        
    Future Domain Events:
        - TicketCreated: WebSocket notification to agents
        - SLAScheduled: SLA monitoring system trigger
        - CustomerNotified: Customer confirmation message
        - AIAgentTriggered: AI agent analysis and auto-assignment
    """
    
    # Validate customer exists and belongs to organization
    from apps.crm.selectors import get_customer
    try:
        customer = get_customer(customer_id, organization_id)
    except Exception:
        raise HelpdeskValidationError(
            f"Customer {customer_id} not found for organization {organization_id}"
        )
    
    # Validate required fields
    if not title or not title.strip():
        raise HelpdeskValidationError("Ticket title is required")
    
    title = title.strip()
    if len(title) < 3:
        raise HelpdeskValidationError("Ticket title must be at least 3 characters")
    
    # Validate channel
    if channel not in [choice[0] for choice in Ticket.Channel.choices]:
        raise HelpdeskValidationError(f"Invalid channel: {channel}")
    
    # Validate priority
    if priority not in [choice[0] for choice in Ticket.Priority.choices]:
        raise HelpdeskValidationError(f"Invalid priority: {priority}")
    
    # Calculate SLA due date based on priority
    sla_due_at = _calculate_sla_due_date(priority)
    
    # Prepare ticket data
    ticket_metadata = metadata or kwargs.get('metadata', {}) or {}
    if correlation_id:
        ticket_metadata.setdefault('correlation_id', str(correlation_id))
    if source_provider:
        ticket_metadata.setdefault('source_provider', source_provider)

    ticket_data = {
        'organization_id': organization_id,
        'customer': customer,
        'title': title,
        'channel': channel,
        'priority': priority,
        'status': Ticket.Status.OPEN,
        'sla_due_at': sla_due_at,
        'metadata': ticket_metadata,
    }
    
    # Handle initial assignment if provided
    if 'assigned_to' in kwargs and kwargs['assigned_to']:
        # Validate agent belongs to organization
        agent_id = kwargs['assigned_to']
        if not _validate_agent_belongs_to_org(agent_id, organization_id):
            raise AssignmentError(
                f"Agent {agent_id} does not belong to organization {organization_id}"
            )
        ticket_data['assigned_to_id'] = agent_id
    
    # Create the ticket
    ticket = Ticket.objects.create(**ticket_data)
    
    event = build_ticket_updated_event(
        ticket,
        correlation_id=str(correlation_id) if correlation_id else None,
        provider=source_provider,
    )
    transaction.on_commit(lambda: _broadcast_realtime_event(organization_id, event))
    
    # Log business event for audit and debugging
    print(f"Ticket created: #{str(ticket.id)[:8]} for {customer.name} via {channel}")
    
    return ticket


@transaction.atomic
def update_ticket_status(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID,
    new_status: str,
    updated_by: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
    correlation_id: Optional[uuid.UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
    source_provider: Optional[str] = None,
) -> Ticket:
    """
    Update ticket status with business rule validation and audit context.
    
    This service handles status transitions with:
    1. Status transition validation
    2. SLA impact calculation
    3. Assignment rule evaluation
    4. Audit trail preparation
    
    Args:
        ticket_id: UUID of the ticket to update
        organization_id: UUID of the organization
        new_status: New status to set
        updated_by: UUID of user making the change (for audit)
        reason: Optional reason for status change
        
    Returns:
        Updated Ticket instance
        
    Raises:
        TicketTransitionError: If status transition is invalid
        
    Future Domain Events:
        - TicketStatusChanged: WebSocket notification
        - SLAUpdated: SLA monitoring system update
        - CustomerNotified: Status change notification
        - AIAgentTriggered: AI analysis for next actions
    """
    
    # Get ticket with lock to prevent concurrent modifications
    ticket = selectors.get_ticket_for_update(ticket_id, organization_id)
    
    # Validate status transition
    if not _is_valid_status_transition(ticket.status, new_status):
        raise TicketTransitionError(
            f"Invalid status transition from '{ticket.status}' to '{new_status}'"
        )
    
    # Store previous state for event context
    previous_status = ticket.status
    
    # Update ticket status
    ticket.status = new_status
    
    # Handle status-specific business logic
    if new_status == Ticket.Status.RESOLVED:
        # When resolving, update SLA if not already breached
        if ticket.sla_due_at and timezone.now() <= ticket.sla_due_at:
            # Mark as resolved within SLA
            if 'sla_met' not in ticket.metadata:
                ticket.metadata = ticket.metadata or {}
                ticket.metadata['sla_met'] = True
    
    elif new_status == Ticket.Status.CLOSED:
        # When closing, record closure metadata
        ticket.metadata = ticket.metadata or {}
        ticket.metadata.update({
            'closed_at': timezone.now().isoformat(),
            'closed_by': str(updated_by) if updated_by else None,
            'closure_reason': reason,
        })
    
    elif new_status == Ticket.Status.OPEN and previous_status in [Ticket.Status.RESOLVED, Ticket.Status.CLOSED]:
        # Reopening ticket - recalculate SLA
        ticket.sla_due_at = _calculate_sla_due_date(ticket.priority)
        ticket.metadata = ticket.metadata or {}
        ticket.metadata['reopened_at'] = timezone.now().isoformat()
    
    if metadata:
        ticket.metadata = ticket.metadata or {}
        ticket.metadata.update(metadata)
    if correlation_id:
        ticket.metadata = ticket.metadata or {}
        ticket.metadata['correlation_id'] = str(correlation_id)
    if source_provider:
        ticket.metadata = ticket.metadata or {}
        ticket.metadata['source_provider'] = source_provider
    
    # Save the ticket
    ticket.save()
    
    event = build_ticket_updated_event(
        ticket,
        correlation_id=str(correlation_id) if correlation_id else None,
        provider=source_provider,
    )
    transaction.on_commit(lambda: _broadcast_realtime_event(organization_id, event))
    
    print(f"Ticket status updated: #{str(ticket.id)[:8]} {previous_status} → {new_status}")
    
    return ticket


@transaction.atomic
def assign_ticket(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    assigned_by: Optional[uuid.UUID] = None
) -> Ticket:
    """
    Assign ticket to an agent with validation and workload consideration.
    
    Args:
        ticket_id: UUID of the ticket to assign
        organization_id: UUID of the organization
        agent_id: UUID of the agent to assign to
        assigned_by: UUID of user making the assignment (for audit)
        
    Returns:
        Updated Ticket instance
        
    Raises:
        AssignmentError: If assignment validation fails
        
    Future Domain Events:
        - TicketAssigned: WebSocket notification to agent
        - WorkloadUpdated: Agent workload tracking
        - CustomerNotified: Assignment notification
    """
    
    # Get ticket with lock
    ticket = selectors.get_ticket_for_update(ticket_id, organization_id)
    
    # Validate agent belongs to organization
    if not _validate_agent_belongs_to_org(agent_id, organization_id):
        raise AssignmentError(
            f"Agent {agent_id} does not belong to organization {organization_id}"
        )
    
    # Update assignment
    ticket.assigned_to_id = agent_id
    ticket.save()
    
    event = build_ticket_updated_event(ticket)
    transaction.on_commit(lambda: _broadcast_realtime_event(organization_id, event))
    
    print(f"Ticket assigned: #{str(ticket.id)[:8]} to agent {str(agent_id)[:8]}")
    
    return ticket


# =============================================================================
# MESSAGE SERVICES
# =============================================================================

@transaction.atomic
def add_message_to_ticket(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID,
    sender_type: str,
    content: str,
    direction: str = Message.Direction.INBOUND,
    sender_id: Optional[uuid.UUID] = None,
    is_internal: bool = False,
    external_message_id: Optional[str] = None,
    correlation_id: Optional[uuid.UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
    source_provider: Optional[str] = None,
    event_timestamp: Optional[str] = None,
    **kwargs
) -> Message:
    """
    Add a message to a ticket with comprehensive business logic.
    
    This is the core operational function that handles all message creation:
    1. Ticket state evaluation and updates
    2. SLA impact assessment
    3. Auto-response triggers preparation
    4. Real-time notification preparation
    
    Args:
        ticket_id: UUID of the ticket
        organization_id: UUID of the organization
        sender_type: Type of sender ('customer', 'agent', 'system', 'ai_agent')
        content: Message content
        direction: Message direction ('inbound', 'outbound')
        sender_id: UUID of the sender (optional)
        is_internal: Whether message is internal note
        external_message_id: ID from external platform (for deduplication)
        **kwargs: Additional message metadata
        
    Returns:
        Created Message instance
        
    Raises:
        HelpdeskValidationError: If validation fails
        
    Future Domain Events:
        - MessageCreated: WebSocket broadcast to conversation participants
        - TicketUpdated: Ticket state change notification
        - AIAgentTriggered: AI analysis and auto-response
        - CustomerNotified: External platform message delivery
        - SLAEvaluated: SLA status update
    """
    
    # Validate message content
    if not content or not content.strip():
        raise HelpdeskValidationError("Message content is required")
    
    content = content.strip()
    
    # Validate sender type
    if sender_type not in [choice[0] for choice in Message.SenderType.choices]:
        raise HelpdeskValidationError(f"Invalid sender type: {sender_type}")
    
    # Validate direction
    if direction not in [choice[0] for choice in Message.Direction.choices]:
        raise HelpdeskValidationError(f"Invalid direction: {direction}")
    
    # Check for duplicate external message (webhook deduplication)
    if external_message_id:
        existing_message = selectors.get_message_by_external_id(
            external_message_id, organization_id
        )
        if existing_message:
            print(f"Duplicate message prevented: {external_message_id}")
            return existing_message
    
    # Get ticket with lock for state updates
    ticket = selectors.get_ticket_for_update(ticket_id, organization_id)
    
    # Prepare message data
    message_metadata = metadata or kwargs.get('metadata', {}) or {}
    if correlation_id:
        message_metadata.setdefault('correlation_id', str(correlation_id))
    if source_provider:
        message_metadata.setdefault('source_provider', source_provider)
    if event_timestamp:
        message_metadata.setdefault('provider_event_timestamp', event_timestamp)

    message_data = {
        'organization_id': organization_id,
        'ticket': ticket,
        'sender_type': sender_type,
        'direction': direction,
        'sender_id': sender_id,
        'content': content,
        'is_internal': is_internal,
        'external_message_id': external_message_id,
        'metadata': message_metadata,
    }
    
    # Create the message
    message = Message.objects.create(**message_data)
    
    # CRITICAL: Update ticket's updated_at timestamp
    # This ensures ticket appears at top of agent dashboards
    ticket.save()  # This updates the updated_at field automatically
    
    # Evaluate ticket state changes based on message
    ticket_state_changed = False
    
    # Business Rule: Customer messages may reopen resolved tickets
    if (sender_type == Message.SenderType.CUSTOMER and 
        direction == Message.Direction.INBOUND and 
        ticket.status == Ticket.Status.RESOLVED):
        
        # Reopen ticket when customer replies to resolved ticket
        ticket.status = Ticket.Status.OPEN
        ticket.sla_due_at = _calculate_sla_due_date(ticket.priority)
        ticket.save()
        ticket_state_changed = True
        
        print(f"Ticket reopened by customer message: #{str(ticket.id)[:8]}")
    
    # Business Rule: Agent responses may change status from pending
    elif (sender_type == Message.SenderType.AGENT and 
          direction == Message.Direction.OUTBOUND and 
          ticket.status == Ticket.Status.PENDING):
        
        # Agent responded to pending ticket - keep it open for customer response
        ticket.status = Ticket.Status.OPEN
        ticket.save()
        ticket_state_changed = True
        
        print(f"Ticket status changed to open by agent response: #{str(ticket.id)[:8]}")
    
    new_message_event = build_new_message_event(
        message,
        correlation_id=str(correlation_id) if correlation_id else None,
        provider=source_provider,
        event_timestamp=event_timestamp,
    )
    transaction.on_commit(lambda: _broadcast_realtime_event(organization_id, new_message_event))

    if ticket_state_changed:
        ticket_updated_event = build_ticket_updated_event(
            ticket,
            correlation_id=str(correlation_id) if correlation_id else None,
            provider=source_provider,
            event_timestamp=event_timestamp,
        )
        transaction.on_commit(lambda: _broadcast_realtime_event(organization_id, ticket_updated_event))
    
    print(f"Message added: {sender_type} → #{str(ticket.id)[:8]} ({len(content)} chars)")
    
    return message


# =============================================================================
# OUTBOUND WHATSAPP (META) PIPELINE
# =============================================================================


def _outbound_success_rank(status: Optional[str]) -> int:
    if not status:
        return 0
    order: Dict[str, int] = {
        Message.DeliveryStatus.PENDING: 10,
        Message.DeliveryStatus.QUEUED: 20,
        Message.DeliveryStatus.SENDING: 30,
        Message.DeliveryStatus.SENT: 40,
        Message.DeliveryStatus.DELIVERED: 50,
    }
    return order.get(status, 0)


def broadcast_helpdesk_message_event(
    organization_id: uuid.UUID,
    message: Message,
    *,
    correlation_id: Optional[uuid.UUID] = None,
    provider: Optional[str] = "meta",
    event_timestamp: Optional[str] = None,
) -> None:
    """Emit new_message-shaped WebSocket event (post-commit or from Celery)."""
    event = build_message_delivery_updated_event(
        message,
        correlation_id=str(correlation_id) if correlation_id else None,
        provider=provider,
        event_timestamp=event_timestamp,
    )
    _broadcast_realtime_event(organization_id, event)


def normalize_whatsapp_to_number(phone: str) -> str:
    cleaned = (phone or "").strip()
    if not cleaned:
        raise HelpdeskValidationError("Customer phone is required for WhatsApp outbound")
    if cleaned.startswith("+"):
        return "".join(character for character in cleaned if character not in " \t")
    digits = "".join(character for character in cleaned if character.isdigit())
    if not digits:
        raise HelpdeskValidationError("Customer phone is invalid for WhatsApp outbound")
    return f"+{digits}"


@transaction.atomic
def create_outbound_message(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID,
    agent_user_id: uuid.UUID,
    content: str,
    correlation_id: Optional[uuid.UUID] = None,
) -> Message:
    """
    Create an outbound WhatsApp message: persist as queued, enqueue Celery after commit.

    Meta API is never called inside this transaction.
    """
    if not content or not content.strip():
        raise HelpdeskValidationError("Message content is required")

    content = content.strip()
    correlation = correlation_id or uuid.uuid4()

    ticket = selectors.get_ticket_for_update(ticket_id, organization_id)
    if ticket.channel != Ticket.Channel.WHATSAPP:
        raise HelpdeskValidationError("Outbound messaging is only available for WhatsApp tickets")

    normalize_whatsapp_to_number(ticket.customer.phone or "")

    if not _validate_agent_belongs_to_org(agent_user_id, organization_id):
        raise HelpdeskValidationError(
            f"Agent {agent_user_id} does not belong to organization {organization_id}"
        )

    now = timezone.now()
    message = Message.objects.create(
        organization_id=organization_id,
        ticket=ticket,
        sender_type=Message.SenderType.AGENT,
        direction=Message.Direction.OUTBOUND,
        sender_id=agent_user_id,
        content=content,
        is_internal=False,
        delivery_status=Message.DeliveryStatus.QUEUED,
        queued_at=now,
        correlation_id=correlation,
        metadata={"correlation_id": str(correlation)},
    )

    ticket.save()

    ticket_state_changed = False
    if (
        ticket.status == Ticket.Status.PENDING
    ):
        ticket.status = Ticket.Status.OPEN
        ticket.save()
        ticket_state_changed = True

    new_message_event = build_new_message_event(
        message,
        correlation_id=str(correlation),
        provider="meta",
    )
    transaction.on_commit(
        lambda: _broadcast_realtime_event(organization_id, new_message_event)
    )

    if ticket_state_changed:
        ticket_updated_event = build_ticket_updated_event(
            ticket,
            correlation_id=str(correlation),
            provider="meta",
        )
        transaction.on_commit(
            lambda: _broadcast_realtime_event(organization_id, ticket_updated_event)
        )

    def _enqueue_outbound() -> None:
        from apps.integrations.meta.tasks import send_outbound_message_task

        send_outbound_message_task.delay(str(message.id), str(correlation))

    transaction.on_commit(_enqueue_outbound)

    return message


@transaction.atomic
def start_outbound_message_send(message_id: uuid.UUID, organization_id: uuid.UUID) -> Message:
    """
    Transition queued -> sending under row lock.

    If the row is already ``sending`` without a provider id (worker died mid-flight),
    the same state is returned so a retry can still invoke the Graph API once.
    """
    message = selectors.get_message_for_outbound_send(message_id, organization_id)
    if message.provider_message_id:
        return message
    if message.delivery_status in (
        Message.DeliveryStatus.FAILED,
        Message.DeliveryStatus.SENT,
        Message.DeliveryStatus.DELIVERED,
    ):
        return message
    if message.delivery_status == Message.DeliveryStatus.QUEUED:
        message.delivery_status = Message.DeliveryStatus.SENDING
        message.save(update_fields=["delivery_status", "updated_at"])
    elif message.delivery_status != Message.DeliveryStatus.SENDING:
        return message
    return message


@transaction.atomic
def finalize_outbound_message_sent(
    message_id: uuid.UUID,
    organization_id: uuid.UUID,
    provider_message_id: str,
) -> Message:
    """Persist wamid and sent (or noop if webhook advanced state first)."""
    message = selectors.get_message_for_outbound_send(message_id, organization_id)
    if message.provider_message_id:
        return message
    if message.delivery_status == Message.DeliveryStatus.FAILED:
        return message

    current_rank = _outbound_success_rank(message.delivery_status)
    delivered_rank = _outbound_success_rank(Message.DeliveryStatus.DELIVERED)

    if current_rank >= delivered_rank:
        message.provider_message_id = provider_message_id
        message.save(update_fields=["provider_message_id", "updated_at"])
        return message

    now = timezone.now()
    message.provider_message_id = provider_message_id
    message.delivery_status = Message.DeliveryStatus.SENT
    message.sent_at = now
    message.save(
        update_fields=[
            "provider_message_id",
            "delivery_status",
            "sent_at",
            "updated_at",
        ]
    )
    return message


@transaction.atomic
def finalize_outbound_message_failed(
    message_id: uuid.UUID,
    organization_id: uuid.UUID,
    error_message: str,
) -> Message:
    """Mark message failed unless already delivered or already sent with wamid."""
    message = selectors.get_message_for_outbound_send(message_id, organization_id)
    if message.provider_message_id:
        return message
    if _outbound_success_rank(message.delivery_status) >= _outbound_success_rank(
        Message.DeliveryStatus.DELIVERED
    ):
        return message

    meta = dict(message.metadata or {})
    meta["outbound_last_error"] = error_message[:2000]
    message.metadata = meta
    message.delivery_status = Message.DeliveryStatus.FAILED
    message.failed_at = timezone.now()
    message.save(
        update_fields=["metadata", "delivery_status", "failed_at", "updated_at"]
    )
    return message


@transaction.atomic
def update_message_delivery_from_meta_status(
    organization_id: uuid.UUID,
    provider_message_id: str,
    meta_status: str,
    *,
    status_timestamp: Optional[str] = None,
) -> bool:
    """
    Apply Meta message status webhook (sent / delivered / failed / read).

    Returns True if a message row was updated or metadata was touched.
    """
    if not provider_message_id:
        return False

    key = (meta_status or "").lower()
    if key == "read":
        message = selectors.get_message_by_provider_message_id(
            provider_message_id, organization_id
        )
        if not message:
            return False
        locked = Message.objects.select_for_update(of=("self",)).get(pk=message.pk)
        meta = dict(locked.metadata or {})
        meta["meta_read_receipt_at"] = status_timestamp
        locked.metadata = meta
        locked.save(update_fields=["metadata", "updated_at"])
        cid = locked.correlation_id
        oid = organization_id
        mid = locked.id

        def _broadcast_read() -> None:
            refreshed = Message.objects.get(pk=mid)
            broadcast_helpdesk_message_event(
                oid,
                refreshed,
                correlation_id=cid,
                provider="meta",
                event_timestamp=status_timestamp,
            )

        transaction.on_commit(_broadcast_read)
        return True

    target_map = {
        "sent": Message.DeliveryStatus.SENT,
        "delivered": Message.DeliveryStatus.DELIVERED,
        "failed": Message.DeliveryStatus.FAILED,
    }
    if key not in target_map:
        return False
    target = target_map[key]

    try:
        message = Message.objects.select_for_update(of=("self",)).select_related(
            "ticket"
        ).get(
            provider_message_id=provider_message_id,
            organization_id=organization_id,
        )
    except Message.DoesNotExist:
        logger.info(
            "meta_status_no_message_yet",
            extra={
                "provider_message_id": provider_message_id,
                "organization_id": str(organization_id),
                "meta_status": key,
            },
        )
        return False

    if key == "failed":
        if _outbound_success_rank(message.delivery_status) >= _outbound_success_rank(
            Message.DeliveryStatus.DELIVERED
        ):
            return False
        meta = dict(message.metadata or {})
        meta["meta_failed_at"] = status_timestamp
        message.metadata = meta
        message.delivery_status = Message.DeliveryStatus.FAILED
        message.failed_at = timezone.now()
        message.save(
            update_fields=["metadata", "delivery_status", "failed_at", "updated_at"]
        )
        oid = organization_id
        mid = message.id
        cid = message.correlation_id

        def _broadcast_failed() -> None:
            refreshed = Message.objects.get(pk=mid)
            broadcast_helpdesk_message_event(
                oid,
                refreshed,
                correlation_id=cid,
                provider="meta",
                event_timestamp=status_timestamp,
            )

        transaction.on_commit(_broadcast_failed)
        return True

    if _outbound_success_rank(message.delivery_status) >= _outbound_success_rank(target):
        return False

    now = timezone.now()
    message.delivery_status = target
    if target == Message.DeliveryStatus.SENT:
        message.sent_at = message.sent_at or now
    if target == Message.DeliveryStatus.DELIVERED:
        message.delivered_at = now
        message.sent_at = message.sent_at or now
    message.save(
        update_fields=["delivery_status", "sent_at", "delivered_at", "updated_at"]
    )
    oid = organization_id
    mid = message.id
    cid = message.correlation_id

    def _broadcast_delivery() -> None:
        refreshed = Message.objects.get(pk=mid)
        broadcast_helpdesk_message_event(
            oid,
            refreshed,
            correlation_id=cid,
            provider="meta",
            event_timestamp=status_timestamp,
        )

    transaction.on_commit(_broadcast_delivery)
    return True


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@transaction.atomic
def bulk_assign_tickets(
    ticket_ids: List[uuid.UUID],
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    assigned_by: Optional[uuid.UUID] = None
) -> List[Ticket]:
    """
    Assign multiple tickets to an agent in a single transaction.
    
    Useful for workload distribution and bulk operations.
    
    Args:
        ticket_ids: List of ticket UUIDs to assign
        organization_id: UUID of the organization
        agent_id: UUID of the agent to assign to
        assigned_by: UUID of user making the assignments
        
    Returns:
        List of updated Ticket instances
        
    Raises:
        AssignmentError: If validation fails
    """
    if not ticket_ids:
        return []
    
    # Validate agent belongs to organization
    if not _validate_agent_belongs_to_org(agent_id, organization_id):
        raise AssignmentError(
            f"Agent {agent_id} does not belong to organization {organization_id}"
        )
    
    updated_tickets = []
    
    # Process each ticket with proper locking
    for ticket_id in ticket_ids:
        try:
            ticket = selectors.get_ticket_for_update(ticket_id, organization_id)
            ticket.assigned_to_id = agent_id
            ticket.save()
            updated_tickets.append(ticket)
        except Ticket.DoesNotExist:
            print(f"Warning: Ticket {ticket_id} not found, skipping")
            continue
    
    print(f"Bulk assigned {len(updated_tickets)} tickets to agent {str(agent_id)[:8]}")
    
    return updated_tickets


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _calculate_sla_due_date(priority: str) -> datetime:
    """
    Calculate SLA due date based on ticket priority.
    
    Business Rules:
    - Urgent: 1 hour
    - High: 4 hours  
    - Medium: 24 hours
    - Low: 48 hours
    """
    now = timezone.now()
    
    if priority == Ticket.Priority.URGENT:
        return now + timedelta(hours=1)
    elif priority == Ticket.Priority.HIGH:
        return now + timedelta(hours=4)
    elif priority == Ticket.Priority.MEDIUM:
        return now + timedelta(hours=24)
    else:  # LOW
        return now + timedelta(hours=48)


def _is_valid_status_transition(current_status: str, new_status: str) -> bool:
    """
    Validate if a status transition is allowed.
    
    Business Rules:
    - Any status can go to any other status (flexible workflow)
    - Could be made more restrictive based on business requirements
    """
    # For now, allow all transitions (flexible workflow)
    # Future: Add more restrictive business rules if needed
    return True


def _validate_agent_belongs_to_org(agent_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
    """
    Validate that an agent belongs to the organization.
    
    Args:
        agent_id: UUID of the agent
        organization_id: UUID of the organization
        
    Returns:
        True if agent belongs to organization, False otherwise
    """
    from apps.iam.models import User
    
    try:
        User.objects.get(
            id=agent_id,
            organization_id=organization_id
        )
        return True
    except User.DoesNotExist:
        return False


def _broadcast_realtime_event(organization_id: uuid.UUID, event: Dict[str, Any]) -> None:
    """
    Broadcast an already-built realtime event to the tenant-scoped group.

    This function is intentionally small and side-effect focused. It is called
    only from transaction.on_commit callbacks, so frontend clients never receive
    events for writes that were rolled back.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        _organization_events_group_name(organization_id),
        event,
    )


def _organization_events_group_name(organization_id: uuid.UUID) -> str:
    return f"org_{organization_id}_events"