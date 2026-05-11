"""
CRM Django Admin Configuration for ArNet Platform.

This module configures the Django admin interface for CRM models with:
1. Multi-tenant filtering (users only see their organization's data)
2. Optimized list views with filtering and search
3. Custom form layouts for better user experience
4. Read-only fields for audit trails
5. Bulk operations for efficiency

Key Principles:
1. ALWAYS filter by organization (tenant isolation)
2. Provide useful search and filtering options
3. Show relationships clearly (customer -> subscriptions)
4. Make audit information visible but read-only
5. Prevent accidental data corruption

Why customize Django Admin?
- Default admin doesn't understand multi-tenancy
- CRM users need specific workflows and views
- Performance optimization with select_related/prefetch_related
- Business-specific filtering and search options
"""

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.urls import reverse
from typing import Optional

from .models import Customer, Subscription


# =============================================================================
# CUSTOM ADMIN BASE CLASSES
# =============================================================================

class TenantAwareAdminMixin:
    """
    Mixin to provide tenant-aware filtering for admin interfaces.
    
    This ensures that admin users only see data belonging to their organization.
    Think of this as a "security filter" that automatically applies to all admin views.
    """
    
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """
        Filter queryset to only show data for the user's organization.
        
        This is our security boundary - without this, admin users could
        potentially see data from other organizations.
        """
        qs = super().get_queryset(request)
        
        # Only apply filtering if user has an organization
        # (superusers might not have an organization assigned)
        if hasattr(request.user, 'organization_id') and request.user.organization_id:
            qs = qs.filter(organization_id=request.user.organization_id)
        
        return qs
    
    def save_model(self, request: HttpRequest, obj, form, change: bool):
        """
        Automatically set organization when saving through admin.
        
        This ensures new records are always assigned to the correct organization.
        """
        if not change and hasattr(obj, 'organization_id') and not obj.organization_id:
            # For new objects, set the organization from the current user
            if hasattr(request.user, 'organization_id'):
                obj.organization_id = request.user.organization_id
        
        super().save_model(request, obj, form, change)


# =============================================================================
# CUSTOMER ADMIN
# =============================================================================

@admin.register(Customer)
class CustomerAdmin(TenantAwareAdminMixin, admin.ModelAdmin):
    """
    Admin interface for Customer model.
    
    Provides a comprehensive view of customers with:
    - List view with key information and filtering
    - Detail view with organized form layout
    - Search functionality across multiple fields
    - Bulk operations for common tasks
    """
    
    # List view configuration
    list_display = [
        'name',
        'email', 
        'status',
        'subscription_count',
        'document_id',
        'phone',
        'created_at',
        'updated_at'
    ]
    
    list_filter = [
        'status',
        'created_at',
        'updated_at',
        # Custom filter for customers with/without subscriptions
        ('subscriptions', admin.RelatedOnlyFieldListFilter),
    ]
    
    search_fields = [
        'name',
        'email',
        'document_id',
        'phone'
    ]
    
    # Ordering (most recent first)
    ordering = ['-created_at']
    
    # Pagination
    list_per_page = 25
    
    # Detail view configuration
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'email', 'phone', 'document_id')
        }),
        ('Status & Classification', {
            'fields': ('status', 'tags')
        }),
        ('System Information', {
            'fields': ('id', 'organization', 'created_at', 'updated_at'),
            'classes': ('collapse',),  # Collapsible section
        }),
    )
    
    readonly_fields = [
        'id', 
        'created_at', 
        'updated_at',
        'subscription_count'
    ]
    
    # Performance optimization
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """
        Optimize queryset with related data loading.
        
        This prevents N+1 queries when displaying the list view.
        """
        qs = super().get_queryset(request)
        return qs.select_related('organization').prefetch_related('subscriptions')
    
    def subscription_count(self, obj: Customer) -> int:
        """
        Display count of customer subscriptions in list view.
        
        This gives a quick overview of customer engagement.
        """
        return obj.subscriptions.count()
    subscription_count.short_description = 'Subscriptions'
    subscription_count.admin_order_field = 'subscriptions__count'
    
    # Custom actions
    actions = ['mark_as_active', 'mark_as_inactive', 'mark_as_lead']
    
    def mark_as_active(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark customers as active."""
        updated = queryset.update(status=Customer.Status.ACTIVE)
        self.message_user(request, f'{updated} customers marked as active.')
    mark_as_active.short_description = "Mark selected customers as active"
    
    def mark_as_inactive(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark customers as inactive."""
        updated = queryset.update(status=Customer.Status.INACTIVE)
        self.message_user(request, f'{updated} customers marked as inactive.')
    mark_as_inactive.short_description = "Mark selected customers as inactive"
    
    def mark_as_lead(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark customers as leads."""
        updated = queryset.update(status=Customer.Status.LEAD)
        self.message_user(request, f'{updated} customers marked as leads.')
    mark_as_lead.short_description = "Mark selected customers as leads"


# =============================================================================
# SUBSCRIPTION ADMIN
# =============================================================================

@admin.register(Subscription)
class SubscriptionAdmin(TenantAwareAdminMixin, admin.ModelAdmin):
    """
    Admin interface for Subscription model.
    
    Provides subscription management with:
    - Clear relationship to customers
    - Status-based filtering and actions
    - Expiration date tracking
    - Billing period information
    """
    
    # List view configuration
    list_display = [
        'customer_name_link',
        'plan_name',
        'status',
        'current_period_end',
        'is_expiring_soon',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'plan_name',
        'current_period_end',
        'created_at',
    ]
    
    search_fields = [
        'customer__name',
        'customer__email',
        'plan_name'
    ]
    
    ordering = ['-created_at']
    list_per_page = 25
    
    # Detail view configuration
    fieldsets = (
        ('Subscription Details', {
            'fields': ('customer', 'plan_name', 'status')
        }),
        ('Billing Information', {
            'fields': ('current_period_end',)
        }),
        ('System Information', {
            'fields': ('id', 'organization', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = [
        'id',
        'created_at', 
        'updated_at'
    ]
    
    # Performance optimization
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset with customer data loading."""
        qs = super().get_queryset(request)
        return qs.select_related('customer', 'organization')
    
    def customer_name_link(self, obj: Subscription) -> str:
        """
        Display customer name as a clickable link to customer detail.
        
        This creates easy navigation between related records.
        """
        url = reverse('admin:crm_customer_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.name)
    customer_name_link.short_description = 'Customer'
    customer_name_link.admin_order_field = 'customer__name'
    
    def is_expiring_soon(self, obj: Subscription) -> bool:
        """
        Display if subscription is expiring soon.
        
        Helps identify subscriptions that need attention.
        """
        return obj.is_expiring_soon
    is_expiring_soon.short_description = 'Expiring Soon?'
    is_expiring_soon.boolean = True  # Shows as checkmark/X icon
    
    # Custom filters
    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        """
        Filter foreign key choices based on organization.
        
        When creating/editing subscriptions, only show customers
        from the same organization in the dropdown.
        """
        if db_field.name == "customer":
            if hasattr(request.user, 'organization_id') and request.user.organization_id:
                kwargs["queryset"] = Customer.objects.filter(
                    organization_id=request.user.organization_id
                )
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    # Bulk actions
    actions = ['mark_as_active', 'mark_as_past_due', 'cancel_subscriptions']
    
    def mark_as_active(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark subscriptions as active."""
        updated = queryset.update(status=Subscription.Status.ACTIVE)
        self.message_user(request, f'{updated} subscriptions marked as active.')
    mark_as_active.short_description = "Mark selected subscriptions as active"
    
    def mark_as_past_due(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to mark subscriptions as past due."""
        updated = queryset.update(status=Subscription.Status.PAST_DUE)
        self.message_user(request, f'{updated} subscriptions marked as past due.')
    mark_as_past_due.short_description = "Mark selected subscriptions as past due"
    
    def cancel_subscriptions(self, request: HttpRequest, queryset: QuerySet):
        """Bulk action to cancel subscriptions."""
        updated = queryset.update(status=Subscription.Status.CANCELED)
        self.message_user(request, f'{updated} subscriptions canceled.')
    cancel_subscriptions.short_description = "Cancel selected subscriptions"


# =============================================================================
# INLINE ADMIN CLASSES
# =============================================================================

class SubscriptionInline(admin.TabularInline):
    """
    Inline admin for showing subscriptions within customer detail view.
    
    This allows admin users to see and manage customer subscriptions
    directly from the customer page, providing better workflow.
    """
    model = Subscription
    extra = 0  # Don't show empty forms by default
    readonly_fields = ['created_at', 'updated_at']
    
    # Show essential fields only
    fields = [
        'plan_name',
        'status', 
        'current_period_end',
        'created_at'
    ]
    
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize inline queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('customer')


# Add inline to Customer admin
CustomerAdmin.inlines = [SubscriptionInline]


# =============================================================================
# ADMIN SITE CUSTOMIZATION
# =============================================================================

# Customize admin site headers for CRM section
admin.site.site_header = "ArNet CRM Administration"
admin.site.site_title = "ArNet CRM Admin"
admin.site.index_title = "Customer Relationship Management"

# Custom admin site configuration
class CRMAdminConfig:
    """
    Configuration class for CRM admin customizations.
    
    This could be extended to include:
    - Custom dashboard widgets
    - Analytics views
    - Export functionality
    - Advanced filtering options
    """
    pass