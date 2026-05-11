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

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Ticket, Message
from . import selectors


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
    ticket_data = {
        'organization_id': organization_id,
        'customer': customer,
        'title': title,
        'channel': channel,
        'priority': priority,
        'status': Ticket.Status.OPEN,
        'sla_due_at': sla_due_at,
        'metadata': kwargs.get('metadata', {}),
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
    
    # Prepare domain event context for future implementation
    event_context = {
        'ticket_id': ticket.id,
        'customer_id': customer.id,
        'organization_id': organization_id,
        'channel': channel,
        'priority': priority,
        'sla_due_at': sla_due_at,
        'assigned_to': ticket.assigned_to_id,
        'created_at': ticket.created_at,
    }
    
    # Future: Emit TicketCreated domain event
    # domain_events.emit('ticket.created', event_context)
    
    # Log business event for audit and debugging
    print(f"Ticket created: #{str(ticket.id)[:8]} for {customer.name} via {channel}")
    
    return ticket


@transaction.atomic
def update_ticket_status(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID,
    new_status: str,
    updated_by: Optional[uuid.UUID] = None,
    reason: Optional[str] = None
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
    
    # Save the ticket
    ticket.save()
    
    # Prepare domain event context
    event_context = {
        'ticket_id': ticket.id,
        'organization_id': organization_id,
        'previous_status': previous_status,
        'new_status': new_status,
        'updated_by': updated_by,
        'reason': reason,
        'updated_at': ticket.updated_at,
        'sla_due_at': ticket.sla_due_at,
    }
    
    # Future: Emit TicketStatusChanged domain event
    # domain_events.emit('ticket.status_changed', event_context)
    
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
    
    # Store previous assignment for event context
    previous_agent_id = ticket.assigned_to_id
    
    # Update assignment
    ticket.assigned_to_id = agent_id
    ticket.save()
    
    # Prepare domain event context
    event_context = {
        'ticket_id': ticket.id,
        'organization_id': organization_id,
        'previous_agent_id': previous_agent_id,
        'new_agent_id': agent_id,
        'assigned_by': assigned_by,
        'assigned_at': ticket.updated_at,
    }
    
    # Future: Emit TicketAssigned domain event
    # domain_events.emit('ticket.assigned', event_context)
    
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
    message_data = {
        'organization_id': organization_id,
        'ticket': ticket,
        'sender_type': sender_type,
        'direction': direction,
        'sender_id': sender_id,
        'content': content,
        'is_internal': is_internal,
        'external_message_id': external_message_id,
        'metadata': kwargs.get('metadata', {}),
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
    
    # Prepare domain event context
    event_context = {
        'message_id': message.id,
        'ticket_id': ticket.id,
        'organization_id': organization_id,
        'sender_type': sender_type,
        'direction': direction,
        'sender_id': sender_id,
        'content': content,
        'is_internal': is_internal,
        'external_message_id': external_message_id,
        'created_at': message.created_at,
        'ticket_state_changed': ticket_state_changed,
        'new_ticket_status': ticket.status if ticket_state_changed else None,
    }
    
    # Future: Emit MessageCreated domain event
    # domain_events.emit('message.created', event_context)
    
    # If ticket state changed, emit additional event
    if ticket_state_changed:
        # Future: Emit TicketStatusChanged domain event
        # domain_events.emit('ticket.status_changed', {
        #     'ticket_id': ticket.id,
        #     'new_status': ticket.status,
        #     'changed_by_message': message.id,
        #     ...
        # })
        pass
    
    print(f"Message added: {sender_type} → #{str(ticket.id)[:8]} ({len(content)} chars)")
    
    return message


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