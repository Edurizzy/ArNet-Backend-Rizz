"""
Helpdesk Django Admin Configuration for ArNet Platform.

This module configures Django admin for helpdesk operations with focus on:
1. Operational monitoring and management
2. Agent productivity and workload visibility  
3. Customer service quality assurance
4. SLA tracking and escalation management
5. Audit trails and conversation history

Key Features:
- Multi-tenant filtering (tenant-safe operations)
- Optimized queries for large message volumes
- Real-time operational insights
- Bulk operations for efficiency
- Customer service workflow optimization
"""

from django.contrib import admin
from django.db.models import QuerySet, Count, Q, Max
from django.http import HttpRequest
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from typing import Optional

from .models import Ticket, Message


# =============================================================================
# CUSTOM ADMIN BASE CLASSES
# =============================================================================

class HelpdeskAdminMixin:
    """
    Mixin to provide tenant-aware filtering for helpdesk admin interfaces.
    
    Ensures operational staff only see data for their organization
    while providing performance optimizations for large datasets.
    """
    
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Filter queryset to organization with performance optimization."""
        qs = super().get_queryset(request)
        
        # Apply tenant filtering if user has organization
        if hasattr(request.user, 'organization_id') and request.user.organization_id:
            qs = qs.filter(organization_id=request.user.organization_id)
        
        return qs
    
    def save_model(self, request: HttpRequest, obj, form, change: bool):
        """Automatically set organization for new objects."""
        if not change and hasattr(obj, 'organization_id') and not obj.organization_id:
            if hasattr(request.user, 'organization_id'):
                obj.organization_id = request.user.organization_id
        
        super().save_model(request, obj, form, change)


# =============================================================================
# TICKET ADMIN
# =============================================================================

@admin.register(Ticket)
class TicketAdmin(HelpdeskAdminMixin, admin.ModelAdmin):
    """
    Admin interface for Ticket model with operational focus.
    
    Designed for:
    - Agent workload monitoring
    - SLA tracking and escalation
    - Customer service oversight  
    - Bulk ticket operations
    - Quality assurance workflows
    """
    
    # List view optimized for operational monitoring
    list_display = [
        'ticket_number',
        'customer_link',
        'title_truncated',
        'status_badge',
        'priority_badge',
        'channel_badge',
        'assigned_to_link',
        'message_count',
        'sla_status',
        'created_at',
        'last_activity'
    ]
    
    list_filter = [
        'status',
        'priority', 
        'channel',
        'assigned_to',
        ('sla_due_at', admin.DateFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
        ('updated_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'title',
        'customer__name',
        'customer__email',
        'assigned_to__first_name',
        'assigned_to__last_name',
        'assigned_to__email'
    ]
    
    # Filters for operational workflows
    list_filter = [
        'status',
        'priority',
        'channel', 
        'assigned_to',
        'sla_due_at',
        'created_at'
    ]
    
    # Ordering for operational priority
    ordering = ['-priority', '-updated_at']
    list_per_page = 50  # Handle large volumes
    
    # Detail view organization
    fieldsets = (
        ('Ticket Information', {
            'fields': ('customer', 'title', 'channel', 'status', 'priority')
        }),
        ('Assignment & SLA', {
            'fields': ('assigned_to', 'sla_due_at')
        }),
        ('Metadata & Context', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('id', 'organization', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'message_count',
        'last_activity'
    ]
    
    # Performance optimization for admin queries
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset with related data and annotations."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'customer',
            'assigned_to',
            'organization'
        ).annotate(
            message_count=Count('messages'),
            last_message_at=Max('messages__created_at')
        ).prefetch_related('messages')
    
    # Custom display methods
    def ticket_number(self, obj: Ticket) -> str:
        """Display ticket number as short ID."""
        return f"#{str(obj.id)[:8]}"
    ticket_number.short_description = 'Ticket #'
    ticket_number.admin_order_field = 'id'
    
    def customer_link(self, obj: Ticket) -> str:
        """Display customer name as link to customer admin."""
        url = reverse('admin:crm_customer_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.name)
    customer_link.short_description = 'Customer'
    customer_link.admin_order_field = 'customer__name'
    
    def title_truncated(self, obj: Ticket) -> str:
        """Display truncated title for list view."""
        if len(obj.title) > 50:
            return f"{obj.title[:50]}..."
        return obj.title
    title_truncated.short_description = 'Title'
    title_truncated.admin_order_field = 'title'
    
    def status_badge(self, obj: Ticket) -> str:
        """Display status as colored badge."""
        color_map = {
            'open': '#dc3545',      # Red
            'pending': '#ffc107',   # Yellow
            'resolved': '#28a745',  # Green
            'closed': '#6c757d'     # Gray
        }
        color = color_map.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def priority_badge(self, obj: Ticket) -> str:
        """Display priority as colored badge."""
        color_map = {
            'urgent': '#dc3545',    # Red
            'high': '#fd7e14',      # Orange
            'medium': '#ffc107',    # Yellow
            'low': '#28a745'        # Green
        }
        color = color_map.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    priority_badge.admin_order_field = 'priority'
    
    def channel_badge(self, obj: Ticket) -> str:
        """Display channel with appropriate styling."""
        return format_html(
            '<span class="badge">{}</span>',
            obj.get_channel_display()
        )
    channel_badge.short_description = 'Channel'
    channel_badge.admin_order_field = 'channel'
    
    def assigned_to_link(self, obj: Ticket) -> str:
        """Display assigned agent with link."""
        if obj.assigned_to:
            url = reverse('admin:iam_user_change', args=[obj.assigned_to.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.assigned_to.get_full_name()
            )
        return format_html('<span style="color: #dc3545;">Unassigned</span>')
    assigned_to_link.short_description = 'Assigned To'
    assigned_to_link.admin_order_field = 'assigned_to__first_name'
    
    def message_count(self, obj: Ticket) -> int:
        """Display message count from annotation."""
        return getattr(obj, 'message_count', 0)
    message_count.short_description = 'Messages'
    message_count.admin_order_field = 'message_count'
    
    def sla_status(self, obj: Ticket) -> str:
        """Display SLA status with visual indicators."""
        if not obj.sla_due_at:
            return format_html('<span style="color: #6c757d;">No SLA</span>')
        
        now = timezone.now()
        if now > obj.sla_due_at:
            return format_html('<span style="color: #dc3545;">⚠️ OVERDUE</span>')
        
        time_remaining = obj.sla_due_at - now
        if time_remaining.total_seconds() < 3600:  # Less than 1 hour
            return format_html('<span style="color: #fd7e14;">🕐 < 1hr</span>')
        
        return format_html('<span style="color: #28a745;">✅ On Time</span>')
    sla_status.short_description = 'SLA Status'
    sla_status.admin_order_field = 'sla_due_at'
    
    def last_activity(self, obj: Ticket) -> str:
        """Display last activity timestamp."""
        return obj.updated_at
    last_activity.short_description = 'Last Activity'
    last_activity.admin_order_field = 'updated_at'
    
    # Bulk actions for operational efficiency
    actions = [
        'mark_as_open',
        'mark_as_pending',
        'mark_as_resolved',
        'mark_as_closed',
        'assign_to_me'
    ]
    
    def mark_as_open(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark tickets as open."""
        updated = queryset.update(status=Ticket.Status.OPEN)
        self.message_user(request, f'{updated} tickets marked as open.')
    mark_as_open.short_description = "Mark selected tickets as open"
    
    def mark_as_pending(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark tickets as pending."""
        updated = queryset.update(status=Ticket.Status.PENDING)
        self.message_user(request, f'{updated} tickets marked as pending.')
    mark_as_pending.short_description = "Mark selected tickets as pending"
    
    def mark_as_resolved(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark tickets as resolved."""
        updated = queryset.update(status=Ticket.Status.RESOLVED)
        self.message_user(request, f'{updated} tickets marked as resolved.')
    mark_as_resolved.short_description = "Mark selected tickets as resolved"
    
    def mark_as_closed(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark tickets as closed."""
        updated = queryset.update(status=Ticket.Status.CLOSED)
        self.message_user(request, f'{updated} tickets marked as closed.')
    mark_as_closed.short_description = "Mark selected tickets as closed"
    
    def assign_to_me(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to assign tickets to current user."""
        updated = queryset.update(assigned_to=request.user)
        self.message_user(request, f'{updated} tickets assigned to you.')
    assign_to_me.short_description = "Assign selected tickets to me"


# =============================================================================
# MESSAGE ADMIN
# =============================================================================

@admin.register(Message)
class MessageAdmin(HelpdeskAdminMixin, admin.ModelAdmin):
    """
    Admin interface for Message model with conversation focus.
    
    Designed for:
    - Quality assurance and audit trails
    - Conversation monitoring and review
    - Customer interaction analysis
    - Message search and filtering
    """
    
    # List view for message monitoring
    list_display = [
        'message_id',
        'ticket_link',
        'sender_info',
        'direction_badge',
        'content_preview',
        'is_internal',
        'created_at'
    ]
    
    list_filter = [
        'sender_type',
        'direction',
        'is_internal',
        ('created_at', admin.DateFieldListFilter),
        'ticket__status',
        'ticket__channel'
    ]
    
    search_fields = [
        'content',
        'ticket__title',
        'ticket__customer__name',
        'ticket__customer__email',
        'external_message_id'
    ]
    
    ordering = ['-created_at']
    list_per_page = 100  # Handle large conversation volumes
    
    # Detail view organization
    fieldsets = (
        ('Message Information', {
            'fields': ('ticket', 'sender_type', 'direction', 'sender_id', 'content')
        }),
        ('Message Properties', {
            'fields': ('is_internal', 'external_message_id')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('id', 'organization', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at'
    ]
    
    # Performance optimization
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset with related data."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'ticket',
            'ticket__customer',
            'ticket__assigned_to',
            'organization'
        )
    
    # Custom display methods
    def message_id(self, obj: Message) -> str:
        """Display message ID as short identifier."""
        return f"MSG#{str(obj.id)[:8]}"
    message_id.short_description = 'Message ID'
    message_id.admin_order_field = 'id'
    
    def ticket_link(self, obj: Message) -> str:
        """Display ticket as clickable link."""
        url = reverse('admin:helpdesk_ticket_change', args=[obj.ticket.id])
        return format_html(
            '<a href="{}">#{}</a>',
            url,
            str(obj.ticket.id)[:8]
        )
    ticket_link.short_description = 'Ticket'
    ticket_link.admin_order_field = 'ticket__id'
    
    def sender_info(self, obj: Message) -> str:
        """Display sender information with context."""
        if obj.sender_type == Message.SenderType.CUSTOMER:
            return format_html(
                '<span style="color: #007bff;">👤 {}</span>',
                obj.ticket.customer.name
            )
        elif obj.sender_type == Message.SenderType.AGENT:
            return format_html(
                '<span style="color: #28a745;">🎧 Agent</span>'
            )
        elif obj.sender_type == Message.SenderType.AI_AGENT:
            return format_html(
                '<span style="color: #6f42c1;">🤖 AI Assistant</span>'
            )
        else:
            return format_html(
                '<span style="color: #6c757d;">⚙️ System</span>'
            )
    sender_info.short_description = 'Sender'
    sender_info.admin_order_field = 'sender_type'
    
    def direction_badge(self, obj: Message) -> str:
        """Display message direction with visual indicator."""
        if obj.direction == Message.Direction.INBOUND:
            return format_html(
                '<span style="color: #007bff;">📥 In</span>'
            )
        else:
            return format_html(
                '<span style="color: #28a745;">📤 Out</span>'
            )
    direction_badge.short_description = 'Direction'
    direction_badge.admin_order_field = 'direction'
    
    def content_preview(self, obj: Message) -> str:
        """Display truncated message content."""
        content = obj.content.strip()
        if len(content) > 100:
            return f"{content[:100]}..."
        return content
    content_preview.short_description = 'Content'
    content_preview.admin_order_field = 'content'
    
    # Filter foreign key choices based on organization
    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        """Filter ticket choices to organization scope."""
        if db_field.name == "ticket":
            if hasattr(request.user, 'organization_id') and request.user.organization_id:
                kwargs["queryset"] = Ticket.objects.filter(
                    organization_id=request.user.organization_id
                ).select_related('customer')
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# =============================================================================
# INLINE ADMIN CLASSES
# =============================================================================

class MessageInline(admin.TabularInline):
    """
    Inline admin for showing messages within ticket detail view.
    
    Provides conversation context directly in ticket management interface.
    """
    model = Message
    extra = 0
    readonly_fields = ['created_at', 'sender_type', 'direction']
    
    fields = [
        'sender_type',
        'direction',
        'content',
        'is_internal',
        'created_at'
    ]
    
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize inline queryset and limit to recent messages."""
        qs = super().get_queryset(request)
        # Show only recent 10 messages in inline (performance)
        return qs.order_by('-created_at')[:10]


# Add inline to Ticket admin
TicketAdmin.inlines = [MessageInline]


# =============================================================================
# ADMIN SITE CUSTOMIZATION
# =============================================================================

# Customize admin site headers for helpdesk section
admin.site.site_header = "ArNet Helpdesk Administration"
admin.site.site_title = "ArNet Helpdesk Admin" 
admin.site.index_title = "Customer Support Operations"

# Performance note: For production deployments with large message volumes,
# consider implementing:
# 1. Database query optimization with proper indexing
# 2. Admin pagination and filtering limits
# 3. Caching for frequently accessed data
# 4. Separate read-only admin views for large datasets