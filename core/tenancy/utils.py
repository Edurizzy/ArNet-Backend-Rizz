"""
Utility functions and decorators for tenant-aware operations.
"""

import functools
import uuid
from typing import Optional, Type, Any
from django.db import models
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.organizations.models import Organization


def with_tenant_context(func):
    """
    Decorator to ensure a function has access to tenant context.
    
    Usage:
    @with_tenant_context
    def my_view(request):
        # request.tenant is guaranteed to exist
        pass
    """
    @functools.wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not hasattr(request, 'tenant'):
            from .middleware import TenantContext
            request.tenant = TenantContext()
        
        return func(request, *args, **kwargs)
    
    return wrapper


def require_organization(func):
    """
    Decorator to require organization context for a view.
    
    Usage:
    @require_organization
    def my_view(request):
        # request.tenant.organization is guaranteed to exist
        pass
    """
    @functools.wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not hasattr(request, 'tenant') or not request.tenant.organization:
            raise PermissionDenied("Organization context is required")
        
        return func(request, *args, **kwargs)
    
    return wrapper


def superuser_or_organization_admin(func):
    """
    Decorator to require superuser or organization admin privileges.
    """
    @functools.wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required")
        
        if request.user.is_superuser:
            return func(request, *args, **kwargs)
        
        if hasattr(request, 'tenant') and request.tenant.organization:
            if request.user.is_organization_admin():
                return func(request, *args, **kwargs)
        
        raise PermissionDenied("Superuser or organization admin required")
    
    return wrapper


class TenantQuerySetMixin:
    """
    Mixin for QuerySets to add tenant-aware methods.
    """
    
    def for_tenant(self, organization: Organization):
        """Filter queryset for a specific tenant."""
        return self.filter(organization=organization)
    
    def for_request_tenant(self, request: HttpRequest):
        """Filter queryset for the current request's tenant."""
        from .middleware import get_current_organization
        
        organization = get_current_organization(request)
        if not organization:
            return self.none()
        
        return self.for_tenant(organization)


class TenantManagerMixin:
    """
    Mixin for Model Managers to add tenant-aware methods.
    """
    
    def for_tenant(self, organization: Organization):
        """Get queryset for a specific tenant."""
        return self.get_queryset().for_tenant(organization)
    
    def for_request_tenant(self, request: HttpRequest):
        """Get queryset for the current request's tenant."""
        return self.get_queryset().for_request_tenant(request)


def create_tenant_aware_manager(base_manager_class: Type[models.Manager]):
    """
    Factory function to create tenant-aware manager classes.
    
    Usage:
    class MyModel(TenantAwareModel):
        objects = create_tenant_aware_manager(models.Manager)()
    """
    class TenantAwareManager(TenantManagerMixin, base_manager_class):
        def get_queryset(self):
            queryset = super().get_queryset()
            # Add tenant-aware queryset methods
            for method_name in ['for_tenant', 'for_request_tenant']:
                if not hasattr(queryset, method_name):
                    setattr(
                        queryset, 
                        method_name, 
                        getattr(TenantQuerySetMixin, method_name).__get__(queryset, type(queryset))
                    )
            return queryset
    
    return TenantAwareManager


def validate_tenant_access(request: HttpRequest, obj: Any) -> bool:
    """
    Validate that the current user can access an object based on tenant rules.
    
    Args:
        request: The HTTP request
        obj: The object to check access for
    
    Returns:
        bool: True if access is allowed, False otherwise
    """
    if not hasattr(request, 'tenant'):
        return False
    
    tenant = request.tenant
    
    # Superusers can access everything
    if tenant.is_superuser:
        return True
    
    # No organization means no access to tenant-scoped objects
    if not tenant.organization:
        return False
    
    # Check if object has organization field
    if hasattr(obj, 'organization') and obj.organization:
        return obj.organization.id == tenant.organization.id
    
    # Objects without organization field are accessible to authenticated users
    return True


def get_tenant_scoped_queryset(
    model_class: Type[models.Model], 
    request: HttpRequest,
    base_queryset: Optional[models.QuerySet] = None
) -> models.QuerySet:
    """
    Get a queryset scoped to the current tenant.
    
    Args:
        model_class: The model class to query
        request: The HTTP request with tenant context
        base_queryset: Optional base queryset to filter
    
    Returns:
        QuerySet filtered by tenant context
    """
    from .middleware import get_current_tenant
    
    # Use provided queryset or default manager
    if base_queryset is not None:
        queryset = base_queryset
    else:
        queryset = model_class.objects.all()
    
    tenant = get_current_tenant(request)
    if not tenant:
        return queryset.none()
    
    # Superusers see everything
    if tenant.is_superuser:
        return queryset
    
    # Users without organization see nothing
    if not tenant.organization:
        return queryset.none()
    
    # Filter by organization if model supports it
    if hasattr(model_class, 'organization'):
        return queryset.filter(organization=tenant.organization)
    
    # Model doesn't have organization field, return full queryset
    return queryset


def ensure_tenant_ownership(request: HttpRequest, obj: Any):
    """
    Ensure that an object belongs to the current tenant.
    Raises PermissionDenied if not.
    
    Args:
        request: The HTTP request
        obj: The object to check
    
    Raises:
        PermissionDenied: If object doesn't belong to current tenant
    """
    if not validate_tenant_access(request, obj):
        raise PermissionDenied("Access denied: Object does not belong to your organization")


class TenantAwareModelMixin:
    """
    Mixin for models to add tenant-aware methods.
    
    Add this to models that need tenant-specific behavior.
    """
    
    def belongs_to_tenant(self, organization: Organization) -> bool:
        """Check if this object belongs to a specific tenant."""
        if hasattr(self, 'organization') and self.organization:
            return self.organization.id == organization.id
        return False
    
    def ensure_tenant_ownership(self, request: HttpRequest):
        """Ensure this object belongs to the request's tenant."""
        ensure_tenant_ownership(request, self)
    
    @classmethod
    def for_tenant(cls, organization: Organization):
        """Get all instances for a specific tenant."""
        if hasattr(cls, 'organization'):
            return cls.objects.filter(organization=organization)
        return cls.objects.all()
    
    @classmethod
    def for_request_tenant(cls, request: HttpRequest):
        """Get all instances for the request's tenant."""
        return get_tenant_scoped_queryset(cls, request)


def get_or_create_for_tenant(
    model_class: Type[models.Model],
    organization: Organization,
    defaults: Optional[dict] = None,
    **kwargs
) -> tuple[Any, bool]:
    """
    Get or create a model instance for a specific tenant.
    
    Similar to Model.objects.get_or_create but ensures tenant scoping.
    
    Args:
        model_class: The model class
        organization: The tenant organization
        defaults: Default values for creation
        **kwargs: Lookup parameters
    
    Returns:
        Tuple of (instance, created)
    """
    # Add organization to lookup parameters
    if hasattr(model_class, 'organization'):
        kwargs['organization'] = organization
    
    # Add organization to defaults if not present
    if defaults is None:
        defaults = {}
    
    if hasattr(model_class, 'organization') and 'organization' not in defaults:
        defaults['organization'] = organization
    
    return model_class.objects.get_or_create(defaults=defaults, **kwargs)