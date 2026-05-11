"""
CRM API Views for ArNet Platform.

ViewSets handle HTTP request/response orchestration and are responsible ONLY for:
1. HTTP protocol concerns (status codes, headers, etc.)
2. Request/response serialization 
3. Authentication and permission checking
4. Calling appropriate Services/Selectors
5. Tenant context management

ViewSets should NOT contain:
- Business logic (belongs in Services)
- Complex data querying (belongs in Selectors)
- Direct ORM operations (belongs in Services/Selectors)

Think of ViewSets as "HTTP traffic controllers" that route requests to the 
appropriate business logic layer and format responses back to clients.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from django.http import Http404

from ..models import Customer, Subscription
from .. import selectors, services
from .serializers import (
    CustomerSerializer, CustomerCreateSerializer, CustomerListSerializer,
    SubscriptionSerializer, SubscriptionCreateSerializer, SubscriptionListSerializer,
    CustomerFilterSerializer, SubscriptionFilterSerializer,
    BulkCustomerStatusUpdateSerializer
)


# =============================================================================
# CUSTOMER VIEWSET
# =============================================================================

class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customers.
    
    Provides standard CRUD operations:
    - GET /customers/ - List customers with filtering
    - POST /customers/ - Create new customer  
    - GET /customers/{id}/ - Retrieve specific customer
    - PUT /customers/{id}/ - Update customer (full)
    - PATCH /customers/{id}/ - Update customer (partial)
    - DELETE /customers/{id}/ - Delete customer (soft delete)
    
    Custom actions:
    - POST /customers/bulk-update-status/ - Bulk status updates
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Get base queryset for the current organization.
        
        This is the foundation of our multi-tenant isolation - every query
        is automatically scoped to the user's organization.
        
        Why we don't use selectors here:
        DRF expects a QuerySet for its built-in pagination, filtering, etc.
        We use selectors for specific queries, but this provides the base.
        """
        # Get the organization from the authenticated user
        organization_id = self.request.user.organization_id
        
        # Use selector to get the base queryset with proper optimization
        return selectors.list_customers_for_org(organization_id)
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.
        
        Different actions need different levels of data:
        - List: Lightweight data for performance
        - Create: Required field validation
        - Detail: Full data
        """
        if self.action == 'list':
            return CustomerListSerializer
        elif self.action == 'create':
            return CustomerCreateSerializer
        else:
            return CustomerSerializer
    
    def get_object(self):
        """
        Retrieve a single customer with proper tenant isolation.
        
        This overrides DRF's default get_object to ensure we use our
        selectors with proper error handling and tenant isolation.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        customer_id = self.kwargs[lookup_url_kwarg]
        organization_id = self.request.user.organization_id
        
        try:
            return selectors.get_customer(customer_id, organization_id)
        except Customer.DoesNotExist:
            raise Http404("Customer not found")
    
    def list(self, request):
        """
        List customers with filtering support.
        
        Query parameters:
        - status: Filter by customer status
        - search: Search in name, email, document_id
        - tags: Comma-separated tags to filter by
        """
        organization_id = request.user.organization_id
        
        # Validate and process filter parameters
        filter_serializer = CustomerFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        filters = filter_serializer.validated_data
        
        # Get filtered customers using selector
        customers = selectors.list_customers_for_org(organization_id, filters)
        
        # Paginate the results (DRF handles this automatically)
        page = self.paginate_queryset(customers)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(customers, many=True)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Create a new customer.
        
        This demonstrates the Service Layer pattern:
        1. Validate input data (Serializer)
        2. Call business logic (Service)  
        3. Return response (ViewSet)
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            # Call service layer for business logic
            customer = services.create_customer(
                organization_id=organization_id,
                **serializer.validated_data
            )
            
            # Serialize response
            response_serializer = CustomerSerializer(customer)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except services.CustomerValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Log the error in a real application
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """
        Update a customer (full update).
        """
        partial = kwargs.pop('partial', False)
        customer = self.get_object()
        serializer = self.get_serializer(customer, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            # Call service layer for business logic
            updated_customer = services.update_customer(
                customer_id=customer.id,
                organization_id=organization_id,
                **serializer.validated_data
            )
            
            response_serializer = CustomerSerializer(updated_customer)
            return Response(response_serializer.data)
            
        except services.CustomerValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def partial_update(self, request, *args, **kwargs):
        """
        Update a customer (partial update).
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a customer (soft delete).
        """
        customer = self.get_object()
        organization_id = request.user.organization_id
        
        try:
            services.delete_customer(
                customer_id=customer.id,
                organization_id=organization_id
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to delete customer'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_update_status(self, request):
        """
        Bulk update customer status.
        
        POST /api/v1/crm/customers/bulk-update-status/
        {
            "customer_ids": ["uuid1", "uuid2"],
            "new_status": "active"
        }
        """
        serializer = BulkCustomerStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            updated_customers = services.bulk_update_customer_status(
                organization_id=organization_id,
                customer_ids=serializer.validated_data['customer_ids'],
                new_status=serializer.validated_data['new_status']
            )
            
            return Response({
                'message': f'Updated {len(updated_customers)} customers',
                'updated_count': len(updated_customers)
            })
            
        except services.CustomerValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# =============================================================================
# SUBSCRIPTION VIEWSET
# =============================================================================

class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing subscriptions.
    
    Provides standard CRUD operations plus custom actions:
    - POST /subscriptions/{id}/cancel/ - Cancel subscription
    - POST /subscriptions/{id}/renew/ - Renew subscription
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get base queryset for the current organization."""
        organization_id = self.request.user.organization_id
        return selectors.list_subscriptions_for_org(organization_id)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return SubscriptionListSerializer
        elif self.action == 'create':
            return SubscriptionCreateSerializer
        else:
            return SubscriptionSerializer
    
    def get_object(self):
        """Retrieve a single subscription with proper tenant isolation."""
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        subscription_id = self.kwargs[lookup_url_kwarg]
        organization_id = self.request.user.organization_id
        
        try:
            return selectors.get_subscription(subscription_id, organization_id)
        except Subscription.DoesNotExist:
            raise Http404("Subscription not found")
    
    def list(self, request):
        """List subscriptions with filtering support."""
        organization_id = request.user.organization_id
        
        # Validate filter parameters
        filter_serializer = SubscriptionFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        filters = filter_serializer.validated_data
        
        # Get filtered subscriptions
        subscriptions = selectors.list_subscriptions_for_org(organization_id, filters)
        
        # Paginate results
        page = self.paginate_queryset(subscriptions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(subscriptions, many=True)
        return Response(serializer.data)
    
    def create(self, request):
        """Create a new subscription."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            # Extract customer_id and remove from data
            customer_id = serializer.validated_data.pop('customer_id')
            
            subscription = services.create_subscription(
                organization_id=organization_id,
                customer_id=customer_id,
                **serializer.validated_data
            )
            
            response_serializer = SubscriptionSerializer(subscription)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except (Customer.DoesNotExist, services.SubscriptionValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def update(self, request, *args, **kwargs):
        """Update a subscription."""
        partial = kwargs.pop('partial', False)
        subscription = self.get_object()
        
        # For updates, we don't allow changing the customer
        data = request.data.copy()
        if 'customer_id' in data:
            data.pop('customer_id')
        
        serializer = self.get_serializer(subscription, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        organization_id = request.user.organization_id
        
        try:
            updated_subscription = services.update_subscription(
                subscription_id=subscription.id,
                organization_id=organization_id,
                **serializer.validated_data
            )
            
            response_serializer = SubscriptionSerializer(updated_subscription)
            return Response(response_serializer.data)
            
        except services.SubscriptionValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update a subscription."""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel a subscription.
        
        POST /api/v1/crm/subscriptions/{id}/cancel/
        """
        subscription = self.get_object()
        organization_id = request.user.organization_id
        
        try:
            canceled_subscription = services.cancel_subscription(
                subscription_id=subscription.id,
                organization_id=organization_id
            )
            
            serializer = SubscriptionSerializer(canceled_subscription)
            return Response(serializer.data)
            
        except services.SubscriptionValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """
        Renew a subscription.
        
        POST /api/v1/crm/subscriptions/{id}/renew/
        {
            "new_period_end": "2024-12-31T23:59:59Z"
        }
        """
        subscription = self.get_object()
        organization_id = request.user.organization_id
        
        # Validate renewal data
        new_period_end = request.data.get('new_period_end')
        if not new_period_end:
            return Response(
                {'error': 'new_period_end is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Parse the date
            from datetime import datetime
            if isinstance(new_period_end, str):
                from django.utils.dateparse import parse_datetime
                new_period_end = parse_datetime(new_period_end)
            
            if not new_period_end:
                return Response(
                    {'error': 'Invalid date format. Use ISO format: YYYY-MM-DDTHH:MM:SSZ'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            renewed_subscription = services.renew_subscription(
                subscription_id=subscription.id,
                organization_id=organization_id,
                new_period_end=new_period_end
            )
            
            serializer = SubscriptionSerializer(renewed_subscription)
            return Response(serializer.data)
            
        except services.SubscriptionValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValueError as e:
            return Response(
                {'error': 'Invalid date format'},
                status=status.HTTP_400_BAD_REQUEST
            )