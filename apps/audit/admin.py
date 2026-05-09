"""
Admin interface for Audit app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.common.admin import BaseModelAdmin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(BaseModelAdmin):
    """
    Admin interface for AuditLog model.
    
    This provides a comprehensive view of all audit logs
    with filtering, searching, and detailed information.
    """
    
    list_display = [
        'created_at',
        'actor_display',
        'action_badge',
        'entity_info',
        'outcome_badge',
        'risk_badge',
        'organization_link',
        'ip_address'
    ]
    
    list_filter = [
        'action_category',
        'outcome',
        'is_sensitive',
        ('risk_score', admin.RangeFilter),
        'created_at',
        'organization_id'
    ]
    
    search_fields = [
        'action',
        'entity_type',
        'entity_name',
        'ip_address',
        'correlation_id'
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'actor_display_detailed',
        'entity_display',
        'request_info',
        'changes_display',
        'details_display'
    ]
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id',
                'created_at',
                'correlation_id',
                'action',
                'action_category',
                'outcome',
                'status_code',
            )
        }),
        ('Actor Information', {
            'fields': (
                'actor_user_id',
                'actor_type',
                'actor_display_detailed',
            )
        }),
        ('Entity Information', {
            'fields': (
                'entity_type',
                'entity_id',
                'entity_name',
                'entity_display',
            )
        }),
        ('Request Context', {
            'fields': (
                'ip_address',
                'user_agent',
                'session_id',
                'request_info',
            )
        }),
        ('Risk & Security', {
            'fields': (
                'risk_score',
                'is_sensitive',
                'duration_ms',
            )
        }),
        ('Data & Changes', {
            'fields': (
                'details_display',
                'changes_display',
                'metadata',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Audit logs should not be manually created."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Audit logs should not be deleted."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Audit logs should be read-only."""
        return False
    
    # Custom display methods
    
    def actor_display(self, obj):
        """Display actor information."""
        if obj.actor_user_id:
            return format_html(
                '<strong>👤 {}</strong>',
                obj.get_actor_display()
            )
        return format_html(
            '<em>🤖 {}</em>',
            obj.actor_type.title()
        )
    actor_display.short_description = 'Actor'
    
    def action_badge(self, obj):
        """Display action with colored badge."""
        colors = {
            'create': 'green',
            'update': 'blue',
            'delete': 'red',
            'view': 'gray',
            'login': 'purple',
            'logout': 'orange',
        }
        
        # Find color based on action content
        color = 'gray'
        for action_type, action_color in colors.items():
            if action_type in obj.action.lower():
                color = action_color
                break
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            obj.action
        )
    action_badge.short_description = 'Action'
    
    def entity_info(self, obj):
        """Display entity information."""
        if obj.entity_type:
            return format_html(
                '<strong>{}</strong><br/><small>{}</small>',
                obj.entity_type,
                obj.entity_name or str(obj.entity_id)[:8] + '...' if obj.entity_id else 'N/A'
            )
        return '—'
    entity_info.short_description = 'Entity'
    
    def outcome_badge(self, obj):
        """Display outcome with colored badge."""
        colors = {
            'success': 'green',
            'failure': 'red',
            'error': 'red',
            'denied': 'orange',
        }
        color = colors.get(obj.outcome, 'gray')
        
        icon = '✓' if obj.outcome == 'success' else '✗'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.outcome.title()
        )
    outcome_badge.short_description = 'Outcome'
    
    def risk_badge(self, obj):
        """Display risk score with colored badge."""
        if obj.risk_score >= 70:
            color = 'red'
            level = 'HIGH'
        elif obj.risk_score >= 40:
            color = 'orange'
            level = 'MEDIUM'
        else:
            color = 'green'
            level = 'LOW'
        
        sensitive_indicator = ' 🔒' if obj.is_sensitive else ''
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} ({}){}</span>',
            color,
            level,
            obj.risk_score,
            sensitive_indicator
        )
    risk_badge.short_description = 'Risk'
    
    def organization_link(self, obj):
        """Display organization with link."""
        if obj.organization_id:
            try:
                from apps.organizations.models import Organization
                org = Organization.objects.get(id=obj.organization_id)
                url = reverse('admin:organizations_organization_change', args=[org.id])
                return format_html(
                    '<a href="{}">{}</a>',
                    url,
                    org.name
                )
            except:
                return str(obj.organization_id)[:8] + '...'
        return '—'
    organization_link.short_description = 'Organization'
    
    # Detailed display methods for readonly fields
    
    def actor_display_detailed(self, obj):
        """Detailed actor display for admin form."""
        return obj.get_actor_display()
    actor_display_detailed.short_description = 'Actor Details'
    
    def entity_display(self, obj):
        """Detailed entity display."""
        if not obj.entity_type:
            return 'No entity'
        
        info = f"Type: {obj.entity_type}"
        if obj.entity_id:
            info += f"\nID: {obj.entity_id}"
        if obj.entity_name:
            info += f"\nName: {obj.entity_name}"
        
        return format_html('<pre>{}</pre>', info)
    entity_display.short_description = 'Entity Details'
    
    def request_info(self, obj):
        """Display request information."""
        info_parts = []
        
        if obj.ip_address:
            info_parts.append(f"IP: {obj.ip_address}")
        
        if obj.user_agent:
            # Truncate long user agents
            ua = obj.user_agent[:100] + '...' if len(obj.user_agent) > 100 else obj.user_agent
            info_parts.append(f"User Agent: {ua}")
        
        if obj.session_id:
            info_parts.append(f"Session: {obj.session_id}")
        
        if obj.duration_ms:
            info_parts.append(f"Duration: {obj.duration_ms}ms")
        
        return format_html('<pre>{}</pre>', '\n'.join(info_parts)) if info_parts else '—'
    request_info.short_description = 'Request Information'
    
    def changes_display(self, obj):
        """Display changes in readable format."""
        if not obj.changes:
            return '—'
        
        try:
            import json
            formatted = json.dumps(obj.changes, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except:
            return str(obj.changes)
    changes_display.short_description = 'Changes'
    
    def details_display(self, obj):
        """Display details in readable format."""
        if not obj.details:
            return '—'
        
        try:
            import json
            formatted = json.dumps(obj.details, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except:
            return str(obj.details)
    details_display.short_description = 'Details'
    
    def get_queryset(self, request):
        """Optimize queryset for admin interface."""
        return super().get_queryset(request).select_related()
    
    # Custom actions
    actions = ['export_selected_logs']
    
    def export_selected_logs(self, request, queryset):
        """Export selected audit logs to JSON."""
        # TODO: Implement audit log export functionality
        count = queryset.count()
        self.message_user(
            request,
            f'Export functionality for {count} audit log(s) will be implemented.'
        )
    export_selected_logs.short_description = "Export selected audit logs"