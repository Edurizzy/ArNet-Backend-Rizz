"""
API views for Audit app.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.tenancy.middleware import get_current_tenant
from ..models import AuditLog
from .serializers import (
    AuditLogSerializer,
    AuditLogDetailSerializer,
    AuditLogFilterSerializer
)


@extend_schema_view(
    list=extend_schema(
        description="List audit logs for the organization",
        summary="Get audit logs"
    ),
    retrieve=extend_schema(
        description="Get detailed audit log information",
        summary="Retrieve audit log"
    ),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing audit logs.
    
    This viewset provides read-only access to audit logs with
    automatic tenant scoping and comprehensive filtering options.
    
    Note: Audit logs are read-only by design - they cannot be
    created, updated, or deleted through the API.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    
    # Filtering options
    filterset_fields = [
        'action',
        'action_category',
        'entity_type',
        'outcome',
        'is_sensitive',
        'risk_score'
    ]
    
    # Ordering options
    ordering_fields = [
        'created_at',
        'risk_score',
        'duration_ms'
    ]
    ordering = ['-created_at']  # Default ordering
    
    # Search fields
    search_fields = [
        'action',
        'entity_type',
        'entity_name',
        'correlation_id'
    ]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions and tenant context.
        """
        # Get tenant context
        tenant = get_current_tenant(self.request)
        
        if not tenant:
            return AuditLog.objects.none()
        
        # Superusers can see all audit logs
        if tenant.is_superuser:
            queryset = AuditLog.objects.all()
        else:
            # Regular users can only see their organization's audit logs
            if not tenant.organization:
                return AuditLog.objects.none()
            
            queryset = AuditLog.objects.for_organization(tenant.organization.id)
        
        return queryset.select_related()
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.
        """
        if self.action == 'retrieve':
            return AuditLogDetailSerializer
        return AuditLogSerializer
    
    @extend_schema(
        description="Get security-relevant audit logs",
        summary="Get security logs",
        responses={200: AuditLogSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def security(self, request):
        """
        Get security-relevant audit logs.
        """
        queryset = self.get_queryset().security_relevant()
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get high-risk audit logs",
        summary="Get high-risk logs",
        responses={200: AuditLogSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def high_risk(self, request):
        """
        Get high-risk audit logs (risk score >= 70).
        """
        queryset = self.get_queryset().filter(risk_score__gte=70)
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get failed actions (failures, errors, denied access)",
        summary="Get failed actions",
        responses={200: AuditLogSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def failures(self, request):
        """
        Get audit logs for failed actions.
        """
        queryset = self.get_queryset().filter(
            outcome__in=['failure', 'error', 'denied']
        )
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get audit logs for a specific correlation ID",
        summary="Get correlated logs",
        responses={200: AuditLogSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_correlation(self, request):
        """
        Get audit logs by correlation ID.
        """
        correlation_id = request.query_params.get('correlation_id')
        if not correlation_id:
            return Response(
                {'error': 'correlation_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().for_correlation_id(correlation_id)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get audit statistics for the organization",
        summary="Get audit statistics",
        responses={200: dict}
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get audit log statistics.
        """
        queryset = self.get_queryset()
        
        # Calculate various statistics
        total_logs = queryset.count()
        
        # Recent activity (last 7 days)
        recent_logs = queryset.recent(days=7).count()
        
        # Outcome distribution
        outcome_stats = {}
        for outcome in ['success', 'failure', 'error', 'denied']:
            outcome_stats[outcome] = queryset.filter(outcome=outcome).count()
        
        # Risk distribution
        risk_stats = {
            'low': queryset.filter(risk_score__lt=40).count(),
            'medium': queryset.filter(risk_score__gte=40, risk_score__lt=70).count(),
            'high': queryset.filter(risk_score__gte=70).count(),
        }
        
        # Action category distribution
        category_stats = {}
        for category in ['auth', 'admin', 'data', 'other']:
            category_stats[category] = queryset.filter(action_category=category).count()
        
        # Top actions
        top_actions = (
            queryset.values('action')
            .annotate(count=models.Count('action'))
            .order_by('-count')[:10]
        )
        
        return Response({
            'total_logs': total_logs,
            'recent_activity': {
                'last_7_days': recent_logs,
            },
            'outcomes': outcome_stats,
            'risk_levels': risk_stats,
            'categories': category_stats,
            'top_actions': list(top_actions),
        })
    
    @extend_schema(
        description="Get audit logs for a specific user",
        summary="Get user logs",
        responses={200: AuditLogSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """
        Get audit logs for a specific user.
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from uuid import UUID
            user_uuid = UUID(user_id)
        except ValueError:
            return Response(
                {'error': 'Invalid user_id format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().for_user(user_uuid)
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)