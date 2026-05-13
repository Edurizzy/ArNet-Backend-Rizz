"""
Helpdesk API Serializers for ArNet Platform.

Serializers handle data validation and serialization for the helpdesk API with
strict separation of concerns:

1. Data format validation (types, required fields, formats) 
2. Basic field-level validation
3. JSON serialization/deserialization

They should NOT contain:
- Business logic (belongs in Services)
- Complex cross-field validation (belongs in Services)
- Database operations (belongs in Services/Selectors)
- Side effects or orchestration logic

These serializers are optimized for:
- Real-time helpdesk operations
- Agent productivity workflows
- High-frequency message creation
- WebSocket-compatible data structures
"""

from rest_framework import serializers
from datetime import datetime
from typing import Dict, Any

from ..models import Ticket, Message


# =============================================================================
# TICKET SERIALIZERS
# =============================================================================

class TicketSerializer(serializers.ModelSerializer):
    """
    Full ticket serializer for detail views and updates.
    
    Used for complete ticket information including all relationships
    and metadata needed for agent conversation views.
    """
    
    # Read-only customer information for display
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    
    # Read-only agent information for display
    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name', 
        read_only=True,
        allow_null=True
    )
    
    # Computed fields for UI display
    is_overdue = serializers.ReadOnlyField()
    message_count = serializers.IntegerField(read_only=True)
    
    # Customer ID for ticket creation/updates
    customer_id = serializers.UUIDField(write_only=True)
    
    # Agent assignment
    assigned_to = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="UUID of agent to assign ticket to"
    )
    
    class Meta:
        model = Ticket
        fields = [
            'id',
            'customer_id',
            'customer_name',
            'customer_email',
            'assigned_to',
            'assigned_to_name',
            'title',
            'channel',
            'status',
            'priority',
            'sla_due_at',
            'metadata',
            'is_overdue',
            'message_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'customer_name', 
            'customer_email',
            'assigned_to_name',
            'is_overdue',
            'message_count',
            'created_at',
            'updated_at'
        ]
    
    def validate_title(self, value: str) -> str:
        """Validate ticket title format."""
        if not value or not value.strip():
            raise serializers.ValidationError("Ticket title cannot be empty")
        
        title = value.strip()
        if len(title) < 3:
            raise serializers.ValidationError("Ticket title must be at least 3 characters")
        
        if len(title) > 255:
            raise serializers.ValidationError("Ticket title cannot exceed 255 characters")
        
        return title
    
    def validate_channel(self, value: str) -> str:
        """Validate communication channel."""
        if value not in [choice[0] for choice in Ticket.Channel.choices]:
            raise serializers.ValidationError(f"Invalid channel: {value}")
        return value
    
    def validate_priority(self, value: str) -> str:
        """Validate ticket priority."""
        if value not in [choice[0] for choice in Ticket.Priority.choices]:
            raise serializers.ValidationError(f"Invalid priority: {value}")
        return value
    
    def validate_status(self, value: str) -> str:
        """Validate ticket status."""
        if value not in [choice[0] for choice in Ticket.Status.choices]:
            raise serializers.ValidationError(f"Invalid status: {value}")
        return value


class TicketCreateSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for creating tickets.
    
    Streamlined for ticket creation with required fields explicit.
    """
    
    customer_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the customer creating the ticket"
    )
    
    title = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Brief description of the customer issue"
    )
    
    channel = serializers.ChoiceField(
        choices=Ticket.Channel.choices,
        required=True,
        help_text="Communication channel where ticket originated"
    )
    
    priority = serializers.ChoiceField(
        choices=Ticket.Priority.choices,
        required=False,
        default=Ticket.Priority.MEDIUM,
        help_text="Ticket priority level"
    )
    
    assigned_to = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional initial agent assignment"
    )
    
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Additional ticket metadata"
    )
    
    class Meta:
        model = Ticket
        fields = [
            'customer_id',
            'title', 
            'channel',
            'priority',
            'assigned_to',
            'metadata'
        ]


class TicketListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for ticket list views.
    
    Optimized for agent dashboards with minimal data transfer
    while providing essential information for ticket management.
    """
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name',
        read_only=True,
        allow_null=True
    )
    
    # Message count annotation (provided by selector)
    message_count = serializers.IntegerField(read_only=True)
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = Ticket
        fields = [
            'id',
            'customer_name',
            'assigned_to_name',
            'title',
            'channel',
            'status', 
            'priority',
            'message_count',
            'is_overdue',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'customer_name', 'assigned_to_name', 'created_at', 'updated_at']


# =============================================================================
# MESSAGE SERIALIZERS
# =============================================================================

class MessageSerializer(serializers.ModelSerializer):
    """
    Full message serializer for conversation views.
    
    Used for displaying messages in ticket conversations with
    all necessary context for real-time communication.
    """
    
    # Sender information for display (when applicable)
    sender_name = serializers.SerializerMethodField()
    
    # Computed properties for UI
    is_from_customer = serializers.ReadOnlyField()
    is_ai_generated = serializers.ReadOnlyField()
    needs_response = serializers.ReadOnlyField()
    
    class Meta:
        model = Message
        fields = [
            'id',
            'sender_type',
            'direction',
            'sender_id',
            'sender_name',
            'content',
            'is_internal',
            'external_message_id',
            'metadata',
            'delivery_status',
            'provider_message_id',
            'correlation_id',
            'queued_at',
            'sent_at',
            'delivered_at',
            'failed_at',
            'is_from_customer',
            'is_ai_generated',
            'needs_response',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'sender_name',
            'is_from_customer',
            'is_ai_generated', 
            'needs_response',
            'delivery_status',
            'provider_message_id',
            'correlation_id',
            'queued_at',
            'sent_at',
            'delivered_at',
            'failed_at',
            'created_at',
            'updated_at'
        ]
    
    def get_sender_name(self, obj: Message) -> str:
        """
        Get human-readable sender name based on sender type and ID.
        
        This provides context for message attribution in the UI.
        """
        if obj.sender_type == Message.SenderType.CUSTOMER:
            return obj.ticket.customer.name
        elif obj.sender_type == Message.SenderType.AGENT and obj.sender_id:
            # In a real implementation, we'd look up the agent name
            # For now, return a placeholder
            return f"Agent"
        elif obj.sender_type == Message.SenderType.AI_AGENT:
            return "AI Assistant"
        elif obj.sender_type == Message.SenderType.SYSTEM:
            return "System"
        else:
            return "Unknown"


class MessageCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating messages in tickets.
    
    Optimized for high-frequency message creation with validation
    focused on real-time communication workflows.
    """
    
    ticket_id = serializers.UUIDField(
        write_only=True,
        required=True,
        help_text="UUID of the ticket to add message to"
    )
    
    sender_type = serializers.ChoiceField(
        choices=Message.SenderType.choices,
        required=True,
        help_text="Type of message sender"
    )
    
    direction = serializers.ChoiceField(
        choices=Message.Direction.choices,
        required=False,
        default=Message.Direction.INBOUND,
        help_text="Message direction"
    )
    
    content = serializers.CharField(
        required=True,
        help_text="Message content/text"
    )
    
    sender_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="UUID of the message sender"
    )
    
    is_internal = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether message is internal note"
    )
    
    external_message_id = serializers.CharField(
        required=False,
        allow_null=True,
        max_length=255,
        help_text="External platform message ID for deduplication"
    )
    
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Message metadata (attachments, AI context, etc.)"
    )
    
    class Meta:
        model = Message
        fields = [
            'ticket_id',
            'sender_type',
            'direction',
            'sender_id',
            'content',
            'is_internal',
            'external_message_id',
            'metadata'
        ]
    
    def validate_content(self, value: str) -> str:
        """Validate message content."""
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        
        content = value.strip()
        if len(content) > 10000:  # Reasonable limit for message length
            raise serializers.ValidationError("Message content too long (max 10,000 characters)")
        
        return content


class OutboundWhatsAppMessageCreateSerializer(serializers.Serializer):
    """POST body for ``/tickets/{id}/messages/`` (WhatsApp outbound)."""

    content = serializers.CharField(
        required=True,
        help_text="Message body to send via WhatsApp",
    )
    correlation_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional client trace id; server generates one if omitted",
    )

    def validate_content(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        content = value.strip()
        if len(content) > 10000:
            raise serializers.ValidationError("Message content too long (max 10,000 characters)")
        return content


class MessageListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for message lists and real-time updates.
    
    Used for conversation loading and WebSocket message streaming
    with minimal data transfer overhead.
    """
    
    sender_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id',
            'sender_type',
            'direction',
            'sender_name',
            'content',
            'is_internal',
            'delivery_status',
            'provider_message_id',
            'created_at'
        ]
        read_only_fields = ['id', 'sender_name', 'delivery_status', 'provider_message_id', 'created_at']
    
    def get_sender_name(self, obj: Message) -> str:
        """Get simplified sender name for list display."""
        if obj.sender_type == Message.SenderType.CUSTOMER:
            return obj.ticket.customer.name
        elif obj.sender_type == Message.SenderType.AGENT:
            return "Agent"
        elif obj.sender_type == Message.SenderType.AI_AGENT:
            return "AI"
        else:
            return "System"


# =============================================================================
# FILTER SERIALIZERS (Query Parameters)
# =============================================================================

class TicketFilterSerializer(serializers.Serializer):
    """
    Serializer for ticket list filtering query parameters.
    
    Validates URL query parameters for ticket filtering:
    GET /api/v1/helpdesk/tickets/?status=open&priority=urgent&assigned_to=uuid
    """
    
    status = serializers.ChoiceField(
        choices=Ticket.Status.choices,
        required=False,
        help_text="Filter by ticket status"
    )
    
    priority = serializers.ChoiceField(
        choices=Ticket.Priority.choices,
        required=False,
        help_text="Filter by ticket priority"
    )
    
    channel = serializers.ChoiceField(
        choices=Ticket.Channel.choices,
        required=False,
        help_text="Filter by communication channel"
    )
    
    assigned_to = serializers.UUIDField(
        required=False,
        help_text="Filter by assigned agent UUID"
    )
    
    search = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Search in customer name, email, or ticket title"
    )
    
    sla_overdue = serializers.BooleanField(
        required=False,
        help_text="Filter tickets that are past SLA due date"
    )
    
    unassigned = serializers.BooleanField(
        required=False,
        help_text="Filter unassigned tickets"
    )
    
    created_after = serializers.DateTimeField(
        required=False,
        help_text="Filter tickets created after this date"
    )
    
    created_before = serializers.DateTimeField(
        required=False,
        help_text="Filter tickets created before this date"
    )


class MessageFilterSerializer(serializers.Serializer):
    """
    Serializer for message pagination and filtering query parameters.
    
    Used for conversation loading and real-time message streaming.
    """
    
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=200,  # Reasonable limit for conversation loading
        help_text="Number of messages to return (max 200)"
    )
    
    offset = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="Number of messages to skip"
    )
    
    before_id = serializers.UUIDField(
        required=False,
        help_text="Get messages before this message ID (for scrolling up)"
    )
    
    after_id = serializers.UUIDField(
        required=False,
        help_text="Get messages after this message ID (for real-time updates)"
    )


# =============================================================================
# OPERATIONAL SERIALIZERS
# =============================================================================

class TicketStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for ticket status update operations.
    
    Used for status change API endpoints with audit context.
    """
    
    status = serializers.ChoiceField(
        choices=Ticket.Status.choices,
        required=True,
        help_text="New ticket status"
    )
    
    reason = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Optional reason for status change"
    )


class TicketAssignmentSerializer(serializers.Serializer):
    """
    Serializer for ticket assignment operations.
    """
    
    agent_id = serializers.UUIDField(
        required=True,
        help_text="UUID of agent to assign ticket to"
    )


class BulkTicketAssignmentSerializer(serializers.Serializer):
    """
    Serializer for bulk ticket assignment operations.
    """
    
    ticket_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50,  # Reasonable limit for bulk operations
        help_text="List of ticket UUIDs to assign (max 50)"
    )
    
    agent_id = serializers.UUIDField(
        required=True,
        help_text="UUID of agent to assign tickets to"
    )


# =============================================================================
# ANALYTICS SERIALIZERS
# =============================================================================

class TicketStatisticsSerializer(serializers.Serializer):
    """
    Serializer for ticket statistics data (read-only).
    
    Used for dashboard metrics and reporting endpoints.
    """
    
    total_tickets = serializers.IntegerField(read_only=True)
    open_tickets = serializers.IntegerField(read_only=True)
    pending_tickets = serializers.IntegerField(read_only=True)
    overdue_tickets = serializers.IntegerField(read_only=True)
    unassigned_tickets = serializers.IntegerField(read_only=True)
    by_priority = serializers.DictField(read_only=True)
    by_channel = serializers.DictField(read_only=True)