"""
Audit logging models for ArNet platform.

These models provide comprehensive audit trails for all actions
performed within the system, essential for security, compliance,
and debugging purposes.
"""

import uuid
import json
from typing import Optional, Dict, Any

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.common.models import UUIDModel, TimeStampedModel

User = get_user_model()


class AuditLogQuerySet(models.QuerySet):
    """
    Custom QuerySet for AuditLog model.
    """
    
    def for_organization(self, organization_id: uuid.UUID):
        """Filter audit logs by organization."""
        return self.filter(organization_id=organization_id)
    
    def for_user(self, user_id: uuid.UUID):
        """Filter audit logs by user."""
        return self.filter(actor_user_id=user_id)
    
    def for_entity(self, entity_type: str, entity_id: uuid.UUID):
        """Filter audit logs for a specific entity."""
        return self.filter(entity_type=entity_type, entity_id=entity_id)
    
    def for_action(self, action: str):
        """Filter audit logs by action type."""
        return self.filter(action=action)
    
    def for_correlation_id(self, correlation_id: str):
        """Filter audit logs by correlation ID (to group related actions)."""
        return self.filter(correlation_id=correlation_id)
    
    def recent(self, days: int = 30):
        """Get recent audit logs within specified days."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)
    
    def security_relevant(self):
        """Get security-relevant audit logs."""
        security_actions = [
            'login', 'logout', 'login_failed',
            'password_change', 'password_reset',
            'permission_grant', 'permission_revoke',
            'user_create', 'user_delete', 'user_suspend',
            'organization_create', 'organization_delete',
            'api_key_create', 'api_key_delete',
        ]
        return self.filter(action__in=security_actions)


class AuditLogManager(models.Manager):
    """
    Custom manager for AuditLog model.
    """
    
    def get_queryset(self):
        return AuditLogQuerySet(self.model, using=self._db)
    
    def log(
        self,
        action: str,
        organization_id: Optional[uuid.UUID] = None,
        actor_user_id: Optional[uuid.UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **extra_fields
    ):
        """
        Convenience method to create audit log entries.
        
        This is like filling out an "incident report" - we record
        what happened, who did it, when, and any relevant details.
        """
        return self.create(
            action=action,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            **extra_fields
        )
    
    def log_user_action(
        self,
        user: User,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        request=None,
        **extra_fields
    ):
        """
        Log an action performed by a user.
        
        This method automatically extracts user and organization
        information from the user object and request.
        """
        # Extract organization from user
        organization_id = None
        if user and hasattr(user, 'organization') and user.organization:
            organization_id = user.organization.id
        
        # Extract request information
        ip_address = None
        user_agent = None
        correlation_id = None
        
        if request:
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            
            # Generate correlation ID for request tracking
            if hasattr(request, 'META'):
                correlation_id = request.META.get('HTTP_X_REQUEST_ID')
            
            if not correlation_id:
                import uuid as uuid_lib
                correlation_id = str(uuid_lib.uuid4())
        
        return self.log(
            action=action,
            organization_id=organization_id,
            actor_user_id=user.id if user else None,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            **extra_fields
        )
    
    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AuditLog(UUIDModel, TimeStampedModel):
    """
    Comprehensive audit log model.
    
    This model is like a "security camera recording" - it captures
    every important action that happens in our system with enough
    detail to understand what happened, when, and by whom.
    
    Key features:
    - Multi-tenant aware (organization scoped)
    - Flexible entity tracking (can audit any model)
    - Correlation IDs for tracking related actions
    - Rich metadata capture
    - Performance optimized with indexes
    """
    
    # Organization (Tenant) Information
    organization_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Organization this audit log belongs to"
    )
    
    # Actor Information (Who performed the action)
    actor_user_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="User who performed the action"
    )
    
    actor_type = models.CharField(
        max_length=50,
        default='user',
        help_text="Type of actor (user, system, api_key, etc.)"
    )
    
    # Action Information (What was done)
    action = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Action that was performed (e.g., 'create', 'update', 'delete')"
    )
    
    action_category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Category of action (e.g., 'auth', 'data', 'admin')"
    )
    
    # Entity Information (What was acted upon)
    entity_type = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Type of entity acted upon (model name)"
    )
    
    entity_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID of the entity acted upon"
    )
    
    entity_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable name of the entity"
    )
    
    # Generic foreign key for direct entity reference (optional)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    object_id = models.UUIDField(
        null=True,
        blank=True
    )
    
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Request Context
    correlation_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="ID to correlate related actions within a request or workflow"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text="User agent string from the request"
    )
    
    session_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Session ID if applicable"
    )
    
    # Outcome and Status
    outcome = models.CharField(
        max_length=20,
        default='success',
        choices=[
            ('success', 'Success'),
            ('failure', 'Failure'),
            ('error', 'Error'),
            ('denied', 'Access Denied'),
        ],
        help_text="Outcome of the action"
    )
    
    status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code if applicable"
    )
    
    # Details and Metadata
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details about the action"
    )
    
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Changes made (before/after values for updates)"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata"
    )
    
    # Timing Information
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of the operation in milliseconds"
    )
    
    # Risk and Security Scoring
    risk_score = models.IntegerField(
        default=0,
        help_text="Risk score for the action (0-100, higher is riskier)"
    )
    
    is_sensitive = models.BooleanField(
        default=False,
        help_text="Whether this action involves sensitive data"
    )
    
    # Custom Manager
    objects = AuditLogManager()
    
    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']
        
        indexes = [
            # Primary indexes for common queries
            models.Index(fields=['organization_id', 'created_at']),
            models.Index(fields=['actor_user_id', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['correlation_id']),
            
            # Security monitoring indexes
            models.Index(fields=['outcome', 'created_at']),
            models.Index(fields=['risk_score', 'created_at']),
            models.Index(fields=['is_sensitive', 'created_at']),
            
            # Performance indexes
            models.Index(fields=['action_category', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]
    
    def __str__(self):
        actor = f"user:{self.actor_user_id}" if self.actor_user_id else "system"
        entity = f" on {self.entity_type}:{self.entity_id}" if self.entity_type else ""
        return f"{actor} {self.action}{entity} at {self.created_at}"
    
    def save(self, *args, **kwargs):
        """
        Override save to set calculated fields.
        """
        # Set action category based on action if not provided
        if not self.action_category and self.action:
            self.action_category = self._get_action_category()
        
        # Calculate risk score if not set
        if self.risk_score == 0:
            self.risk_score = self._calculate_risk_score()
        
        # Set sensitive flag based on action and entity
        if not self.is_sensitive:
            self.is_sensitive = self._is_sensitive_action()
        
        super().save(*args, **kwargs)
    
    def _get_action_category(self) -> str:
        """
        Determine action category based on action name.
        """
        auth_actions = ['login', 'logout', 'register', 'password_change', 'password_reset']
        admin_actions = ['user_create', 'user_delete', 'organization_create', 'permission_grant']
        data_actions = ['create', 'update', 'delete', 'view', 'export']
        
        action_lower = self.action.lower()
        
        if any(auth_action in action_lower for auth_action in auth_actions):
            return 'auth'
        elif any(admin_action in action_lower for admin_action in admin_actions):
            return 'admin'
        elif any(data_action in action_lower for data_action in data_actions):
            return 'data'
        else:
            return 'other'
    
    def _calculate_risk_score(self) -> int:
        """
        Calculate risk score based on action and context.
        """
        score = 0
        
        # Base score by action type
        high_risk_actions = ['delete', 'user_delete', 'permission_grant', 'data_export']
        medium_risk_actions = ['create', 'update', 'user_create', 'password_change']
        
        action_lower = self.action.lower()
        
        if any(action in action_lower for action in high_risk_actions):
            score += 60
        elif any(action in action_lower for action in medium_risk_actions):
            score += 30
        else:
            score += 10
        
        # Increase score for failed actions
        if self.outcome in ['failure', 'error', 'denied']:
            score += 20
        
        # Increase score for admin actions
        if self.action_category == 'admin':
            score += 15
        
        # Increase score for sensitive entities
        sensitive_entities = ['user', 'organization', 'api_key', 'webhook']
        if self.entity_type and any(entity in self.entity_type.lower() for entity in sensitive_entities):
            score += 10
        
        return min(score, 100)  # Cap at 100
    
    def _is_sensitive_action(self) -> bool:
        """
        Determine if this is a sensitive action.
        """
        sensitive_actions = [
            'password_change', 'password_reset', 'api_key_create',
            'user_delete', 'organization_delete', 'data_export',
            'permission_grant', 'permission_revoke'
        ]
        
        return any(action in self.action.lower() for action in sensitive_actions)
    
    @property
    def is_high_risk(self) -> bool:
        """Check if this is a high-risk action."""
        return self.risk_score >= 70
    
    @property
    def is_failure(self) -> bool:
        """Check if this action failed."""
        return self.outcome in ['failure', 'error', 'denied']
    
    def add_detail(self, key: str, value: Any):
        """
        Add a detail to the audit log.
        """
        if not isinstance(self.details, dict):
            self.details = {}
        
        self.details[key] = value
        self.save(update_fields=['details'])
    
    def set_changes(self, before: Dict[str, Any], after: Dict[str, Any]):
        """
        Set before/after changes for update operations.
        """
        self.changes = {
            'before': before,
            'after': after,
            'modified_fields': list(set(before.keys()) & set(after.keys()))
        }
        self.save(update_fields=['changes'])
    
    def get_actor_display(self) -> str:
        """
        Get a human-readable actor description.
        """
        if self.actor_user_id:
            try:
                user = User.objects.get(id=self.actor_user_id)
                return f"{user.get_display_name()} ({user.email})"
            except User.DoesNotExist:
                return f"User {self.actor_user_id} (deleted)"
        
        return f"{self.actor_type.title()} Actor"