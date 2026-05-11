"""
CRM Domain Models for ArNet Platform.

This module contains the core business entities for Customer Relationship Management:
- Customer: Central entity representing clients/leads
- Subscription: Represents customer subscriptions to services/plans

Key Design Principles:
1. All models inherit from TenantAwareModel for multi-tenant isolation
2. Models contain ONLY fields, relationships, and simple computed properties
3. NO business logic in models (belongs in Services)
4. Proper database indexing for performance
5. Clear relationship definitions with proper related_names
"""

import uuid
from typing import TYPE_CHECKING

from django.core.validators import RegexValidator
from django.db import models

from apps.common.models import TenantAwareModel

if TYPE_CHECKING:
    from django.db.models import QuerySet


class Customer(TenantAwareModel):
    """
    Customer model representing clients, leads, or prospects.
    
    Think of this as a digital business card that contains all the essential
    information about someone who does (or might) do business with a company.
    
    The multi-tenant design ensures each organization only sees their own customers,
    like having separate filing cabinets for different businesses.
    """
    
    # Customer Status Choices
    # These are like "buckets" that help organize customers by their relationship stage
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'          # Paying customers
        INACTIVE = 'inactive', 'Inactive'    # Former customers
        LEAD = 'lead', 'Lead'               # Potential customers
    
    # Core identification fields
    name = models.CharField(
        max_length=255,
        help_text="Full name or company name of the customer"
    )
    
    email = models.EmailField(
        help_text="Primary email address for communication"
    )
    
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Primary phone number"
    )
    
    # Document ID with basic validation (CPF/CNPJ format)
    # This is like a "tax ID" - different countries have different formats
    document_id = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^[\d\.\-\/]+$',
                message="Document ID must contain only numbers, dots, dashes, and slashes"
            )
        ],
        help_text="Tax document number (CPF/CNPJ)"
    )
    
    # Business status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LEAD,
        help_text="Current relationship status with the customer"
    )
    
    # Flexible metadata storage
    # JSONField is like a flexible notepad where we can store different types of info
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Flexible tags for categorization and filtering"
    )
    
    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        
        # Database indexes for performance optimization
        # Think of indexes like a book's index - they help find information quickly
        indexes = [
            # Multi-tenant queries (most common pattern)
            models.Index(fields=['organization', 'email'], name='crm_customer_org_email_idx'),
            models.Index(fields=['organization', 'document_id'], name='crm_customer_org_doc_idx'),
            models.Index(fields=['organization', 'status'], name='crm_customer_org_status_idx'),
            # Search optimization
            models.Index(fields=['organization', 'created_at'], name='crm_customer_org_created_idx'),
        ]
        
        # Business constraints
        # These are "rules" enforced at the database level for data integrity
        constraints = [
            # Ensure unique email per organization (not globally unique)
            models.UniqueConstraint(
                fields=['organization', 'email'],
                name='crm_customer_unique_email_per_org'
            ),
            # Ensure unique document per organization
            models.UniqueConstraint(
                fields=['organization', 'document_id'],
                name='crm_customer_unique_document_per_org'
            ),
        ]
    
    def __str__(self) -> str:
        """Human-readable representation of the customer."""
        return f"{self.name} ({self.email})"
    
    @property
    def is_active_customer(self) -> bool:
        """
        Simple computed property to check if customer is active.
        
        This is acceptable in models because it's a simple property
        that doesn't involve complex business logic.
        """
        return self.status == self.Status.ACTIVE


class Subscription(TenantAwareModel):
    """
    Subscription model representing customer subscriptions to plans/services.
    
    Think of this as a "contract" or "agreement" between the company and customer.
    It tracks what service they're paying for, when it expires, and the current status.
    
    The relationship to Customer creates a "one customer can have many subscriptions" pattern.
    """
    
    # Subscription Status Choices
    # These represent the lifecycle states of a subscription
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'              # Currently active and paid
        PAST_DUE = 'past_due', 'Past Due'       # Payment failed, grace period
        CANCELED = 'canceled', 'Canceled'        # Terminated by customer or admin
    
    # Relationship to Customer
    # This creates the "foreign key" link - like a reference in a filing system
    customer = models.ForeignKey(
        'Customer',  # String reference to avoid circular imports
        on_delete=models.CASCADE,  # If customer is deleted, delete their subscriptions
        related_name='subscriptions',  # Allows customer.subscriptions.all()
        help_text="Customer who owns this subscription"
    )
    
    # Subscription details
    plan_name = models.CharField(
        max_length=100,
        help_text="Name of the subscribed plan or service"
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Current status of the subscription"
    )
    
    # Billing period tracking
    current_period_end = models.DateTimeField(
        help_text="When the current billing period ends"
    )
    
    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        
        # Performance indexes
        indexes = [
            # Multi-tenant + status queries (for billing, renewals, etc.)
            models.Index(fields=['organization', 'status'], name='crm_sub_org_status_idx'),
            # Customer subscription lookups
            models.Index(fields=['customer', 'status'], name='crm_sub_cust_status_idx'),
            # Billing period queries (for renewal processing)
            models.Index(fields=['organization', 'current_period_end'], name='crm_sub_org_period_idx'),
        ]
    
    def __str__(self) -> str:
        """Human-readable representation of the subscription."""
        return f"{self.customer.name} - {self.plan_name} ({self.status})"
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status == self.Status.ACTIVE
    
    @property
    def is_expiring_soon(self) -> bool:
        """
        Check if subscription is expiring within the next 7 days.
        
        This is a simple computed property that can help with renewal notifications.
        Complex business logic for "what constitutes expiring soon" should be in Services.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.is_active:
            return False
        
        return self.current_period_end <= timezone.now() + timedelta(days=7)