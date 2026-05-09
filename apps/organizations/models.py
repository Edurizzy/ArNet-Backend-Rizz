"""
Organization models for ArNet platform.

The Organization model is the core of our multi-tenant architecture.
Think of it as the "company" or "workspace" that users belong to.
Each organization has its own isolated data space.
"""

import re
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.common.models import UUIDModel, TimeStampedModel, SoftDeleteModel


class OrganizationQuerySet(models.QuerySet):
    """
    Custom QuerySet for Organization model.
    
    Provides common query methods for organizations.
    """
    
    def active(self):
        """Return only active organizations."""
        return self.filter(is_active=True, deleted_at__isnull=True)
    
    def by_domain(self, domain: str):
        """Find organization by email domain."""
        return self.filter(email_domains__icontains=domain)


class OrganizationManager(models.Manager):
    """
    Custom manager for Organization model.
    """
    
    def get_queryset(self):
        return OrganizationQuerySet(self.model, using=self._db)
    
    def active(self):
        """Get only active organizations."""
        return self.get_queryset().active()
    
    def create_organization(self, name: str, admin_email: str, **extra_fields):
        """
        Create a new organization with proper setup.
        
        This is a convenience method that handles:
        - Slug generation
        - Initial setup
        - Validation
        """
        if not name:
            raise ValueError('Organization name is required')
        
        if not admin_email:
            raise ValueError('Admin email is required')
        
        # Generate a unique slug
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        
        while self.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        organization = self.model(
            name=name,
            slug=slug,
            admin_email=admin_email,
            **extra_fields
        )
        
        organization.full_clean()
        organization.save()
        
        return organization


class Organization(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """
    Organization model representing a tenant in the multi-tenant system.
    
    Each organization is like a separate "company" using our platform.
    All user data is scoped to their organization, ensuring complete
    data isolation between tenants.
    """
    
    class SubscriptionTier(models.TextChoices):
        """
        Subscription tiers for organizations.
        This will be used for feature gating and billing.
        """
        FREE = 'free', _('Free')
        STARTER = 'starter', _('Starter')
        PROFESSIONAL = 'professional', _('Professional')
        ENTERPRISE = 'enterprise', _('Enterprise')
    
    class Status(models.TextChoices):
        """
        Organization status options.
        """
        ACTIVE = 'active', _('Active')
        SUSPENDED = 'suspended', _('Suspended')
        TRIAL = 'trial', _('Trial')
        INACTIVE = 'inactive', _('Inactive')
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        help_text="Organization name (e.g., 'Acme Corporation')"
    )
    
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-safe version of organization name"
    )
    
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name for the organization (optional)"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Organization description"
    )
    
    # Contact Information
    admin_email = models.EmailField(
        help_text="Primary admin email for the organization"
    )
    
    website = models.URLField(
        blank=True,
        help_text="Organization website URL"
    )
    
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Organization phone number"
    )
    
    # Address Information
    address_line_1 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Street address"
    )
    
    address_line_2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Apartment, suite, etc."
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City"
    )
    
    state_province = models.CharField(
        max_length=100,
        blank=True,
        help_text="State or Province"
    )
    
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Postal or ZIP code"
    )
    
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Country"
    )
    
    # Status and Settings
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
        help_text="Current organization status"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the organization is active"
    )
    
    # Subscription Information
    subscription_tier = models.CharField(
        max_length=20,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.FREE,
        help_text="Current subscription tier"
    )
    
    trial_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the trial period ends"
    )
    
    # Domain-based user authentication
    email_domains = models.TextField(
        blank=True,
        help_text="Comma-separated list of email domains for auto-assignment (e.g., 'acme.com,acme.org')"
    )
    
    # Feature Flags and Limits
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="Organization-specific feature flags and settings"
    )
    
    limits = models.JSONField(
        default=dict,
        blank=True,
        help_text="Usage limits for the organization (users, storage, etc.)"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional organization metadata"
    )
    
    # Custom Manager
    objects = OrganizationManager()
    
    class Meta:
        db_table = 'organizations'
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['subscription_tier']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.display_name or self.name
    
    def clean(self):
        """
        Validate the organization data.
        """
        super().clean()
        
        # Validate slug format
        if self.slug:
            if not re.match(r'^[a-z0-9-]+$', self.slug):
                raise ValidationError({
                    'slug': 'Slug can only contain lowercase letters, numbers, and hyphens.'
                })
        
        # Validate email domains format
        if self.email_domains:
            domains = [domain.strip() for domain in self.email_domains.split(',')]
            for domain in domains:
                if domain and not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
                    raise ValidationError({
                        'email_domains': f'Invalid domain format: {domain}'
                    })
    
    def save(self, *args, **kwargs):
        """
        Override save to handle slug generation and validation.
        """
        # Generate slug if not provided
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        
        # Set display_name to name if not provided
        if not self.display_name and self.name:
            self.display_name = self.name
        
        # Initialize default features and limits
        if not self.features:
            self.features = self.get_default_features()
        
        if not self.limits:
            self.limits = self.get_default_limits()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_default_features(self) -> dict:
        """
        Get default feature flags based on subscription tier.
        """
        features = {
            'ai_assistant': False,
            'advanced_automation': False,
            'custom_integrations': False,
            'priority_support': False,
            'sso': False,
            'audit_logs': False,
            'white_labeling': False,
        }
        
        # Enable features based on subscription tier
        if self.subscription_tier in [self.SubscriptionTier.STARTER, 
                                     self.SubscriptionTier.PROFESSIONAL, 
                                     self.SubscriptionTier.ENTERPRISE]:
            features['ai_assistant'] = True
        
        if self.subscription_tier in [self.SubscriptionTier.PROFESSIONAL, 
                                     self.SubscriptionTier.ENTERPRISE]:
            features.update({
                'advanced_automation': True,
                'priority_support': True,
                'audit_logs': True,
            })
        
        if self.subscription_tier == self.SubscriptionTier.ENTERPRISE:
            features.update({
                'custom_integrations': True,
                'sso': True,
                'white_labeling': True,
            })
        
        return features
    
    def get_default_limits(self) -> dict:
        """
        Get default usage limits based on subscription tier.
        """
        limits_map = {
            self.SubscriptionTier.FREE: {
                'max_users': 3,
                'max_storage_mb': 100,
                'max_api_calls_per_month': 1000,
                'max_automations': 5,
            },
            self.SubscriptionTier.STARTER: {
                'max_users': 10,
                'max_storage_mb': 1000,  # 1GB
                'max_api_calls_per_month': 10000,
                'max_automations': 25,
            },
            self.SubscriptionTier.PROFESSIONAL: {
                'max_users': 50,
                'max_storage_mb': 10000,  # 10GB
                'max_api_calls_per_month': 100000,
                'max_automations': 100,
            },
            self.SubscriptionTier.ENTERPRISE: {
                'max_users': -1,  # Unlimited
                'max_storage_mb': -1,  # Unlimited
                'max_api_calls_per_month': -1,  # Unlimited
                'max_automations': -1,  # Unlimited
            },
        }
        
        return limits_map.get(self.subscription_tier, limits_map[self.SubscriptionTier.FREE])
    
    def has_feature(self, feature_name: str) -> bool:
        """
        Check if the organization has a specific feature enabled.
        """
        return self.features.get(feature_name, False)
    
    def get_limit(self, limit_name: str) -> int:
        """
        Get a specific usage limit for the organization.
        Returns -1 for unlimited.
        """
        return self.limits.get(limit_name, 0)
    
    def is_within_limit(self, limit_name: str, current_usage: int) -> bool:
        """
        Check if current usage is within the specified limit.
        """
        limit = self.get_limit(limit_name)
        return limit == -1 or current_usage < limit  # -1 means unlimited
    
    def get_user_count(self) -> int:
        """
        Get the current number of users in the organization.
        """
        # Import here to avoid circular imports
        from apps.iam.models import User
        return User.objects.filter(organization=self, is_active=True).count()
    
    def can_add_user(self) -> bool:
        """
        Check if the organization can add another user.
        """
        current_users = self.get_user_count()
        return self.is_within_limit('max_users', current_users)
    
    @property
    def is_trial(self) -> bool:
        """
        Check if the organization is in trial status.
        """
        return self.status == self.Status.TRIAL
    
    @property
    def is_enterprise(self) -> bool:
        """
        Check if the organization has enterprise subscription.
        """
        return self.subscription_tier == self.SubscriptionTier.ENTERPRISE
    
    def get_email_domain_list(self) -> list:
        """
        Get list of email domains for the organization.
        """
        if not self.email_domains:
            return []
        return [domain.strip() for domain in self.email_domains.split(',') if domain.strip()]