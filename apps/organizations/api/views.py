"""
API views for Organizations app.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from ..models import Organization
from .serializers import (
    OrganizationSerializer,
    OrganizationCreateSerializer,
    OrganizationUpdateSerializer,
    OrganizationDetailSerializer,
)


@extend_schema_view(
    list=extend_schema(
        description="List organizations",
        summary="Get list of organizations"
    ),
    retrieve=extend_schema(
        description="Get organization details",
        summary="Retrieve organization by ID"
    ),
    create=extend_schema(
        description="Create new organization",
        summary="Create organization"
    ),
    update=extend_schema(
        description="Update organization",
        summary="Update organization details"
    ),
    partial_update=extend_schema(
        description="Partially update organization",
        summary="Partial organization update"
    ),
    destroy=extend_schema(
        description="Delete organization (soft delete)",
        summary="Delete organization"
    ),
)
class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Organization management.
    
    This viewset provides CRUD operations for organizations with
    proper tenant scoping and permission checks.
    """
    
    queryset = Organization.objects.active()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """
        Return appropriate serializer class based on action.
        """
        if self.action == 'create':
            return OrganizationCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OrganizationUpdateSerializer
        elif self.action == 'retrieve':
            return OrganizationDetailSerializer
        return OrganizationSerializer
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        # Superusers can see all organizations
        if user.is_superuser:
            return Organization.objects.all()
        
        # Regular users can only see their own organization
        if hasattr(user, 'organization') and user.organization:
            return Organization.objects.filter(id=user.organization.id)
        
        # Users without organization see none
        return Organization.objects.none()
    
    def perform_create(self, serializer):
        """
        Handle organization creation.
        """
        # Only superusers can create organizations for now
        if not self.request.user.is_superuser:
            raise PermissionError("Only superusers can create organizations")
        
        serializer.save()
    
    def perform_update(self, serializer):
        """
        Handle organization updates.
        """
        # Users can only update their own organization
        organization = self.get_object()
        user = self.request.user
        
        if not user.is_superuser:
            if not hasattr(user, 'organization') or user.organization != organization:
                raise PermissionError("You can only update your own organization")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """
        Perform soft delete on organization.
        """
        # Only superusers can delete organizations
        if not self.request.user.is_superuser:
            raise PermissionError("Only superusers can delete organizations")
        
        instance.delete()  # This will be a soft delete
    
    @extend_schema(
        description="Get current user's organization",
        summary="Get my organization",
        responses={200: OrganizationDetailSerializer}
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user's organization.
        """
        user = request.user
        
        if not hasattr(user, 'organization') or not user.organization:
            return Response(
                {'detail': 'User is not associated with any organization'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = OrganizationDetailSerializer(user.organization)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get organization features",
        summary="Get organization features",
        responses={200: dict}
    )
    @action(detail=True, methods=['get'])
    def features(self, request, pk=None):
        """
        Get organization features and capabilities.
        """
        organization = self.get_object()
        
        return Response({
            'features': organization.features,
            'subscription_tier': organization.subscription_tier,
            'limits': organization.limits,
            'usage': {
                'users': organization.get_user_count(),
                'can_add_user': organization.can_add_user(),
            }
        })
    
    @extend_schema(
        description="Check organization usage limits",
        summary="Get usage statistics",
        responses={200: dict}
    )
    @action(detail=True, methods=['get'])
    def usage(self, request, pk=None):
        """
        Get detailed usage statistics for the organization.
        """
        organization = self.get_object()
        
        usage_data = {
            'users': {
                'current': organization.get_user_count(),
                'limit': organization.get_limit('max_users'),
                'can_add_more': organization.can_add_user(),
            },
            'storage': {
                'current_mb': 0,  # TODO: Implement storage tracking
                'limit_mb': organization.get_limit('max_storage_mb'),
            },
            'api_calls': {
                'current_month': 0,  # TODO: Implement API call tracking
                'limit_per_month': organization.get_limit('max_api_calls_per_month'),
            },
            'automations': {
                'current': 0,  # TODO: Implement automation counting
                'limit': organization.get_limit('max_automations'),
            }
        }
        
        return Response(usage_data)