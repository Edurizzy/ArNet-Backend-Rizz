"""
Admin interface for Organizations app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.common.admin import BaseModelAdmin, SoftDeleteAdmin
from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(SoftDeleteAdmin):
    """
    Admin interface for Organization model.
    """
    
    list_display = [
        'name', 
        'slug', 
        'status_badge', 
        'subscription_tier', 
        'user_count_display',
        'is_active', 
        'deleted_status',
        'created_at'
    ]
    
    list_filter = [
        'subscription_tier', 
        'status', 
        'is_active', 
        'deleted_at',
        'created_at'
    ]
    
    search_fields = [
        'name', 
        'slug', 
        'admin_email', 
        'email_domains'
    ]
    
    readonly_fields = [
        'id', 
        'created_at', 
        'updated_at', 
        'user_count_display',
        'slug_preview'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id',
                'name',
                'slug',
                'slug_preview',
                'display_name',
                'description',
            )
        }),
        ('Contact Information', {
            'fields': (
                'admin_email',
                'website',
                'phone',
            )
        }),
        ('Address', {
            'fields': (
                'address_line_1',
                'address_line_2',
                'city',
                'state_province',
                'postal_code',
                'country',
            ),
            'classes': ('collapse',),
        }),
        ('Status & Subscription', {
            'fields': (
                'status',
                'is_active',
                'subscription_tier',
                'trial_ends_at',
            )
        }),
        ('Domain Configuration', {
            'fields': (
                'email_domains',
            ),
            'description': 'Comma-separated list of email domains for auto-user assignment.'
        }),
        ('Features & Limits', {
            'fields': (
                'features',
                'limits',
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': (
                'metadata',
            ),
            'classes': ('collapse',),
        }),
        ('System Information', {
            'fields': (
                'user_count_display',
                'created_at',
                'updated_at',
                'deleted_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    prepopulated_fields = {'slug': ('name',)}
    
    def status_badge(self, obj):
        """
        Display status with colored badge.
        """
        colors = {
            'active': 'green',
            'trial': 'orange',
            'suspended': 'red',
            'inactive': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def user_count_display(self, obj):
        """
        Display user count with link to users.
        """
        if obj.id:
            count = obj.get_user_count()
            max_users = obj.get_limit('max_users')
            
            if max_users == -1:
                limit_text = "unlimited"
            else:
                limit_text = f"{max_users}"
            
            return format_html(
                '<strong>{}</strong> / {} users',
                count,
                limit_text
            )
        return "N/A"
    user_count_display.short_description = 'Users'
    
    def slug_preview(self, obj):
        """
        Show how the slug will appear in URLs.
        """
        if obj.slug:
            return format_html(
                '<code>https://app.arnet.com/{}/</code>',
                obj.slug
            )
        return "Will be generated from name"
    slug_preview.short_description = 'URL Preview'
    
    def get_queryset(self, request):
        """
        Optimize queryset with select_related.
        """
        return super().get_queryset(request).prefetch_related()
    
    actions = ['activate_organizations', 'deactivate_organizations', 'reset_trial']
    
    def activate_organizations(self, request, queryset):
        """
        Activate selected organizations.
        """
        updated = queryset.update(is_active=True, status=Organization.Status.ACTIVE)
        self.message_user(
            request,
            f'Successfully activated {updated} organization(s).'
        )
    activate_organizations.short_description = "Activate selected organizations"
    
    def deactivate_organizations(self, request, queryset):
        """
        Deactivate selected organizations.
        """
        updated = queryset.update(is_active=False, status=Organization.Status.INACTIVE)
        self.message_user(
            request,
            f'Successfully deactivated {updated} organization(s).'
        )
    deactivate_organizations.short_description = "Deactivate selected organizations"
    
    def reset_trial(self, request, queryset):
        """
        Reset trial status for selected organizations.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        trial_end = timezone.now() + timedelta(days=14)  # 14-day trial
        
        updated = queryset.update(
            status=Organization.Status.TRIAL,
            trial_ends_at=trial_end
        )
        
        self.message_user(
            request,
            f'Successfully reset trial for {updated} organization(s).'
        )
    reset_trial.short_description = "Reset 14-day trial for selected organizations"