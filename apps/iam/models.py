"""
User models and authentication for ArNet platform.

This module contains the custom User model that serves as the foundation
for authentication and authorization throughout the platform.
"""

import uuid
from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.common.models import UUIDModel, TimeStampedModel, SoftDeleteModel

if TYPE_CHECKING:
    from apps.organizations.models import Organization


class UserManager(BaseUserManager):
    """
    Custom manager for User model.
    
    This manager handles creating users and superusers with proper
    validation and setup.
    """
    
    def create_user(self, email: str, password: str = None, **extra_fields):
        """
        Create and return a regular user.
        
        Think of this as the "standard registration process" for new users.
        """
        if not email:
            raise ValueError('Email address is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        if password:
            user.set_password(password)
        
        user.full_clean()
        user.save(using=self._db)
        
        return user
    
    def create_superuser(self, email: str, password: str = None, **extra_fields):
        """
        Create and return a superuser.
        
        Superusers are like "master keys" - they can access everything.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)
    
    def create_organization_admin(self, email: str, organization: 'Organization', 
                                 password: str = None, **extra_fields):
        """
        Create an organization admin user.
        
        Organization admins are like "department managers" - they have
        full control within their organization but not system-wide.
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_active', True)
        
        user = self.create_user(
            email=email, 
            password=password, 
            organization=organization,
            **extra_fields
        )
        
        # TODO: Assign organization admin role when RBAC is implemented
        
        return user


class User(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel, SoftDeleteModel):
    """
    Custom User model for ArNet platform.
    
    This is the "digital identity" of every person using our platform.
    Each user belongs to an organization (tenant) and has specific roles
    and permissions within that organization.
    """
    
    class Status(models.TextChoices):
        """User status options."""
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        PENDING = 'pending', _('Pending Activation')
        SUSPENDED = 'suspended', _('Suspended')
    
    # Authentication Fields
    email = models.EmailField(
        unique=True,
        help_text="User's email address (used for login)"
    )
    
    # Personal Information
    first_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="User's first name"
    )
    
    last_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="User's last name"
    )
    
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name (auto-generated if not provided)"
    )
    
    # Organization Relationship
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,  # Temporary for migration purposes
        blank=True,
        related_name='users',
        help_text="Organization this user belongs to"
    )
    
    # Status and Permissions
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Current user status"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the user can log in"
    )
    
    is_staff = models.BooleanField(
        default=False,
        help_text="Whether the user can access admin interface"
    )
    
    # Profile Information
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="User's phone number"
    )
    
    avatar = models.URLField(
        blank=True,
        help_text="URL to user's avatar image"
    )
    
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="User's preferred timezone"
    )
    
    language = models.CharField(
        max_length=10,
        default='en',
        help_text="User's preferred language"
    )
    
    # Authentication Tracking
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of last login"
    )
    
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's email is verified"
    )
    
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the email was verified"
    )
    
    # Security Settings
    two_factor_enabled = models.BooleanField(
        default=False,
        help_text="Whether two-factor authentication is enabled"
    )
    
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the password was last changed"
    )
    
    # Preferences
    preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="User preferences and settings"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional user metadata"
    )
    
    # Django authentication configuration
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['email']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.get_display_name()
    
    def clean(self):
        """
        Validate user data.
        """
        super().clean()
        
        # Normalize email
        if self.email:
            self.email = self.email.lower().strip()
        
        # Validate email uniqueness within organization (future enhancement)
        # This could be used for enterprise customers who want email reuse across orgs
    
    def save(self, *args, **kwargs):
        """
        Override save to handle auto-generation of display name and other setup.
        """
        # Generate display name if not provided
        if not self.display_name:
            self.display_name = self.get_auto_display_name()
        
        # Set email verification status for new users
        if not self.pk and not self.email_verified_at:
            # New user - will need email verification
            self.status = self.Status.PENDING
        
        # Update password change timestamp
        if self.pk:
            try:
                old_user = User.objects.get(pk=self.pk)
                if old_user.password != self.password:
                    self.password_changed_at = timezone.now()
            except User.DoesNotExist:
                pass
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_display_name(self) -> str:
        """
        Get the user's display name.
        """
        if self.display_name:
            return self.display_name
        
        return self.get_auto_display_name()
    
    def get_auto_display_name(self) -> str:
        """
        Auto-generate display name from available information.
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            # Use email prefix as fallback
            return self.email.split('@')[0] if self.email else 'User'
    
    def get_full_name(self) -> str:
        """
        Get user's full name.
        """
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self) -> str:
        """
        Get user's short name.
        """
        return self.first_name or self.email.split('@')[0] if self.email else 'User'
    
    def verify_email(self):
        """
        Mark user's email as verified and activate if needed.
        """
        self.email_verified = True
        self.email_verified_at = timezone.now()
        
        if self.status == self.Status.PENDING:
            self.status = self.Status.ACTIVE
        
        self.save(update_fields=['email_verified', 'email_verified_at', 'status'])
    
    def activate(self):
        """
        Activate the user account.
        """
        self.is_active = True
        self.status = self.Status.ACTIVE
        self.save(update_fields=['is_active', 'status'])
    
    def deactivate(self):
        """
        Deactivate the user account.
        """
        self.is_active = False
        self.status = self.Status.INACTIVE
        self.save(update_fields=['is_active', 'status'])
    
    def suspend(self, reason: str = None):
        """
        Suspend the user account.
        """
        self.is_active = False
        self.status = self.Status.SUSPENDED
        
        if reason and 'suspension_reason' not in self.metadata:
            self.metadata['suspension_reason'] = reason
            self.metadata['suspended_at'] = timezone.now().isoformat()
        
        self.save(update_fields=['is_active', 'status', 'metadata'])
    
    def has_organization_permission(self, permission: str) -> bool:
        """
        Check if user has a specific permission within their organization.
        
        This is a placeholder for future RBAC implementation.
        """
        # TODO: Implement proper RBAC permission checking
        return self.is_active and self.organization is not None
    
    def is_organization_admin(self) -> bool:
        """
        Check if user is an admin of their organization.
        
        This is a placeholder for future role-based checking.
        """
        # TODO: Implement proper role checking
        return self.is_staff or self.is_superuser
    
    def get_organization_role(self) -> str:
        """
        Get user's role within their organization.
        
        This is a placeholder for future RBAC implementation.
        """
        # TODO: Implement proper role system
        if self.is_superuser:
            return 'super_admin'
        elif self.is_staff:
            return 'admin'
        else:
            return 'member'
    
    def update_login_info(self, ip_address: str = None):
        """
        Update last login information.
        """
        self.last_login = timezone.now()
        if ip_address:
            self.last_login_ip = ip_address
        
        self.save(update_fields=['last_login', 'last_login_ip'])
    
    def set_preference(self, key: str, value):
        """
        Set a user preference.
        """
        if not isinstance(self.preferences, dict):
            self.preferences = {}
        
        self.preferences[key] = value
        self.save(update_fields=['preferences'])
    
    def get_preference(self, key: str, default=None):
        """
        Get a user preference.
        """
        if not isinstance(self.preferences, dict):
            return default
        
        return self.preferences.get(key, default)
    
    @property
    def is_email_verified(self) -> bool:
        """
        Check if user's email is verified.
        """
        return self.email_verified
    
    @property
    def needs_password_change(self) -> bool:
        """
        Check if user needs to change password (e.g., temporary password).
        """
        # TODO: Implement password policy checking
        return False
    
    @property
    def can_login(self) -> bool:
        """
        Check if user can log in.
        """
        return (
            self.is_active and 
            self.status == self.Status.ACTIVE and
            self.organization and 
            self.organization.is_active
        )