"""
Common admin configurations for ArNet platform.

This module provides base admin classes that can be inherited
by other apps to ensure consistent admin interface behavior.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe


class BaseModelAdmin(admin.ModelAdmin):
    """
    Base admin class for all models.
    
    Provides common functionality like:
    - Readonly timestamp fields
    - UUID display formatting
    - Basic list display configuration
    """
    
    readonly_fields = ('id', 'created_at', 'updated_at')
    list_per_page = 25
    show_full_result_count = False
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make ID and timestamp fields readonly for all admins.
        """
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if hasattr(self.model, 'created_at'):
            readonly_fields.extend(['created_at', 'updated_at'])
        return readonly_fields


class TenantAwareAdmin(BaseModelAdmin):
    """
    Base admin class for tenant-aware models.
    
    Provides tenant-specific functionality and filtering.
    """
    
    list_filter = ('organization', 'created_at')
    list_display_links = ('id',)
    
    def get_queryset(self, request):
        """
        Filter queryset based on user's organization if needed.
        Superusers can see all data.
        """
        queryset = super().get_queryset(request)
        
        if not request.user.is_superuser and hasattr(request.user, 'organization'):
            # Regular users only see their organization's data
            queryset = queryset.filter(organization=request.user.organization)
        
        return queryset
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Limit organization choices for non-superusers.
        """
        if db_field.name == "organization" and not request.user.is_superuser:
            if hasattr(request.user, 'organization') and request.user.organization:
                kwargs["queryset"] = kwargs.get("queryset", db_field.related_model.objects).filter(
                    id=request.user.organization.id
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SoftDeleteAdmin(BaseModelAdmin):
    """
    Admin class for models with soft delete functionality.
    """
    
    list_filter = ('deleted_at', 'created_at')
    
    def get_queryset(self, request):
        """
        Show both active and soft-deleted records in admin.
        """
        return self.model.all_objects.get_queryset()
    
    def delete_model(self, request, obj):
        """
        Perform soft delete instead of hard delete.
        """
        obj.delete()  # This will call the soft delete method
    
    def delete_queryset(self, request, queryset):
        """
        Soft delete multiple objects.
        """
        for obj in queryset:
            obj.delete()
    
    actions = ['restore_selected', 'hard_delete_selected']
    
    def restore_selected(self, request, queryset):
        """
        Action to restore soft-deleted records.
        """
        restored_count = 0
        for obj in queryset:
            if obj.is_deleted:
                obj.restore()
                restored_count += 1
        
        self.message_user(
            request,
            f'Successfully restored {restored_count} record(s).'
        )
    restore_selected.short_description = "Restore selected records"
    
    def hard_delete_selected(self, request, queryset):
        """
        Action to permanently delete records.
        Use with extreme caution!
        """
        count = queryset.count()
        for obj in queryset:
            obj.hard_delete()
        
        self.message_user(
            request,
            f'Permanently deleted {count} record(s).'
        )
    hard_delete_selected.short_description = "Permanently delete selected records"
    
    def deleted_status(self, obj):
        """
        Display deleted status with visual indicator.
        """
        if obj.is_deleted:
            return format_html(
                '<span style="color: red;">🗑️ Deleted</span>'
            )
        return format_html(
            '<span style="color: green;">✓ Active</span>'
        )
    deleted_status.short_description = 'Status'


class TenantSoftDeleteAdmin(TenantAwareAdmin, SoftDeleteAdmin):
    """
    Combined admin for tenant-aware models with soft delete.
    
    This is the most comprehensive admin class that most of our
    business models will use.
    """
    
    list_filter = ('organization', 'deleted_at', 'created_at')
    
    def get_list_display(self, request):
        """
        Dynamically set list display to include common fields.
        """
        list_display = list(super().get_list_display(request) or [])
        
        # Add common fields if they exist on the model
        common_fields = ['organization', 'deleted_status', 'created_at']
        for field in common_fields:
            if (hasattr(self.model, field.replace('_status', '')) and 
                field not in list_display):
                list_display.append(field)
        
        return list_display or ['id']