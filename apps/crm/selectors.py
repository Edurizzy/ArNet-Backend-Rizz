"""
CRM Selectors (Read Operations) for ArNet Platform.

Selectors are responsible for ALL read operations in the CRM domain.
Think of selectors as "specialized librarians" who know exactly how to find
and retrieve data efficiently and safely.

Key Principles:
1. ALL queries MUST be scoped by organization_id (multi-tenant isolation)
2. Use select_related/prefetch_related for performance optimization
3. Return typed QuerySets and model instances
4. Handle DoesNotExist exceptions appropriately
5. Provide flexible filtering capabilities

Why Selectors?
- Centralizes all read logic in one place
- Ensures consistent tenant isolation
- Optimizes database queries for performance
- Makes testing read operations easier
- Separates concerns from write operations (Services)
"""

import uuid
from typing import Dict, Any, Optional, List
from django.db.models import Q, QuerySet
from django.core.exceptions import ObjectDoesNotExist

from .models import Customer, Subscription


# =============================================================================
# CUSTOMER SELECTORS
# =============================================================================

def get_customer(customer_id: uuid.UUID, organization_id: uuid.UUID) -> Customer:
    """
    Retrieve a single customer by ID within an organization.
    
    This is like asking a librarian: "Please find me the specific customer 
    record with this ID, but only if it belongs to my organization."
    
    Args:
        customer_id: UUID of the customer to retrieve
        organization_id: UUID of the organization (tenant isolation)
    
    Returns:
        Customer instance
        
    Raises:
        Customer.DoesNotExist: If customer not found or doesn't belong to organization
        
    Why we filter by organization_id:
        This is our SECURITY BOUNDARY. Without this, Organization A could
        access Organization B's customers by guessing UUIDs.
    """
    try:
        return Customer.objects.select_related('organization').get(
            id=customer_id,
            organization_id=organization_id
        )
    except Customer.DoesNotExist:
        raise Customer.DoesNotExist(
            f"Customer {customer_id} not found for organization {organization_id}"
        )


def get_customer_for_update(customer_id: uuid.UUID, organization_id: uuid.UUID) -> Customer:
    """
    Retrieve a customer with SELECT FOR UPDATE lock.
    
    This is like putting a "reserved" sign on a library book while you're working with it.
    It prevents other users from modifying the same customer simultaneously,
    which could cause race conditions and data corruption.
    
    Args:
        customer_id: UUID of the customer to retrieve
        organization_id: UUID of the organization
    
    Returns:
        Customer instance with database row lock
        
    Raises:
        Customer.DoesNotExist: If customer not found or doesn't belong to organization
        
    When to use:
        - Before updating customer data in services
        - When you need to ensure atomic updates
        - In high-concurrency scenarios
    """
    try:
        return Customer.objects.select_related('organization').select_for_update().get(
            id=customer_id,
            organization_id=organization_id
        )
    except Customer.DoesNotExist:
        raise Customer.DoesNotExist(
            f"Customer {customer_id} not found for organization {organization_id}"
        )


def list_customers_for_org(
    organization_id: uuid.UUID,
    filters: Optional[Dict[str, Any]] = None
) -> QuerySet[Customer]:
    """
    List customers for an organization with optional filtering.
    
    Think of this as a smart search function that can filter customers
    based on various criteria while maintaining tenant isolation.
    
    Args:
        organization_id: UUID of the organization
        filters: Optional dictionary of filters:
            - status: Customer status ('active', 'inactive', 'lead')
            - search: Search term for name, email, or document
            - tags: List of tags to filter by
            
    Returns:
        QuerySet of Customer instances
        
    Example usage:
        # Get all active customers
        active_customers = list_customers_for_org(org_id, {'status': 'active'})
        
        # Search for customers
        search_results = list_customers_for_org(org_id, {'search': 'john@example.com'})
        
        # Filter by tags
        vip_customers = list_customers_for_org(org_id, {'tags': ['vip', 'premium']})
    """
    # Start with base queryset - always scoped to organization
    queryset = Customer.objects.filter(organization_id=organization_id)
    
    # Optimize database queries by loading related data in advance
    queryset = queryset.select_related('organization')
    
    # Apply filters if provided
    if filters:
        # Status filter
        if 'status' in filters and filters['status']:
            queryset = queryset.filter(status=filters['status'])
        
        # Search across name, email, and document_id
        # Using Q objects allows complex OR conditions
        if 'search' in filters and filters['search']:
            search_term = filters['search'].strip()
            if search_term:
                search_query = Q(name__icontains=search_term) | \
                              Q(email__icontains=search_term) | \
                              Q(document_id__icontains=search_term)
                queryset = queryset.filter(search_query)
        
        # Tag filtering - check if any provided tags are in customer's tags
        if 'tags' in filters and filters['tags']:
            tag_filters = Q()
            for tag in filters['tags']:
                # JSONField contains check - finds customers with this tag
                tag_filters |= Q(tags__contains=[tag])
            queryset = queryset.filter(tag_filters)
    
    # Default ordering by most recently created
    return queryset.order_by('-created_at')


def get_customer_by_email(email: str, organization_id: uuid.UUID) -> Optional[Customer]:
    """
    Find a customer by email within an organization.
    
    This is useful for checking if a customer already exists when creating new ones,
    or for login/lookup functionality.
    
    Args:
        email: Email address to search for
        organization_id: UUID of the organization
        
    Returns:
        Customer instance if found, None otherwise
        
    Note: Returns None instead of raising exception for easier conditional logic
    """
    try:
        return Customer.objects.select_related('organization').get(
            email__iexact=email,  # Case-insensitive email search
            organization_id=organization_id
        )
    except Customer.DoesNotExist:
        return None


def get_customer_by_document_id(document_id: str, organization_id: uuid.UUID) -> Optional[Customer]:
    """
    Find a customer by document ID within an organization.
    
    Useful for duplicate checking and customer lookup by tax document.
    
    Args:
        document_id: Tax document number to search for
        organization_id: UUID of the organization
        
    Returns:
        Customer instance if found, None otherwise
    """
    try:
        return Customer.objects.select_related('organization').get(
            document_id=document_id,
            organization_id=organization_id
        )
    except Customer.DoesNotExist:
        return None


# =============================================================================
# SUBSCRIPTION SELECTORS
# =============================================================================

def get_subscription(subscription_id: uuid.UUID, organization_id: uuid.UUID) -> Subscription:
    """
    Retrieve a single subscription by ID within an organization.
    
    Args:
        subscription_id: UUID of the subscription to retrieve
        organization_id: UUID of the organization
        
    Returns:
        Subscription instance
        
    Raises:
        Subscription.DoesNotExist: If subscription not found or doesn't belong to organization
    """
    try:
        return Subscription.objects.select_related('customer', 'organization').get(
            id=subscription_id,
            organization_id=organization_id
        )
    except Subscription.DoesNotExist:
        raise Subscription.DoesNotExist(
            f"Subscription {subscription_id} not found for organization {organization_id}"
        )


def get_subscription_for_update(subscription_id: uuid.UUID, organization_id: uuid.UUID) -> Subscription:
    """
    Retrieve a subscription with SELECT FOR UPDATE lock.
    
    Args:
        subscription_id: UUID of the subscription to retrieve
        organization_id: UUID of the organization
        
    Returns:
        Subscription instance with database row lock
        
    Raises:
        Subscription.DoesNotExist: If subscription not found or doesn't belong to organization
    """
    try:
        return Subscription.objects.select_related('customer', 'organization').select_for_update().get(
            id=subscription_id,
            organization_id=organization_id
        )
    except Subscription.DoesNotExist:
        raise Subscription.DoesNotExist(
            f"Subscription {subscription_id} not found for organization {organization_id}"
        )


def list_subscriptions_for_org(
    organization_id: uuid.UUID,
    filters: Optional[Dict[str, Any]] = None
) -> QuerySet[Subscription]:
    """
    List subscriptions for an organization with optional filtering.
    
    Args:
        organization_id: UUID of the organization
        filters: Optional dictionary of filters:
            - status: Subscription status ('active', 'past_due', 'canceled')
            - customer_id: Filter by specific customer
            - plan_name: Filter by plan name
            - expiring_soon: Boolean to filter subscriptions expiring within 7 days
            
    Returns:
        QuerySet of Subscription instances
    """
    # Base queryset with performance optimization
    queryset = Subscription.objects.filter(organization_id=organization_id)
    queryset = queryset.select_related('customer', 'organization')
    
    if filters:
        # Status filter
        if 'status' in filters and filters['status']:
            queryset = queryset.filter(status=filters['status'])
        
        # Customer filter
        if 'customer_id' in filters and filters['customer_id']:
            queryset = queryset.filter(customer_id=filters['customer_id'])
        
        # Plan name filter
        if 'plan_name' in filters and filters['plan_name']:
            queryset = queryset.filter(plan_name__icontains=filters['plan_name'])
        
        # Expiring soon filter (next 7 days)
        if 'expiring_soon' in filters and filters['expiring_soon']:
            from django.utils import timezone
            from datetime import timedelta
            
            seven_days_from_now = timezone.now() + timedelta(days=7)
            queryset = queryset.filter(
                status=Subscription.Status.ACTIVE,
                current_period_end__lte=seven_days_from_now
            )
    
    return queryset.order_by('-created_at')


def list_customer_subscriptions(customer_id: uuid.UUID, organization_id: uuid.UUID) -> QuerySet[Subscription]:
    """
    Get all subscriptions for a specific customer.
    
    This is like asking: "Show me all the services this customer is subscribed to."
    
    Args:
        customer_id: UUID of the customer
        organization_id: UUID of the organization
        
    Returns:
        QuerySet of Subscription instances for the customer
    """
    return Subscription.objects.filter(
        customer_id=customer_id,
        organization_id=organization_id
    ).select_related('customer', 'organization').order_by('-created_at')


def get_active_subscriptions_for_customer(customer_id: uuid.UUID, organization_id: uuid.UUID) -> QuerySet[Subscription]:
    """
    Get only active subscriptions for a customer.
    
    Useful for billing, feature access checks, etc.
    
    Args:
        customer_id: UUID of the customer
        organization_id: UUID of the organization
        
    Returns:
        QuerySet of active Subscription instances
    """
    return Subscription.objects.filter(
        customer_id=customer_id,
        organization_id=organization_id,
        status=Subscription.Status.ACTIVE
    ).select_related('customer', 'organization').order_by('-created_at')


# =============================================================================
# ANALYTICS & REPORTING SELECTORS
# =============================================================================

def get_customer_count_by_status(organization_id: uuid.UUID) -> Dict[str, int]:
    """
    Get count of customers grouped by status.
    
    This is useful for dashboard metrics and reporting.
    
    Args:
        organization_id: UUID of the organization
        
    Returns:
        Dictionary with status as key and count as value
        Example: {'active': 150, 'inactive': 25, 'lead': 300}
    """
    from django.db.models import Count
    
    # Use Django's aggregation to count efficiently at database level
    result = Customer.objects.filter(organization_id=organization_id).values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Convert to dictionary for easier use
    return {item['status']: item['count'] for item in result}


def get_subscription_count_by_status(organization_id: uuid.UUID) -> Dict[str, int]:
    """
    Get count of subscriptions grouped by status.
    
    Args:
        organization_id: UUID of the organization
        
    Returns:
        Dictionary with status as key and count as value
    """
    from django.db.models import Count
    
    result = Subscription.objects.filter(organization_id=organization_id).values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    return {item['status']: item['count'] for item in result}