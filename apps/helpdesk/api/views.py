"""
Helpdesk API Views for ArNet Platform.

ViewSets handle HTTP orchestration for helpdesk operations with focus on:
1. Agent productivity and dashboard workflows
2. Real-time communication and message streaming  
3. Operational helpdesk business processes
4. High-performance conversation loading
5. Event-driven architecture preparation

ViewSets are responsible ONLY for:
- HTTP protocol concerns (status codes, headers, authentication)
- Request/response serialization and validation
- Calling appropriate Services/Selectors
- Tenant context management  
- Performance optimization (pagination, caching)

ViewSets should NOT contain:
- Business logic (belongs in Services)
- Complex data querying (belongs in Selectors)  
- Direct ORM operations (belongs in Services/Selectors)
- Domain event emission (belongs in Services)

This module is designed for operational helpdesk workflows and
future real-time system integration.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from django.http import Http404

from ..models import Ticket, Message
from .. import selectors, services
from .serializers import (
    TicketSerializer, TicketCreateSerializer, TicketListSerializer,
    MessageSerializer, MessageCreateSerializer, MessageListSerializer,
    TicketFilterSerializer, MessageFilterSerializer,
    TicketStatusUpdateSerializer, TicketAssignmentSerializer, BulkTicketAssignmentSerializer,
    TicketStatisticsSerializer, OutboundWhatsAppMessageCreateSerializer,
)


# =============================================================================
# TICKET VIEWSET
# =============================================================================

class TicketViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing support tickets with agent productivity focus.
    
    Provides comprehensive ticket management for helpdesk operations:
    - GET /tickets/ - Agent dashboard with filtering and search
    - POST /tickets/ - Create new ticket (from any channel)
    - GET /tickets/{id}/ - Ticket detail with conversation context
    - PUT/PATCH /tickets/{id}/ - Update ticket properties
    - POST /tickets/{id}/assign/ - Assign to agent
    - POST /tickets/{id}/update-status/ - Change ticket status
    - POST /tickets/{id}/messages/ - Outbound WhatsApp message (async send)
    - POST /tickets/bulk-assign/ - Bulk assignment operations
    - GET /tickets/statistics/ - Dashboard metrics
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Get base queryset with performance optimization.
        
        Automatically tenant-scoped and optimized for agent dashboard queries.
        """
        organization_id = self.request.user.organization_id
        
        # Use selector with performance optimizations
        # This includes select_related and message count annotations
        return selectors.list_tickets_for_org(organization_id)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return TicketListSerializer
        elif self.action == 'create':
            return TicketCreateSerializer
        elif self.action in ['update_status']:
            return TicketStatusUpdateSerializer
        elif self.action in ['assign', 'bulk_assign']:
            return TicketAssignmentSerializer
        else:
            return TicketSerializer
    
    def get_object(self):
        """Retrieve single ticket with tenant isolation."""
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        ticket_id = self.kwargs[lookup_url_kwarg]
        organization_id = self.request.user.organization_id
        
        try:
            return selectors.get_ticket_detail(ticket_id, organization_id)
        except Ticket.DoesNotExist:
            raise Http404("Ticket not found")

    @action(detail=True, methods=['post'], url_path='messages')
    def messages(self, request, pk=None):
        """
        Create an outbound WhatsApp message for this ticket (async delivery via Celery).

        POST /api/v1/helpdesk/tickets/{id}/messages/
        """
        ticket = self.get_object()
        serializer = OutboundWhatsAppMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        organization_id = request.user.organization_id

        try:
            message = services.create_outbound_message(
                ticket_id=ticket.id,
                organization_id=organization_id,
                agent_user_id=request.user.id,
                content=serializer.validated_data['content'],
                correlation_id=serializer.validated_data.get('correlation_id'),
            )
        except services.HelpdeskValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = MessageSerializer(message)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request):
        """
        List tickets with comprehensive filtering for agent dashboards.
        
        Query parameters:
        - status: Filter by ticket status
        - priority: Filter by priority level  
        - channel: Filter by communication channel
        - assigned_to: Filter by assigned agent
        - search: Search customer names and ticket titles
        - sla_overdue: Show only overdue tickets
        - unassigned: Show only unassigned tickets
        """
        organization_id = request.user.organization_id
        
        # Validate and process filter parameters
        filter_serializer = TicketFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        filters = filter_serializer.validated_data
        
        # Get filtered tickets using optimized selector
        tickets = selectors.list_tickets_for_org(organization_id, filters)
        
        # Paginate for large datasets (agent dashboard performance)
        page = self.paginate_queryset(tickets)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(tickets, many=True)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Create a new support ticket.
        
        Handles ticket creation from any channel (email, chat, WhatsApp, etc.)
        with proper validation and business logic execution.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            # Extract customer_id and remove from data
            customer_id = serializer.validated_data.pop('customer_id')
            
            # Call service layer for business logic
            ticket = services.create_ticket(
                organization_id=organization_id,
                customer_id=customer_id,
                **serializer.validated_data
            )
            
            # Return detailed ticket information
            response_serializer = TicketSerializer(ticket)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except services.HelpdeskValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Revelando o erro no terminal:
            import traceback
            traceback.print_exc()
            
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """
        Update ticket properties.
        
        Handles general ticket updates while maintaining business rule validation.
        For specific operations like status changes, use dedicated endpoints.
        """
        partial = kwargs.pop('partial', False)
        ticket = self.get_object()
        serializer = self.get_serializer(ticket, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            # For general updates, we can update multiple fields
            # Complex business logic should use specific service methods
            
            # Handle title update
            if 'title' in serializer.validated_data:
                ticket.title = serializer.validated_data['title']
            
            # Handle priority update  
            if 'priority' in serializer.validated_data:
                ticket.priority = serializer.validated_data['priority']
                # Recalculate SLA if priority changed
                if ticket.priority != serializer.validated_data['priority']:
                    ticket.sla_due_at = services._calculate_sla_due_date(
                        serializer.validated_data['priority']
                    )
            
            # Handle metadata update
            if 'metadata' in serializer.validated_data:
                ticket.metadata = serializer.validated_data['metadata']
            
            ticket.save()
            
            response_serializer = TicketSerializer(ticket)
            return Response(response_serializer.data)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to update ticket'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def partial_update(self, request, *args, **kwargs):
        """Partial ticket update."""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Update ticket status with business rule validation.
        
        POST /api/v1/helpdesk/tickets/{id}/update-status/
        {
            "status": "resolved",
            "reason": "Issue resolved via email"
        }
        """
        ticket = self.get_object()
        serializer = TicketStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            updated_ticket = services.update_ticket_status(
                ticket_id=ticket.id,
                organization_id=organization_id,
                new_status=serializer.validated_data['status'],
                updated_by=request.user.id,
                reason=serializer.validated_data.get('reason')
            )
            
            response_serializer = TicketSerializer(updated_ticket)
            return Response(response_serializer.data)
            
        except services.TicketTransitionError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Assign ticket to an agent.
        
        POST /api/v1/helpdesk/tickets/{id}/assign/
        {
            "agent_id": "uuid-of-agent"
        }
        """
        ticket = self.get_object()
        serializer = TicketAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            assigned_ticket = services.assign_ticket(
                ticket_id=ticket.id,
                organization_id=organization_id,
                agent_id=serializer.validated_data['agent_id'],
                assigned_by=request.user.id
            )
            
            response_serializer = TicketSerializer(assigned_ticket)
            return Response(response_serializer.data)
            
        except services.AssignmentError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        """
        Bulk assign multiple tickets to an agent.
        
        POST /api/v1/helpdesk/tickets/bulk-assign/
        {
            "ticket_ids": ["uuid1", "uuid2", "uuid3"],
            "agent_id": "agent-uuid"
        }
        """
        serializer = BulkTicketAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            assigned_tickets = services.bulk_assign_tickets(
                ticket_ids=serializer.validated_data['ticket_ids'],
                organization_id=organization_id,
                agent_id=serializer.validated_data['agent_id'],
                assigned_by=request.user.id
            )
            
            return Response({
                'message': f'Successfully assigned {len(assigned_tickets)} tickets',
                'assigned_count': len(assigned_tickets),
                'ticket_ids': [str(ticket.id) for ticket in assigned_tickets]
            })
            
        except services.AssignmentError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get ticket statistics for dashboard metrics.
        
        GET /api/v1/helpdesk/tickets/statistics/
        
        Returns counts and distributions for agent dashboards.
        """
        organization_id = request.user.organization_id
        
        try:
            stats = selectors.get_ticket_statistics_for_org(organization_id)
            serializer = TicketStatisticsSerializer(stats)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to retrieve statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# MESSAGE VIEWSET
# =============================================================================

class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing messages within tickets.
    
    Provides message operations optimized for real-time conversation:
    - GET /messages/ - List messages for a ticket (conversation view)
    - POST /messages/ - Add new message to ticket
    - GET /messages/{id}/ - Get specific message details
    
    Special considerations:
    - Optimized for high-frequency message creation
    - Pagination support for large conversations
    - Real-time update preparation (WebSocket ready)
    - External platform integration (webhook support)
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return MessageListSerializer
        elif self.action == 'create':
            return MessageCreateSerializer
        else:
            return MessageSerializer
    
    def get_queryset(self):
        """
        Base queryset for messages (requires ticket_id parameter).
        
        Note: This ViewSet is typically used for ticket-specific message operations.
        """
        organization_id = self.request.user.organization_id
        ticket_id = self.request.query_params.get('ticket_id')
        
        if ticket_id:
            return selectors.list_messages_for_ticket(ticket_id, organization_id)
        else:
            # Return empty queryset if no ticket specified
            return Message.objects.none()
    
    def list(self, request):
        """
        List messages for a specific ticket (conversation view).
        
        Required query parameter: ticket_id
        Optional pagination parameters: limit, offset, before_id, after_id
        
        Optimized for:
        - Initial conversation loading
        - Infinite scroll (pagination)
        - Real-time updates (after_id parameter)
        """
        organization_id = request.user.organization_id
        
        # Validate required ticket_id parameter
        ticket_id = request.query_params.get('ticket_id')
        if not ticket_id:
            return Response(
                {'error': 'ticket_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Validate ticket exists and user has access
            ticket = selectors.get_ticket_detail(ticket_id, organization_id)
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate and process pagination parameters
        pagination_serializer = MessageFilterSerializer(data=request.query_params)
        pagination_serializer.is_valid(raise_exception=True)
        pagination = pagination_serializer.validated_data
        
        # Get messages using optimized selector
        messages = selectors.list_messages_for_ticket(ticket_id, organization_id, pagination)
        
        # Handle pagination
        if pagination.get('limit'):
            # Custom pagination for real-time conversations
            serializer = self.get_serializer(messages, many=True)
            return Response({
                'results': serializer.data,
                'count': len(serializer.data),
                'has_more': len(serializer.data) == pagination.get('limit', 0)
            })
        else:
            # Standard pagination
            page = self.paginate_queryset(messages)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Add a new message to a ticket.
        
        Handles message creation with:
        - Business logic validation (via Services)
        - Ticket state evaluation and updates
        - External platform deduplication
        - Real-time notification preparation
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            # Extract ticket_id and remove from data
            ticket_id = serializer.validated_data.pop('ticket_id')
            
            # Call service layer for business logic and state management
            message = services.add_message_to_ticket(
                ticket_id=ticket_id,
                organization_id=organization_id,
                **serializer.validated_data
            )
            
            # Return full message details
            response_serializer = MessageSerializer(message)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except services.HelpdeskValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Pegando o erro completo e forçando ele a aparecer no Swagger!
            import traceback
            error_trace = traceback.format_exc()
            
            return Response(
                {
                    'error': str(e),
                    'traceback': error_trace  # O erro vai aparecer na sua tela!
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def retrieve(self, request, pk=None):
        """
        Get specific message details.
        
        Used for message context, editing, or detailed view requirements.
        """
        organization_id = request.user.organization_id
        
        try:
            # Get message with tenant isolation
            message = Message.objects.select_related('ticket').get(
                id=pk,
                organization_id=organization_id
            )
            
            serializer = self.get_serializer(message)
            return Response(serializer.data)
            
        except Message.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# =============================================================================
# ADDITIONAL OPERATIONAL VIEWS
# =============================================================================

# Note: Additional views for analytics, reporting, and operational
# metrics could be added here as the system grows:
#
# - Agent workload views
# - SLA monitoring endpoints
# - Real-time dashboard data
# - Customer conversation history
# - Analytics and reporting APIs
#
# These would follow the same patterns:
# - Tenant isolation via organization_id
# - Service layer for business logic
# - Selectors for optimized queries
# - Proper error handling and validation