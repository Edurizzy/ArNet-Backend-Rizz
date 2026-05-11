"""
CRM Services (Write Operations & Business Logic) for ArNet Platform.

Services are responsible for ALL write operations and business logic in the CRM domain.
Think of services as "business process managers" who understand the rules and 
ensure everything happens correctly and safely.

Key Principles:
1. ALL write operations MUST use @transaction.atomic
2. Use selectors for reading data (don't duplicate query logic)
3. Validate business rules before saving
4. Handle exceptions appropriately
5. Return the affected objects for further use
6. Log important business events

Why Services?
- Centralizes business logic in one place
- Ensures transactional integrity
- Makes complex operations testable
- Provides a clean API for views and other consumers
- Maintains consistency across different entry points
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Customer, Subscription
from . import selectors


# =============================================================================
# CUSTOMER SERVICES
# =============================================================================

class CustomerValidationError(ValidationError):
    """Custom exception for customer-specific validation errors."""
    pass


@transaction.atomic
def create_customer(organization_id: uuid.UUID, **customer_data) -> Customer:
    """
    Create a new customer with business validation.
    
    This function is like a "customer onboarding manager" that ensures
    all business rules are followed when adding a new customer.
    
    Args:
        organization_id: UUID of the organization (tenant context)
        **customer_data: Dictionary containing customer fields:
            - name: Required string
            - email: Required valid email
            - phone: Optional string
            - document_id: Required string
            - status: Optional, defaults to 'lead'
            - tags: Optional list of strings
    
    Returns:
        Created Customer instance
        
    Raises:
        CustomerValidationError: If validation fails
        
    Business Rules Enforced:
    1. Email must be unique within the organization
    2. Document ID must be unique within the organization  
    3. Name and email are required
    4. Document ID format validation
    
    Why @transaction.atomic?
    If ANY step fails (validation, uniqueness check, save), 
    the entire operation is rolled back - no partial data is left behind.
    """
    
    # Extract and validate required fields
    name = customer_data.get('name', '').strip()
    email = customer_data.get('email', '').strip().lower()
    document_id = customer_data.get('document_id', '').strip()
    
    # Basic required field validation
    if not name:
        raise CustomerValidationError("Customer name is required")
    
    if not email:
        raise CustomerValidationError("Customer email is required")
        
    if not document_id:
        raise CustomerValidationError("Customer document ID is required")
    
    # Business rule validation: Check uniqueness within organization
    existing_customer_by_email = selectors.get_customer_by_email(email, organization_id)
    if existing_customer_by_email:
        raise CustomerValidationError(
            f"Customer with email {email} already exists in this organization"
        )
    
    existing_customer_by_document = selectors.get_customer_by_document_id(document_id, organization_id)
    if existing_customer_by_document:
        raise CustomerValidationError(
            f"Customer with document ID {document_id} already exists in this organization"
        )
    
    # Prepare customer data with defaults
    customer_data_clean = {
        'organization_id': organization_id,
        'name': name,
        'email': email,
        'phone': customer_data.get('phone', '').strip() or None,
        'document_id': document_id,
        'status': customer_data.get('status', Customer.Status.LEAD),
        'tags': customer_data.get('tags', []),
    }
    
    # Create the customer
    customer = Customer.objects.create(**customer_data_clean)
    
    # Log the business event (in a real application, you might use a proper logging service)
    print(f"Customer created: {customer.name} ({customer.email}) for organization {organization_id}")
    
    return customer


@transaction.atomic
def update_customer(
    customer_id: uuid.UUID,
    organization_id: uuid.UUID,
    **update_data
) -> Customer:
    """
    Update an existing customer with business validation.
    
    This is like having a "customer account manager" who safely updates
    customer information while ensuring all business rules are still followed.
    
    Args:
        customer_id: UUID of the customer to update
        organization_id: UUID of the organization
        **update_data: Dictionary of fields to update
    
    Returns:
        Updated Customer instance
        
    Raises:
        Customer.DoesNotExist: If customer not found
        CustomerValidationError: If validation fails
        
    Why select_for_update?
    This prevents race conditions where two users update the same customer
    simultaneously. It's like putting a "reserved" sign on the customer record.
    """
    
    # Get customer with lock to prevent concurrent modifications
    customer = selectors.get_customer_for_update(customer_id, organization_id)
    
    # Validate email uniqueness if being updated
    if 'email' in update_data:
        new_email = update_data['email'].strip().lower()
        if new_email != customer.email:
            existing_customer = selectors.get_customer_by_email(new_email, organization_id)
            if existing_customer and existing_customer.id != customer.id:
                raise CustomerValidationError(
                    f"Customer with email {new_email} already exists in this organization"
                )
    
    # Validate document ID uniqueness if being updated  
    if 'document_id' in update_data:
        new_document_id = update_data['document_id'].strip()
        if new_document_id != customer.document_id:
            existing_customer = selectors.get_customer_by_document_id(new_document_id, organization_id)
            if existing_customer and existing_customer.id != customer.id:
                raise CustomerValidationError(
                    f"Customer with document ID {new_document_id} already exists in this organization"
                )
    
    # Apply updates (only provided fields)
    for field, value in update_data.items():
        if hasattr(customer, field):
            # Clean string fields
            if isinstance(value, str):
                value = value.strip()
                if field == 'email':
                    value = value.lower()
            
            setattr(customer, field, value)
    
    # Save with validation
    customer.full_clean()  # Runs model validation
    customer.save()
    
    print(f"Customer updated: {customer.name} ({customer.email})")
    
    return customer


@transaction.atomic  
def delete_customer(customer_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    """
    Soft delete a customer (and related subscriptions).
    
    This is like "archiving" a customer - they're not permanently deleted,
    but they're marked as deleted and won't appear in normal queries.
    
    Args:
        customer_id: UUID of the customer to delete
        organization_id: UUID of the organization
        
    Raises:
        Customer.DoesNotExist: If customer not found
        
    Business Rules:
    1. Customer is soft-deleted (not permanently removed)
    2. All customer subscriptions are also soft-deleted
    3. Operation is atomic (all or nothing)
    """
    
    customer = selectors.get_customer_for_update(customer_id, organization_id)
    
    # Soft delete all customer subscriptions first
    customer_subscriptions = selectors.list_customer_subscriptions(customer_id, organization_id)
    for subscription in customer_subscriptions:
        subscription.delete()  # Soft delete from TenantAwareModel
    
    # Soft delete the customer
    customer.delete()  # Soft delete from TenantAwareModel
    
    print(f"Customer deleted: {customer.name} ({customer.email}) and {customer_subscriptions.count()} subscriptions")


# =============================================================================
# SUBSCRIPTION SERVICES  
# =============================================================================

class SubscriptionValidationError(ValidationError):
    """Custom exception for subscription-specific validation errors."""
    pass


@transaction.atomic
def create_subscription(
    organization_id: uuid.UUID,
    customer_id: uuid.UUID,
    plan_name: str,
    current_period_end: datetime,
    status: str = Subscription.Status.ACTIVE,
    **extra_data
) -> Subscription:
    """
    Create a new subscription for a customer.
    
    This function is like a "subscription manager" that sets up new services
    for customers while ensuring all business rules are followed.
    
    Args:
        organization_id: UUID of the organization  
        customer_id: UUID of the customer
        plan_name: Name of the subscription plan
        current_period_end: When the billing period ends
        status: Subscription status (defaults to active)
        **extra_data: Additional subscription data
    
    Returns:
        Created Subscription instance
        
    Raises:
        Customer.DoesNotExist: If customer not found
        SubscriptionValidationError: If validation fails
        
    Business Rules:
    1. Customer must exist and belong to the organization
    2. Plan name is required
    3. Period end must be in the future for active subscriptions
    4. One subscription per customer per plan (configurable business rule)
    """
    
    # Validate customer exists in organization
    customer = selectors.get_customer(customer_id, organization_id)
    
    # Basic validation
    if not plan_name or not plan_name.strip():
        raise SubscriptionValidationError("Plan name is required")
    
    plan_name = plan_name.strip()
    
    # Business rule: Period end validation for active subscriptions
    if status == Subscription.Status.ACTIVE and current_period_end <= timezone.now():
        raise SubscriptionValidationError(
            "Active subscriptions must have a future period end date"
        )
    
    # Optional business rule: Check for duplicate plan subscriptions
    # (You might want to allow multiple subscriptions to the same plan, or not)
    existing_subscription = Subscription.objects.filter(
        customer=customer,
        organization_id=organization_id,
        plan_name=plan_name,
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE]
    ).first()
    
    if existing_subscription:
        raise SubscriptionValidationError(
            f"Customer already has an active subscription to {plan_name}"
        )
    
    # Create subscription
    subscription_data = {
        'organization_id': organization_id,
        'customer': customer,
        'plan_name': plan_name,
        'status': status,
        'current_period_end': current_period_end,
        **extra_data
    }
    
    subscription = Subscription.objects.create(**subscription_data)
    
    print(f"Subscription created: {customer.name} -> {plan_name} (expires: {current_period_end})")
    
    return subscription


@transaction.atomic
def update_subscription(
    subscription_id: uuid.UUID,
    organization_id: uuid.UUID,
    **update_data
) -> Subscription:
    """
    Update an existing subscription.
    
    Args:
        subscription_id: UUID of subscription to update
        organization_id: UUID of the organization
        **update_data: Fields to update
        
    Returns:
        Updated Subscription instance
        
    Raises:
        Subscription.DoesNotExist: If subscription not found
        SubscriptionValidationError: If validation fails
    """
    
    # Get subscription with lock
    subscription = selectors.get_subscription_for_update(subscription_id, organization_id)
    
    # Validate period end for active subscriptions
    if 'current_period_end' in update_data and 'status' in update_data:
        if (update_data['status'] == Subscription.Status.ACTIVE and 
            update_data['current_period_end'] <= timezone.now()):
            raise SubscriptionValidationError(
                "Active subscriptions must have a future period end date"
            )
    elif 'current_period_end' in update_data and subscription.status == Subscription.Status.ACTIVE:
        if update_data['current_period_end'] <= timezone.now():
            raise SubscriptionValidationError(
                "Active subscriptions must have a future period end date"
            )
    
    # Apply updates
    for field, value in update_data.items():
        if hasattr(subscription, field):
            if isinstance(value, str):
                value = value.strip()
            setattr(subscription, field, value)
    
    # Validate and save
    subscription.full_clean()
    subscription.save()
    
    print(f"Subscription updated: {subscription.customer.name} -> {subscription.plan_name}")
    
    return subscription


@transaction.atomic
def cancel_subscription(subscription_id: uuid.UUID, organization_id: uuid.UUID) -> Subscription:
    """
    Cancel a subscription (change status to canceled).
    
    This is like "terminating a service contract" - the subscription still exists
    in the system for historical purposes but is no longer active.
    
    Args:
        subscription_id: UUID of subscription to cancel
        organization_id: UUID of the organization
        
    Returns:
        Canceled Subscription instance
        
    Business Rules:
    1. Only active or past_due subscriptions can be canceled
    2. Canceled subscriptions cannot be reactivated (business decision)
    """
    
    subscription = selectors.get_subscription_for_update(subscription_id, organization_id)
    
    # Business rule: Only cancel active or past_due subscriptions
    if subscription.status == Subscription.Status.CANCELED:
        raise SubscriptionValidationError("Subscription is already canceled")
    
    if subscription.status not in [Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE]:
        raise SubscriptionValidationError(
            f"Cannot cancel subscription with status: {subscription.status}"
        )
    
    # Update status
    subscription.status = Subscription.Status.CANCELED
    subscription.save()
    
    print(f"Subscription canceled: {subscription.customer.name} -> {subscription.plan_name}")
    
    return subscription


@transaction.atomic
def renew_subscription(
    subscription_id: uuid.UUID,
    organization_id: uuid.UUID,
    new_period_end: datetime
) -> Subscription:
    """
    Renew a subscription by extending the period end date.
    
    This is like "renewing a contract" - extending the service period.
    
    Args:
        subscription_id: UUID of subscription to renew
        organization_id: UUID of the organization  
        new_period_end: New period end date (must be in future)
        
    Returns:
        Renewed Subscription instance
        
    Business Rules:
    1. Only active or past_due subscriptions can be renewed
    2. New period end must be after current period end
    3. Status is set to active after successful renewal
    """
    
    subscription = selectors.get_subscription_for_update(subscription_id, organization_id)
    
    # Validation
    if subscription.status == Subscription.Status.CANCELED:
        raise SubscriptionValidationError("Cannot renew canceled subscription")
    
    if new_period_end <= subscription.current_period_end:
        raise SubscriptionValidationError(
            "New period end must be after current period end"
        )
    
    if new_period_end <= timezone.now():
        raise SubscriptionValidationError(
            "New period end must be in the future"
        )
    
    # Update subscription
    subscription.current_period_end = new_period_end
    subscription.status = Subscription.Status.ACTIVE
    subscription.save()
    
    print(f"Subscription renewed: {subscription.customer.name} -> {subscription.plan_name} until {new_period_end}")
    
    return subscription


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@transaction.atomic
def bulk_update_customer_status(
    organization_id: uuid.UUID,
    customer_ids: List[uuid.UUID],
    new_status: str
) -> List[Customer]:
    """
    Update status for multiple customers at once.
    
    This is useful for batch operations like "mark all leads as active customers".
    
    Args:
        organization_id: UUID of the organization
        customer_ids: List of customer UUIDs to update
        new_status: New status to set
        
    Returns:
        List of updated Customer instances
        
    Why bulk operations?
    - More efficient than individual updates
    - Atomic (all succeed or all fail)
    - Useful for admin operations and data migrations
    """
    
    if not customer_ids:
        return []
    
    # Validate status
    if new_status not in [choice[0] for choice in Customer.Status.choices]:
        raise CustomerValidationError(f"Invalid status: {new_status}")
    
    # Get customers with locks
    customers = []
    for customer_id in customer_ids:
        try:
            customer = selectors.get_customer_for_update(customer_id, organization_id)
            customers.append(customer)
        except Customer.DoesNotExist:
            # Skip non-existent customers but don't fail the entire operation
            print(f"Warning: Customer {customer_id} not found, skipping")
            continue
    
    # Update all customers
    updated_customers = []
    for customer in customers:
        customer.status = new_status
        customer.save()
        updated_customers.append(customer)
    
    print(f"Bulk updated {len(updated_customers)} customers to status: {new_status}")
    
    return updated_customers