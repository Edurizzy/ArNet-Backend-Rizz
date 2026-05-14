"""
Helpdesk Selectors (Optimized Read Operations) for ArNet Platform.

Selectors handle ALL read operations for the helpdesk domain with special focus on:
1. High-performance queries for large message volumes
2. Real-time dashboard and conversation loading
3. Agent productivity optimization
4. Pagination-ready queries for infinite scroll
5. WebSocket-optimized data retrieval

Key Design Principles:
- ALL queries are tenant-scoped (multi-tenant isolation)
- Optimized for operational helpdesk workflows
- Pagination-ready for large datasets
- Real-time system compatibility
- Agent dashboard performance focus

This module powers:
- Agent dashboards and ticket lists
- Real-time conversation loading
- Customer service history
- Analytics and reporting queries
- WebSocket data feeds
"""

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from django.db.models import Q, QuerySet, Count, Prefetch, F
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from .models import Ticket, Message


# =============================================================================
# TICKET SELECTORS
# =============================================================================

def list_tickets_for_org(
    organization_id: uuid.UUID,
    filters: Optional[Dict[str, Any]] = None
) -> QuerySet[Ticket]:
    """
    List tickets for an organization with comprehensive filtering support.
    
    This is the primary query for agent dashboards and ticket management.
    Optimized for real-time updates and high-performance agent workflows.
    
    Args:
        organization_id: UUID of the organization (tenant isolation)
        filters: Optional dictionary of filters:
            - status: Ticket status ('open', 'pending', 'resolved', 'closed')
            - priority: Priority level ('low', 'medium', 'high', 'urgent')
            - channel: Communication channel ('whatsapp', 'email', etc.)
            - assigned_to: Agent user ID (UUID)
            - search: Search term for customer name or ticket title
            - sla_overdue: Boolean to filter overdue tickets
            
    Returns:
        QuerySet of Ticket instances optimized for dashboard display
        
    Example usage:
        # Agent dashboard - my open tickets
        my_tickets = list_tickets_for_org(org_id, {
            'assigned_to': agent_id,
            'status': 'open'
        })
        
        # Urgent overdue tickets for escalation
        escalation_queue = list_tickets_for_org(org_id, {
            'priority': 'urgent',
            'sla_overdue': True
        })
    """
    # Start with base queryset - always tenant-scoped
    queryset = Ticket.objects.filter(organization_id=organization_id)
    
    # Critical performance optimization for dashboard queries
    # Load related data in advance to prevent N+1 queries
    queryset = queryset.select_related(
        'customer',        # Customer name and details
        'assigned_to',     # Agent information
        'organization'     # Organization context
    ).annotate(
        # Add message count for dashboard display without additional queries
        message_count=Count('messages')
    )
    
    # Apply filters if provided
    if filters:
        # Status filtering (most common dashboard filter)
        if 'status' in filters and filters['status']:
            queryset = queryset.filter(status=filters['status'])
        
        # Priority filtering (for escalation and routing)
        if 'priority' in filters and filters['priority']:
            queryset = queryset.filter(priority=filters['priority'])
        
        # Channel filtering (for specialized agent teams)
        if 'channel' in filters and filters['channel']:
            queryset = queryset.filter(channel=filters['channel'])
        
        # Agent assignment filtering (for personal dashboards)
        if 'assigned_to' in filters and filters['assigned_to']:
            queryset = queryset.filter(assigned_to_id=filters['assigned_to'])
        
        # Search functionality across customer and ticket data
        if 'search' in filters and filters['search']:
            search_term = filters['search'].strip()
            if search_term:
                # Use Q objects for complex OR conditions across related models
                search_query = (
                    Q(title__icontains=search_term) |
                    Q(customer__name__icontains=search_term) |
                    Q(customer__email__icontains=search_term)
                )
                queryset = queryset.filter(search_query)
        
        # SLA overdue filtering (for escalation management)
        if 'sla_overdue' in filters and filters['sla_overdue']:
            now = timezone.now()
            queryset = queryset.filter(
                sla_due_at__isnull=False,
                sla_due_at__lt=now
            )
        
        # Unassigned tickets filter (for assignment queues)
        if 'unassigned' in filters and filters['unassigned']:
            queryset = queryset.filter(assigned_to__isnull=True)
        
        # Date range filtering (for reporting and analytics)
        if 'created_after' in filters and filters['created_after']:
            queryset = queryset.filter(created_at__gte=filters['created_after'])
        
        if 'created_before' in filters and filters['created_before']:
            queryset = queryset.filter(created_at__lte=filters['created_before'])
    
    # Default ordering optimized for agent workflow
    # Most recent activity first, with urgent tickets prioritized
    return queryset.order_by(
        '-priority',     # Urgent tickets first
        '-updated_at'    # Most recently updated first
    )


def get_ticket_detail(ticket_id: uuid.UUID, organization_id: uuid.UUID) -> Ticket:
    """
    Retrieve a single ticket with full detail optimization.
    
    This query is optimized for conversation views where we need
    all ticket details but not necessarily all messages.
    
    Args:
        ticket_id: UUID of the ticket to retrieve
        organization_id: UUID of the organization (tenant isolation)
        
    Returns:
        Ticket instance with optimized related data loading
        
    Raises:
        Ticket.DoesNotExist: If ticket not found or doesn't belong to organization
    """
    try:
        return Ticket.objects.select_related(
            'customer',
            'assigned_to', 
            'organization'
        ).get(
            id=ticket_id,
            organization_id=organization_id
        )
    except Ticket.DoesNotExist:
        raise Ticket.DoesNotExist(
            f"Ticket {ticket_id} not found for organization {organization_id}"
        )


def get_ticket_for_update(ticket_id: uuid.UUID, organization_id: uuid.UUID) -> Ticket:
    """
    Retrieve a ticket with SELECT FOR UPDATE lock.
    
    Critical for preventing race conditions during status changes,
    assignment operations, and message creation that updates ticket state.
    
    Args:
        ticket_id: UUID of the ticket to retrieve
        organization_id: UUID of the organization
        
    Returns:
        Ticket instance with database row lock
        
    Raises:
        Ticket.DoesNotExist: If ticket not found or doesn't belong to organization
        
    When to use:
        - Before changing ticket status
        - During agent assignment operations
        - When adding messages that might change ticket state
        - Any operation that modifies ticket in Services
    """
    try:
        return Ticket.objects.select_related(
            'customer',
            'assigned_to',
            'organization'
        ).select_for_update(of=('self',)).get(
            id=ticket_id,
            organization_id=organization_id
        )
    except Ticket.DoesNotExist:
        raise Ticket.DoesNotExist(
            f"Ticket {ticket_id} not found for organization {organization_id}"
        )


def get_tickets_by_customer(
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
    limit: Optional[int] = None
) -> QuerySet[Ticket]:
    """
    Get all tickets for a specific customer (service history).
    
    Useful for customer service representatives to see full interaction history.
    
    Args:
        customer_id: UUID of the customer
        organization_id: UUID of the organization
        limit: Optional limit on number of tickets returned
        
    Returns:
        QuerySet of Ticket instances for the customer
    """
    queryset = Ticket.objects.filter(
        customer_id=customer_id,
        organization_id=organization_id
    ).select_related('assigned_to').annotate(
        message_count=Count('messages')
    ).order_by('-created_at')
    
    if limit:
        queryset = queryset[:limit]
    
    return queryset


def get_open_ticket_for_customer(
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
    channel: Optional[str] = None,
) -> Optional[Ticket]:
    """Return the latest active ticket for a customer, optionally by channel."""
    queryset = Ticket.objects.filter(
        customer_id=customer_id,
        organization_id=organization_id,
        status__in=[Ticket.Status.OPEN, Ticket.Status.PENDING],
    ).select_related("customer", "assigned_to")

    if channel:
        queryset = queryset.filter(channel=channel)

    return queryset.order_by("-updated_at").first()


# =============================================================================
# MESSAGE SELECTORS
# =============================================================================

def list_messages_for_ticket(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID,
    pagination: Optional[Dict[str, Any]] = None
) -> QuerySet[Message]:
    """
    List messages for a ticket with pagination support.
    
    This is the core query for conversation views. Optimized for:
    - Real-time message loading
    - Infinite scroll pagination
    - WebSocket updates
    - Large conversation performance
    """
    # 1. Base query com isolamento de tenant e ORDENAÇÃO APLICADA PRIMEIRO
    queryset = Message.objects.filter(
        ticket_id=ticket_id,
        organization_id=organization_id
    ).order_by('created_at')
    
    if pagination:
        # 2. Aplica filtros cronológicos (before_id, after_id) ANTES do slice
        if pagination.get('before_id'):
            try:
                before_message = Message.objects.get(
                    id=pagination['before_id'],
                    organization_id=organization_id
                )
                queryset = queryset.filter(created_at__lt=before_message.created_at)
            except Message.DoesNotExist:
                return queryset.none()
        
        if pagination.get('after_id'):
            try:
                after_message = Message.objects.get(
                    id=pagination['after_id'],
                    organization_id=organization_id
                )
                queryset = queryset.filter(created_at__gt=after_message.created_at)
            except Message.DoesNotExist:
                return queryset.none()
                
        # 3. Aplica LIMIT e OFFSET por último (O Slice)
        offset = pagination.get('offset')
        limit = pagination.get('limit')
        
        if offset and limit:
            queryset = queryset[offset:offset + limit]
        elif offset:
            queryset = queryset[offset:]
        elif limit:
            queryset = queryset[:limit]
            
    return queryset


def get_latest_message_for_ticket(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID
) -> Optional[Message]:
    """
    Get the most recent message for a ticket.
    
    Useful for ticket list displays, last activity tracking,
    and determining conversation state.
    
    Args:
        ticket_id: UUID of the ticket
        organization_id: UUID of the organization
        
    Returns:
        Latest Message instance or None if no messages exist
    """
    try:
        return Message.objects.filter(
            ticket_id=ticket_id,
            organization_id=organization_id
        ).order_by('-created_at').first()
    except Message.DoesNotExist:
        return None


def get_message_by_external_id(
    external_message_id: str,
    organization_id: uuid.UUID
) -> Optional[Message]:
    """
    Find a message by its external platform ID.
    
    Critical for webhook deduplication and external platform integration.
    Prevents duplicate message creation from webhook retries.
    
    Args:
        external_message_id: ID from external platform (WhatsApp, email, etc.)
        organization_id: UUID of the organization
        
    Returns:
        Message instance if found, None otherwise
    """
    try:
        return Message.objects.select_related('ticket').get(
            external_message_id=external_message_id,
            organization_id=organization_id
        )
    except Message.DoesNotExist:
        return None


def get_message_by_provider_message_id(
    provider_message_id: str,
    organization_id: uuid.UUID,
) -> Optional[Message]:
    """Lookup message by WhatsApp wamid (outbound) within a tenant."""
    if not provider_message_id:
        return None
    try:
        return Message.objects.select_related("ticket", "ticket__customer").get(
            provider_message_id=provider_message_id,
            organization_id=organization_id,
        )
    except Message.DoesNotExist:
        return None


def get_message_for_outbound_send(
    message_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Message:
    """Lock message row for outbound send pipeline (Celery)."""
    try:
        return Message.objects.select_related("ticket", "ticket__customer").select_for_update(
            of=("self",),
        ).get(
            id=message_id,
            organization_id=organization_id,
        )
    except Message.DoesNotExist:
        raise Message.DoesNotExist(
            f"Message {message_id} not found for organization {organization_id}"
        )


def get_unread_messages_count(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID,
    last_read_at: datetime
) -> int:
    """
    Count unread messages in a ticket since a given timestamp.
    
    Used for notification badges and real-time UI updates.
    
    Args:
        ticket_id: UUID of the ticket
        organization_id: UUID of the organization
        last_read_at: Timestamp of last read message
        
    Returns:
        Count of unread messages
    """
    return Message.objects.filter(
        ticket_id=ticket_id,
        organization_id=organization_id,
        created_at__gt=last_read_at
    ).count()


# =============================================================================
# ANALYTICS AND REPORTING SELECTORS
# =============================================================================

def get_ticket_statistics_for_org(organization_id: uuid.UUID) -> Dict[str, Any]:
    """
    Get comprehensive ticket statistics for organization dashboard.
    
    Provides key metrics for management reporting and agent dashboards.
    
    Args:
        organization_id: UUID of the organization
        
    Returns:
        Dictionary with various ticket statistics
        
    Example return:
        {
            'total_tickets': 150,
            'open_tickets': 25,
            'pending_tickets': 10,
            'overdue_tickets': 3,
            'unassigned_tickets': 8,
            'by_priority': {'urgent': 5, 'high': 15, 'medium': 20, 'low': 10},
            'by_channel': {'whatsapp': 30, 'email': 15, 'webchat': 5}
        }
    """
    base_queryset = Ticket.objects.filter(organization_id=organization_id)
    
    # Basic counts
    total_tickets = base_queryset.count()
    open_tickets = base_queryset.filter(status=Ticket.Status.OPEN).count()
    pending_tickets = base_queryset.filter(status=Ticket.Status.PENDING).count()
    unassigned_tickets = base_queryset.filter(assigned_to__isnull=True).count()
    
    # Overdue tickets (SLA breaches)
    now = timezone.now()
    overdue_tickets = base_queryset.filter(
        sla_due_at__isnull=False,
        sla_due_at__lt=now
    ).count()
    
    # Priority distribution
    priority_stats = {}
    for priority_choice in Ticket.Priority.choices:
        priority_key = priority_choice[0]
        priority_stats[priority_key] = base_queryset.filter(priority=priority_key).count()
    
    # Channel distribution
    channel_stats = {}
    for channel_choice in Ticket.Channel.choices:
        channel_key = channel_choice[0]
        channel_stats[channel_key] = base_queryset.filter(channel=channel_key).count()
    
    return {
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'pending_tickets': pending_tickets,
        'overdue_tickets': overdue_tickets,
        'unassigned_tickets': unassigned_tickets,
        'by_priority': priority_stats,
        'by_channel': channel_stats,
    }


def get_agent_workload_stats(organization_id: uuid.UUID) -> QuerySet:
    """
    Get workload statistics per agent for management dashboards.
    
    Shows ticket distribution and performance metrics per agent.
    
    Args:
        organization_id: UUID of the organization
        
    Returns:
        QuerySet with agent statistics annotated
    """
    from apps.iam.models import User
    
    return User.objects.filter(
        organization_id=organization_id
    ).annotate(
        total_assigned=Count('assigned_tickets'),
        open_assigned=Count(
            'assigned_tickets',
            filter=Q(assigned_tickets__status=Ticket.Status.OPEN)
        ),
        pending_assigned=Count(
            'assigned_tickets', 
            filter=Q(assigned_tickets__status=Ticket.Status.PENDING)
        )
    ).order_by('-total_assigned')