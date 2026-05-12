"""
Admin interface for IAM app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.common.admin import TenantSoftDeleteAdmin
from .models import User


@admin.register(User)
class UserAdmin(TenantSoftDeleteAdmin, BaseUserAdmin):
    """
    Admin interface for User model.
    """
    
    # Display configuration
    list_display = [
        'email',
        'display_name', 
        'organization',
        'status_badge',
        'is_active',
        'email_verified_badge',
        'last_login',
        'deleted_status',
        'created_at'
    ]

    list_display_links = ['email', 'display_name']
    
    list_filter = [
        'status',
        'is_active', 
        'is_staff', 
        'is_superuser',
        'email_verified',
        'organization',
        'deleted_at',
        'created_at'
    ]
    
    search_fields = [
        'email', 
        'first_name', 
        'last_name', 
        'display_name'
    ]
    
    readonly_fields = [
        'id',
        'last_login',
        'last_login_ip',
        'email_verified_at',
        'password_changed_at',
        'created_at',
        'updated_at',
        'deleted_at'
    ]
    
    ordering = ['email']
    
    # Fieldset configuration
    fieldsets = (
        (None, {
            'fields': ('id', 'email', 'password')
        }),
        (_('Personal info'), {
            'fields': (
                'first_name', 
                'last_name', 
                'display_name',
                'phone',
                'avatar'
            )
        }),
        (_('Organization'), {
            'fields': ('organization',)
        }),
        (_('Status & Permissions'), {
            'fields': (
                'status',
                'is_active',
                'is_staff',
                'is_superuser',
            )
        }),
        (_('Authentication'), {
            'fields': (
                'email_verified',
                'email_verified_at',
                'two_factor_enabled',
                'password_changed_at',
                'last_login',
                'last_login_ip',
            )
        }),
        (_('Preferences'), {
            'fields': (
                'timezone',
                'language',
                'preferences',
            ),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        (_('Important dates'), {
            'fields': (
                'created_at',
                'updated_at',
                'deleted_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 
                'password1', 
                'password2',
                'first_name',
                'last_name',
                'organization',
                'is_active',
                'is_staff',
            ),
        }),
    )
    
    # Custom display methods
    def status_badge(self, obj):
        """Display status with colored badge."""
        colors = {
            'active': 'green',
            'pending': 'orange',
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
    
    def email_verified_badge(self, obj):
        """Display email verification status."""
        if obj.email_verified:
            return format_html(
                '<span style="color: green;">✓ Verified</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Unverified</span>'
        )
    email_verified_badge.short_description = 'Email'
    
    # Actions
    actions = [
        'activate_users',
        'deactivate_users', 
        'verify_emails',
        'send_password_reset'
    ]
    
    def activate_users(self, request, queryset):
        """Activate selected users."""
        count = 0
        for user in queryset:
            if not user.is_active:
                user.activate()
                count += 1
        
        self.message_user(
            request,
            f'Successfully activated {count} user(s).'
        )
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        count = 0
        for user in queryset:
            if user.is_active and not user.is_superuser:
                user.deactivate()
                count += 1
        
        self.message_user(
            request,
            f'Successfully deactivated {count} user(s).'
        )
    deactivate_users.short_description = "Deactivate selected users"
    
    def verify_emails(self, request, queryset):
        """Mark emails as verified for selected users."""
        count = 0
        for user in queryset:
            if not user.email_verified:
                user.verify_email()
                count += 1
        
        self.message_user(
            request,
            f'Successfully verified {count} email(s).'
        )
    verify_emails.short_description = "Verify emails for selected users"
    
    def send_password_reset(self, request, queryset):
        """Send password reset emails to selected users."""
        # TODO: Implement password reset email sending
        count = queryset.count()
        self.message_user(
            request,
            f'Password reset emails will be sent to {count} user(s). (Feature not yet implemented)'
        )
    send_password_reset.short_description = "Send password reset emails"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('organization')