"""
Common base models for ArNet platform.

These models provide foundational functionality that should be inherited
by most other models in the system:
- Timestamp tracking
- UUID primary keys
- Tenant awareness
- Soft delete capability
"""

import uuid
from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from apps.organizations.models import Organization


class TimeStampedModel(models.Model):
    """
    Abstract base class that provides timestamp fields.
    
    This is like adding a "born date" and "last modified date" 
    to every record in our database - essential for auditing
    and understanding when things happened.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the record was last updated"
    )
    
    class Meta:
        abstract = True
        
    def save(self, *args, **kwargs):
        """
        Override save to ensure updated_at is always set.
        This is our safety net to ensure timestamps are accurate.
        """
        if not self.created_at:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class UUIDModel(models.Model):
    """
    Abstract base class that provides UUID primary keys.
    
    UUIDs are like "universal fingerprints" - they're unique across
    the entire universe, not just our database. This is crucial for:
    - Distributed systems
    - Avoiding ID conflicts when merging data
    - Security (harder to guess than sequential IDs)
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this record"
    )
    
    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """
    Custom QuerySet for soft delete functionality.
    
    Think of this as a "special lens" that can show or hide
    deleted records based on what we need.
    """
    
    def active(self):
        """Return only non-deleted records."""
        return self.filter(deleted_at__isnull=True)
    
    def deleted(self):
        """Return only soft-deleted records."""
        return self.filter(deleted_at__isnull=False)
    
    def with_deleted(self):
        """Return all records, including deleted ones."""
        return self


class SoftDeleteManager(models.Manager):
    """
    Manager that handles soft delete operations.
    
    This is like having a smart assistant that knows
    whether to show deleted items or hide them.
    """
    
    def get_queryset(self):
        """By default, exclude soft-deleted records."""
        return SoftDeleteQuerySet(self.model, using=self._db).active()
    
    def all_with_deleted(self):
        """Get all records including soft-deleted ones."""
        return SoftDeleteQuerySet(self.model, using=self._db)
    
    def deleted_only(self):
        """Get only soft-deleted records."""
        return SoftDeleteQuerySet(self.model, using=self._db).deleted()


class SoftDeleteModel(models.Model):
    """
    Abstract base class that provides soft delete functionality.
    
    Soft delete means we don't actually remove records from the database,
    we just mark them as "deleted". This is like moving files to the
    trash can instead of permanently deleting them.
    """
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the record was soft deleted"
    )
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()  # Access to all records including deleted
    
    class Meta:
        abstract = True
    
    def delete(self, using=None, keep_parents=False):
        """
        Soft delete the record instead of actually deleting it.
        """
        self.deleted_at = timezone.now()
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """
        Permanently delete the record from the database.
        Use with extreme caution!
        """
        super().delete(using=using, keep_parents=keep_parents)
    
    def restore(self):
        """
        Restore a soft-deleted record.
        """
        self.deleted_at = None
        self.save()
    
    @property
    def is_deleted(self):
        """
        Check if the record is soft-deleted.
        """
        return self.deleted_at is not None


class TenantAwareQuerySet(models.QuerySet):
    """
    Custom QuerySet for tenant-aware models.
    
    This is like having separate "rooms" in our database - each tenant
    only sees their own data, never someone else's.
    """
    
    def for_organization(self, organization_id: uuid.UUID):
        """Filter records for a specific organization."""
        return self.filter(organization_id=organization_id)


class TenantAwareManager(models.Manager):
    """
    Manager that provides tenant-aware query methods.
    
    This manager will be extended later to automatically scope
    queries to the current tenant context.
    """
    
    def get_queryset(self):
        return TenantAwareQuerySet(self.model, using=self._db)
    
    def for_organization(self, organization_id: uuid.UUID):
        """Get records for a specific organization."""
        return self.get_queryset().for_organization(organization_id)


class TenantAwareModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """
    Base model that combines UUID, timestamps, soft delete, and tenant awareness.
    
    This is our "super model" that most business entities will inherit from.
    It gives every model:
    1. UUID primary key (universal uniqueness)
    2. Timestamps (audit trail)
    3. Soft delete (data safety)
    4. Tenant awareness (multi-tenant isolation)
    """
    
    # We use a string reference to avoid circular imports during initial migrations
    # This will be resolved to the actual Organization model at runtime
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,  # Temporary - will be required after initial setup
        blank=True,
        help_text="Organization this record belongs to"
    )
    
    objects = TenantAwareManager()
    
    class Meta:
        abstract = True
        indexes = [
            # Index on organization for fast tenant filtering
            models.Index(fields=['organization']),
            # Compound index for organization + created_at (common query pattern)
            models.Index(fields=['organization', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        """
        Override save to enforce tenant context and validation.
        """
        # TODO: Add automatic organization assignment from request context
        # This will be implemented when we add the tenancy middleware
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """
        Validate the model instance.
        """
        super().clean()
        
        # TODO: Add tenant-specific validation rules
        # For example, ensuring unique constraints within tenant scope


class BaseModel(UUIDModel, TimeStampedModel):
    """
    Simplified base model for entities that don't need tenant awareness.
    
    Use this for system-wide entities like:
    - User preferences
    - System configurations
    - Platform-wide settings
    """
    
    class Meta:
        abstract = True


# Utility functions for working with tenant-aware models

def get_tenant_aware_models():
    """
    Get all models that inherit from TenantAwareModel.
    Useful for migrations and tenant data operations.
    """
    from django.apps import apps
    
    tenant_models = []
    for model in apps.get_models():
        if issubclass(model, TenantAwareModel) and not model._meta.abstract:
            tenant_models.append(model)
    
    return tenant_models


def validate_tenant_consistency(instance: TenantAwareModel, organization: 'Organization') -> bool:
    """
    Validate that a model instance belongs to the specified organization.
    
    This is a security check to prevent tenant data leakage.
    """
    return instance.organization_id == organization.id if instance.organization_id else False