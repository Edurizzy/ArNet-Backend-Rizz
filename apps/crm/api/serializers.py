"""
CRM API Serializers for ArNet Platform.

Serializers handle the conversion between JSON/HTTP data and Python objects.
They are responsible ONLY for:
1. Data format validation (types, required fields, formats)
2. Basic field-level validation 
3. Serialization of model instances to JSON

They should NOT contain:
- Business logic (belongs in Services)
- Complex cross-field validation (belongs in Services)  
- Database operations (belongs in Services/Selectors)

Think of serializers as "data translators" and "basic validators" - they ensure
the data format is correct before passing it to the business logic layer.
"""

from rest_framework import serializers
from django.core.validators import EmailValidator
from datetime import datetime
from typing import Dict, Any

from ..models import Customer, Subscription


# =============================================================================
# CUSTOMER SERIALIZERS
# =============================================================================

class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for Customer model with basic validation.
    
    This handles the conversion between JSON and Customer objects,
    with basic field validation but no business logic.
    
    Example JSON:
    {
        "name": "John Doe",
        "email": "john@example.com", 
        "phone": "+1234567890",
        "document_id": "123.456.789-00",
        "status": "active",
        "tags": ["vip", "enterprise"]
    }
    """
    
    # Custom validation for email field
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Valid email address for customer communication"
    )
    
    # Document ID with basic format validation
    document_id = serializers.CharField(
        max_length=20,
        help_text="Tax document number (CPF/CNPJ format)"
    )
    
    # Phone field with basic validation
    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Primary phone number"
    )
    
    # Tags field - list of strings
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
        help_text="List of tags for customer categorization"
    )
    
    # Status field with choices validation
    status = serializers.ChoiceField(
        choices=Customer.Status.choices,
        required=False,
        default=Customer.Status.LEAD,
        help_text="Current customer relationship status"
    )
    
    class Meta:
        model = Customer
        fields = [
            'id',
            'name', 
            'email',
            'phone',
            'document_id',
            'status',
            'tags',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_name(self, value: str) -> str:
        """
        Validate customer name field.
        
        Basic field-level validation - just format checking.
        Business rules like "no duplicate names" belong in Services.
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Customer name cannot be empty")
        
        # Basic format validation
        name = value.strip()
        if len(name) < 2:
            raise serializers.ValidationError("Customer name must be at least 2 characters")
        
        if len(name) > 255:
            raise serializers.ValidationError("Customer name cannot exceed 255 characters")
        
        return name
    
    def validate_document_id(self, value: str) -> str:
        """
        Validate document ID format.
        
        Basic format validation only - uniqueness checking happens in Services.
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Document ID is required")
        
        document_id = value.strip()
        
        # Basic format check - should contain only numbers, dots, dashes, slashes
        import re
        if not re.match(r'^[\d\.\-\/]+$', document_id):
            raise serializers.ValidationError(
                "Document ID must contain only numbers, dots, dashes, and slashes"
            )
        
        return document_id
    
    def validate_tags(self, value: list) -> list:
        """
        Validate tags list.
        
        Basic validation - format and length checking.
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list")
        
        # Validate individual tags
        validated_tags = []
        for tag in value:
            if not isinstance(tag, str):
                raise serializers.ValidationError("Each tag must be a string")
            
            tag_clean = tag.strip().lower()
            if not tag_clean:
                continue  # Skip empty tags
            
            if len(tag_clean) > 50:
                raise serializers.ValidationError("Each tag must be 50 characters or less")
            
            # Avoid duplicate tags
            if tag_clean not in validated_tags:
                validated_tags.append(tag_clean)
        
        return validated_tags


class CustomerCreateSerializer(CustomerSerializer):
    """
    Serializer specifically for creating customers.
    
    This makes certain fields required that might be optional for updates.
    """
    
    name = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Full name or company name (required)"
    )
    
    email = serializers.EmailField(
        required=True,
        validators=[EmailValidator()],
        help_text="Valid email address (required)"
    )
    
    document_id = serializers.CharField(
        max_length=20,
        required=True,
        help_text="Tax document number (required)"
    )


class CustomerListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for customer list views.
    
    Contains only essential fields for performance optimization
    in list endpoints where we don't need all details.
    """
    
    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'email', 
            'status',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# =============================================================================
# SUBSCRIPTION SERIALIZERS  
# =============================================================================

class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for Subscription model with basic validation.
    
    Example JSON:
    {
        "customer_id": "123e4567-e89b-12d3-a456-426614174000",
        "plan_name": "Premium Plan",
        "status": "active", 
        "current_period_end": "2024-12-31T23:59:59Z"
    }
    """
    
    # Customer field - we'll use customer_id in requests
    customer_id = serializers.UUIDField(
        write_only=True,
        help_text="UUID of the customer for this subscription"
    )
    
    # Read-only customer details for responses
    customer = CustomerListSerializer(read_only=True)
    
    # Plan name validation
    plan_name = serializers.CharField(
        max_length=100,
        help_text="Name of the subscribed plan or service"
    )
    
    # Status with choices validation
    status = serializers.ChoiceField(
        choices=Subscription.Status.choices,
        required=False,
        default=Subscription.Status.ACTIVE,
        help_text="Current subscription status"
    )
    
    # Period end date validation
    current_period_end = serializers.DateTimeField(
        help_text="When the current billing period ends (ISO format)"
    )
    
    class Meta:
        model = Subscription
        fields = [
            'id',
            'customer_id',
            'customer',
            'plan_name',
            'status', 
            'current_period_end',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'customer', 'created_at', 'updated_at']
    
    def validate_plan_name(self, value: str) -> str:
        """
        Validate plan name field.
        
        Basic format validation only.
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Plan name cannot be empty")
        
        plan_name = value.strip()
        if len(plan_name) < 2:
            raise serializers.ValidationError("Plan name must be at least 2 characters")
        
        return plan_name
    
    def validate_current_period_end(self, value: datetime) -> datetime:
        """
        Validate period end date format.
        
        Basic validation - business rules about future dates are in Services.
        """
        if not value:
            raise serializers.ValidationError("Period end date is required")
        
        # The datetime is already parsed by DRF, just ensure it's valid
        return value


class SubscriptionCreateSerializer(SubscriptionSerializer):
    """
    Serializer specifically for creating subscriptions.
    
    Makes all required fields explicit.
    """
    
    customer_id = serializers.UUIDField(
        required=True,
        help_text="UUID of the customer (required)"
    )
    
    plan_name = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Plan name (required)"
    )
    
    current_period_end = serializers.DateTimeField(
        required=True,
        help_text="Billing period end date (required)"
    )


class SubscriptionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for subscription list views.
    
    Includes customer name for quick reference without full customer object.
    """
    
    customer_name = serializers.CharField(
        source='customer.name', 
        read_only=True
    )
    
    customer_email = serializers.CharField(
        source='customer.email',
        read_only=True
    )
    
    class Meta:
        model = Subscription
        fields = [
            'id',
            'customer_name',
            'customer_email',
            'plan_name',
            'status',
            'current_period_end',
            'created_at'
        ]
        read_only_fields = ['id', 'customer_name', 'customer_email', 'created_at']


# =============================================================================
# FILTER SERIALIZERS (for query parameters)
# =============================================================================

class CustomerFilterSerializer(serializers.Serializer):
    """
    Serializer for customer list filtering query parameters.
    
    This validates URL query parameters like:
    GET /api/v1/crm/customers/?status=active&search=john&tags=vip,premium
    
    This helps ensure API consumers send valid filter parameters.
    """
    
    status = serializers.ChoiceField(
        choices=Customer.Status.choices,
        required=False,
        help_text="Filter by customer status"
    )
    
    search = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Search in name, email, or document ID"
    )
    
    tags = serializers.CharField(
        required=False,
        help_text="Comma-separated list of tags to filter by"
    )
    
    def validate_tags(self, value: str) -> list:
        """
        Convert comma-separated tags string to list.
        
        Example: "vip,premium,enterprise" -> ["vip", "premium", "enterprise"]
        """
        if not value:
            return []
        
        tags = [tag.strip().lower() for tag in value.split(',') if tag.strip()]
        return tags


class SubscriptionFilterSerializer(serializers.Serializer):
    """
    Serializer for subscription list filtering query parameters.
    """
    
    status = serializers.ChoiceField(
        choices=Subscription.Status.choices,
        required=False,
        help_text="Filter by subscription status"
    )
    
    customer_id = serializers.UUIDField(
        required=False,
        help_text="Filter by specific customer UUID"
    )
    
    plan_name = serializers.CharField(
        max_length=100,
        required=False,
        help_text="Filter by plan name (partial match)"
    )
    
    expiring_soon = serializers.BooleanField(
        required=False,
        help_text="Filter subscriptions expiring within 7 days"
    )


# =============================================================================  
# BULK OPERATION SERIALIZERS
# =============================================================================

class BulkCustomerStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk customer status updates.
    
    Example request:
    POST /api/v1/crm/customers/bulk-update-status/
    {
        "customer_ids": ["uuid1", "uuid2", "uuid3"],
        "new_status": "active"
    }
    """
    
    customer_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,  # Reasonable limit for bulk operations
        help_text="List of customer UUIDs to update (max 100)"
    )
    
    new_status = serializers.ChoiceField(
        choices=Customer.Status.choices,
        help_text="New status to apply to all customers"
    )
    
    def validate_customer_ids(self, value: list) -> list:
        """
        Validate customer IDs list.
        
        Basic validation - existence checking happens in Services.
        """
        if len(value) > 100:
            raise serializers.ValidationError("Cannot update more than 100 customers at once")
        
        # Remove duplicates while preserving order
        unique_ids = []
        seen = set()
        for customer_id in value:
            if customer_id not in seen:
                unique_ids.append(customer_id)
                seen.add(customer_id)
        
        return unique_ids