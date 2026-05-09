"""
Tenancy middleware for ArNet platform.

This middleware automatically resolves the current tenant (organization)
from JWT claims and attaches it to the request object. This enables
automatic tenant scoping throughout the application.
"""

import uuid
import logging
from typing import Optional

from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.organizations.models import Organization

logger = logging.getLogger(__name__)


class TenantContext:
    """
    Container for tenant-related context information.
    
    Think of this as a "context card" that travels with each request,
    telling every part of our system which organization's data to work with.
    """
    
    def __init__(
        self, 
        organization: Optional[Organization] = None,
        user_id: Optional[uuid.UUID] = None,
        is_superuser: bool = False
    ):
        self.organization = organization
        self.user_id = user_id
        self.is_superuser = is_superuser
    
    @property
    def organization_id(self) -> Optional[uuid.UUID]:
        """Get organization ID if available."""
        return self.organization.id if self.organization else None
    
    @property
    def organization_slug(self) -> Optional[str]:
        """Get organization slug if available."""
        return self.organization.slug if self.organization else None
    
    def __str__(self):
        if self.organization:
            return f"TenantContext(org={self.organization.slug}, user={self.user_id})"
        return f"TenantContext(no_org, user={self.user_id})"


class TenancyMiddleware(MiddlewareMixin):
    """
    Middleware to resolve and attach tenant context to requests.
    
    This middleware works like a "smart receptionist" at the front desk
    of our API. It looks at each incoming request, figures out which
    organization the user belongs to, and makes that information
    available throughout the request lifecycle.
    
    The process:
    1. Extract JWT token from request
    2. Parse organization claims from token
    3. Resolve organization from database
    4. Attach tenant context to request
    5. Handle errors gracefully
    """
    
    def __init__(self, get_response):
        """
        Initialize the middleware.
        """
        self.get_response = get_response
        self.jwt_authentication = JWTAuthentication()
        super().__init__(get_response)
    
    def process_request(self, request: HttpRequest):
        """
        Process incoming request to resolve tenant context.
        
        This method runs before every view, ensuring that tenant
        context is available for all subsequent processing.
        """
        # Initialize default tenant context
        request.tenant = TenantContext()
        
        try:
            # Try to resolve tenant from JWT token
            self._resolve_tenant_from_jwt(request)
        except Exception as e:
            logger.warning(f"Failed to resolve tenant from JWT: {e}")
            # Continue with empty tenant context
            pass
        
        # Log tenant resolution for debugging
        if hasattr(request, 'user') and request.user.is_authenticated:
            logger.debug(f"Resolved tenant context: {request.tenant}")
    
    def _resolve_tenant_from_jwt(self, request: HttpRequest):
        """
        Resolve tenant information from JWT token claims.
        
        This method extracts the JWT token from the request,
        validates it, and pulls out the organization information.
        """
        # Try to authenticate using JWT
        try:
            auth_result = self.jwt_authentication.authenticate(request)
            
            if auth_result is None:
                # No JWT token found, use anonymous context
                return
            
            user, validated_token = auth_result
            
            # Extract organization claims from token
            org_id_str = validated_token.get('org_id')
            org_slug = validated_token.get('org_slug')
            user_id_str = validated_token.get('user_id')
            is_superuser = validated_token.get('is_superuser', False)
            
            # Convert string IDs to UUIDs
            org_id = None
            user_id = None
            
            if org_id_str:
                try:
                    org_id = uuid.UUID(org_id_str)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid org_id in JWT token: {org_id_str}")
            
            if user_id_str:
                try:
                    user_id = uuid.UUID(user_id_str)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid user_id in JWT token: {user_id_str}")
            
            # Resolve organization from database
            organization = None
            if org_id:
                try:
                    organization = Organization.objects.get(
                        id=org_id,
                        is_active=True
                    )
                except Organization.DoesNotExist:
                    logger.warning(f"Organization not found or inactive: {org_id}")
                    # Organization might have been deactivated since token was issued
                    pass
            
            # Create tenant context
            request.tenant = TenantContext(
                organization=organization,
                user_id=user_id,
                is_superuser=is_superuser
            )
            
            # Attach user to request for compatibility
            request.user = user
            
        except (InvalidToken, TokenError) as e:
            logger.debug(f"JWT token validation failed: {e}")
            # Invalid token, continue with anonymous context
            request.user = AnonymousUser()
        
        except Exception as e:
            logger.error(f"Unexpected error in tenant resolution: {e}")
            # Fallback to anonymous context
            request.user = AnonymousUser()
    
    def process_response(self, request: HttpRequest, response):
        """
        Process outgoing response.
        
        Add tenant-related headers for debugging and monitoring.
        """
        if hasattr(request, 'tenant') and request.tenant.organization:
            # Add tenant information to response headers for debugging
            response['X-Tenant-Org'] = request.tenant.organization_slug
            response['X-Tenant-ID'] = str(request.tenant.organization_id)
        
        return response


class TenantScopingMixin:
    """
    Mixin for views that need automatic tenant scoping.
    
    This mixin provides utilities for views to automatically
    filter querysets based on the current tenant context.
    """
    
    def get_tenant_filtered_queryset(self, queryset, user=None):
        """
        Filter queryset based on current tenant context.
        
        This is like adding an automatic "WHERE organization_id = ?" 
        clause to every database query.
        """
        if not hasattr(self.request, 'tenant'):
            return queryset.none()
        
        tenant = self.request.tenant
        
        # Superusers can see all data
        if tenant.is_superuser:
            return queryset
        
        # Users without organization see no data
        if not tenant.organization:
            return queryset.none()
        
        # Filter by organization
        return queryset.filter(organization=tenant.organization)
    
    def check_tenant_permission(self, obj):
        """
        Check if user has permission to access an object based on tenant.
        
        This is like checking if someone's key card works for a specific door.
        """
        if not hasattr(self.request, 'tenant'):
            return False
        
        tenant = self.request.tenant
        
        # Superusers can access everything
        if tenant.is_superuser:
            return True
        
        # Check if object belongs to user's organization
        if hasattr(obj, 'organization') and obj.organization:
            return obj.organization.id == tenant.organization_id
        
        return False


# Utility functions for tenant context

def get_current_tenant(request: HttpRequest) -> Optional[TenantContext]:
    """
    Get current tenant context from request.
    
    Usage in views:
    tenant = get_current_tenant(request)
    if tenant.organization:
        # Work with tenant data
    """
    return getattr(request, 'tenant', None)


def get_current_organization(request: HttpRequest) -> Optional[Organization]:
    """
    Get current organization from request.
    
    Usage in views:
    org = get_current_organization(request)
    if org:
        # Work with organization
    """
    tenant = get_current_tenant(request)
    return tenant.organization if tenant else None


def require_tenant_organization(request: HttpRequest) -> Organization:
    """
    Get current organization or raise exception.
    
    Usage in views where organization is required:
    org = require_tenant_organization(request)
    """
    organization = get_current_organization(request)
    if not organization:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Organization context is required for this operation")
    
    return organization


def is_superuser_request(request: HttpRequest) -> bool:
    """
    Check if current request is from a superuser.
    """
    tenant = get_current_tenant(request)
    return tenant.is_superuser if tenant else False


class TenantAwareViewMixin:
    """
    View mixin that automatically handles tenant scoping.
    
    Use this mixin in your views to automatically filter
    data based on the current tenant context.
    """
    
    def get_queryset(self):
        """
        Get queryset filtered by current tenant.
        """
        queryset = super().get_queryset()
        
        # Get tenant context
        tenant = get_current_tenant(self.request)
        if not tenant:
            return queryset.none()
        
        # Superusers see everything
        if tenant.is_superuser:
            return queryset
        
        # Users without organization see nothing
        if not tenant.organization:
            return queryset.none()
        
        # Filter by organization if model has organization field
        model = queryset.model
        if hasattr(model, 'organization'):
            return queryset.filter(organization=tenant.organization)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Automatically set organization when creating objects.
        """
        tenant = get_current_tenant(self.request)
        
        if tenant and tenant.organization:
            # Automatically set organization for new objects
            if hasattr(serializer.Meta.model, 'organization'):
                serializer.save(organization=tenant.organization)
                return
        
        # Fallback to default behavior
        super().perform_create(serializer)