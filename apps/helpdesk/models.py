"""
Helpdesk Domain Models for ArNet Platform.

This module contains the operational heart of the customer support system:
- Ticket: Central entity representing customer support cases
- Message: Individual communications within tickets (omnichannel)

Key Design Principles:
1. Event-driven architecture ready (future websockets, automations)
2. Multi-tenant isolation with TenantAwareModel
3. High-performance indexes for large message volumes
4. AI integration ready (metadata, AI agent support)
5. Omnichannel communication support
6. Full auditability and traceability

This is NOT just CRUD - this is an operational event stream that will power:
- Real-time communication
- AI orchestration 
- Automation workflows
- Analytics pipelines
- WebSocket broadcasting
- Audit trails
"""

import uuid
from typing import TYPE_CHECKING

from django.core.validators import MinLengthValidator
from django.db import models

from apps.common.models import TenantAwareModel

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from apps.crm.models import Customer
    from apps.iam.models import User


class Ticket(TenantAwareModel):
    """
    Ticket model representing customer support cases.
    
    This is the central orchestrating entity for all customer interactions.
    Think of it as a "conversation container" that holds all messages,
    tracks status, manages SLAs, and coordinates AI/human agent responses.
    
    The ticket serves as the source of truth for:
    - Customer support cases across all channels
    - AI agent orchestration and handoffs
    - SLA tracking and escalation
    - Agent workload management
    - Audit trails and analytics
    
    Event-Driven Design:
    Every ticket state change will trigger future domain events for:
    - WebSocket notifications to agents/customers
    - AI agent triggers and automations
    - SLA monitoring and alerting
    - Analytics and reporting
    - Audit logging
    """
    
    # Communication Channel Types
    # These represent the omnichannel sources of customer interactions
    class Channel(models.TextChoices):
        WHATSAPP = 'whatsapp', 'WhatsApp'
        EMAIL = 'email', 'Email'
        WEBCHAT = 'webchat', 'Web Chat'
        INSTAGRAM = 'instagram', 'Instagram'
    
    # Ticket Status Lifecycle
    # These represent the operational states in the support workflow
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'                   # New ticket, needs attention
        PENDING = 'pending', 'Pending'         # Waiting for customer response
        RESOLVED = 'resolved', 'Resolved'      # Issue resolved, awaiting confirmation
        CLOSED = 'closed', 'Closed'           # Ticket closed and archived
    
    # Priority Levels for SLA and Escalation
    # These drive routing, SLA calculations, and AI prioritization
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'
    
    # Core Relationships
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.CASCADE,
        related_name='tickets',
        help_text="Customer who created this support ticket"
    )
    
    assigned_to = models.ForeignKey(
        'iam.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        help_text="Agent currently responsible for this ticket"
    )
    
    # Ticket Identification and Classification
    title = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(3)],
        help_text="Brief description of the customer issue"
    )
    
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        help_text="Communication channel where the ticket originated"
    )
    
    # Operational State
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        help_text="Current ticket status in the support workflow"
    )
    
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        help_text="Priority level affecting SLA and routing"
    )
    
    # SLA and Time Tracking
    sla_due_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this ticket's SLA expires (for escalation)"
    )
    
    # Flexible Metadata Storage
    # This supports AI agents, automation rules, and custom integrations
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible storage for AI context, automation data, and integrations"
    )
    
    class Meta:
        verbose_name = "Support Ticket"
        verbose_name_plural = "Support Tickets"
        
        # Performance-optimized indexes for operational queries
        indexes = [
            # Agent dashboard queries (most common)
            models.Index(fields=['organization', 'status'], name='helpdesk_ticket_org_status'),
            models.Index(fields=['organization', 'priority'], name='helpdesk_ticket_org_priority'),
            models.Index(fields=['organization', 'channel'], name='helpdesk_ticket_org_channel'),
            models.Index(fields=['organization', 'assigned_to'], name='helpdesk_ticket_org_assigned'),
            
            # SLA monitoring and escalation queries
            models.Index(fields=['organization', 'sla_due_at'], name='helpdesk_ticket_org_sla'),
            
            # Customer service history
            models.Index(fields=['customer', 'created_at'], name='helpdesk_ticket_cust_created'),
            
            # Time-series queries for analytics
            models.Index(fields=['organization', 'created_at'], name='helpdesk_ticket_org_created'),
        ]
    
    def __str__(self) -> str:
        """Human-readable representation focusing on operational context."""
        return f"#{str(self.id)[:8]} - {self.title} ({self.status.title()})"
    
    @property
    def is_overdue(self) -> bool:
        """
        Check if ticket has exceeded its SLA.
        
        This is a simple computed property for UI display.
        Complex SLA business logic belongs in Services.
        """
        if not self.sla_due_at:
            return False
        
        from django.utils import timezone
        return timezone.now() > self.sla_due_at
    
    @property
    def message_count(self) -> int:
        """
        Get count of messages in this ticket.
        
        Note: This will cause a DB query. For list views, use annotations
        in selectors to avoid N+1 queries.
        """
        return self.messages.count()


class Message(TenantAwareModel):
    """
    Message model representing individual communications within tickets.
    
    This is the granular event unit in our operational stream. Every message
    represents a discrete communication event that can trigger:
    - Real-time WebSocket updates
    - AI agent processing and responses
    - Automation workflows
    - Customer notifications
    - Analytics events
    
    The message model supports:
    - Omnichannel communication (email, chat, WhatsApp, etc.)
    - Human and AI agent interactions
    - Internal notes and system messages
    - External platform integration via external_message_id
    - Rich metadata for AI context and automation
    
    Event-Driven Architecture:
    Every message creation will trigger future domain events for:
    - WebSocket broadcasting to agents/customers
    - AI agent analysis and auto-responses
    - Customer notification delivery
    - Ticket status evaluation (auto-reopen, etc.)
    - Analytics and sentiment tracking
    """
    
    # Message Sender Types
    # These identify who/what created the message for routing and display
    class SenderType(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'       # End customer/user
        AGENT = 'agent', 'Human Agent'         # Human support agent
        SYSTEM = 'system', 'System'            # Automated system messages
        AI_AGENT = 'ai_agent', 'AI Agent'      # AI-powered agent responses
    
    # Message Direction for Omnichannel Routing
    # Critical for understanding conversation flow and automation triggers
    class Direction(models.TextChoices):
        INBOUND = 'inbound', 'Inbound'         # Message coming into the platform
        OUTBOUND = 'outbound', 'Outbound'      # Message going out from the platform
    
    # Core Relationship
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="Ticket this message belongs to"
    )
    
    # Message Attribution and Routing
    sender_type = models.CharField(
        max_length=20,
        choices=SenderType.choices,
        help_text="Type of sender (customer, agent, system, AI)"
    )
    
    direction = models.CharField(
        max_length=20,
        choices=Direction.choices,
        help_text="Message direction (inbound/outbound)"
    )
    
    sender_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID of the sender (User ID, Customer ID, AI Agent ID, etc.)"
    )
    
    # Message Content
    content = models.TextField(
        help_text="The actual message content/text"
    )
    
    # Internal Communication Control
    is_internal = models.BooleanField(
        default=False,
        help_text="True if this is an internal note not visible to customers"
    )
    
    # External Platform Integration
    external_message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,  # Critical for webhook deduplication
        help_text="ID from external platform (WhatsApp, email provider, etc.)"
    )
    
    # Flexible Context Storage
    # Supports AI processing, automation rules, and rich integrations
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="AI context, automation data, attachments, rich content, etc."
    )
    
    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        
        # High-performance indexes for operational queries
        indexes = [
            # Conversation view (most critical query)
            models.Index(fields=['ticket', 'created_at'], name='helpdesk_msg_ticket_created'),
            
            # Real-time message streams and WebSocket queries
            models.Index(fields=['organization', 'created_at'], name='helpdesk_msg_org_created'),
            
            # AI agent and automation processing
            models.Index(fields=['organization', 'sender_type'], name='helpdesk_msg_org_sender'),
            
            # External platform webhook deduplication
            models.Index(fields=['external_message_id'], name='helpdesk_msg_external_id'),
            
            # Customer communication history
            models.Index(fields=['organization', 'sender_id', 'created_at'], name='helpdesk_msg_sender_created'),
        ]
        
        # Ensure message ordering is consistent
        ordering = ['created_at']
    
    def __str__(self) -> str:
        """Human-readable representation for admin and debugging."""
        sender_info = f"{self.sender_type}"
        if self.sender_type == self.SenderType.CUSTOMER:
            sender_info = f"Customer"
        elif self.sender_type == self.SenderType.AGENT:
            sender_info = f"Agent"
        
        # Truncate content for readability
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        
        return f"{sender_info}: {content_preview}"
    
    @property
    def is_from_customer(self) -> bool:
        """Check if message is from customer (useful for UI logic)."""
        return self.sender_type == self.SenderType.CUSTOMER
    
    @property
    def is_ai_generated(self) -> bool:
        """Check if message was generated by AI (useful for analytics)."""
        return self.sender_type == self.SenderType.AI_AGENT
    
    @property
    def needs_response(self) -> bool:
        """
        Simple heuristic for determining if message needs a response.
        
        Complex business logic for response requirements belongs in Services.
        This is just a UI helper.
        """
        return (
            self.sender_type == self.SenderType.CUSTOMER and
            self.direction == self.Direction.INBOUND and
            not self.is_internal
        )