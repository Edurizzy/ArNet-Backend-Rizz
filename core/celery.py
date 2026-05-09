"""
Celery configuration for ArNet platform.

Celery is our "background job processor" - think of it as having
a team of workers that handle tasks that don't need immediate response:
- Sending emails
- Processing files
- Running AI operations
- Generating reports
- Cleanup tasks

This configuration ensures proper tenant isolation even in background tasks.
"""

import os
import logging
from typing import Dict, Any

from celery import Celery
from django.conf import settings

# Set default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.local')

# Initialize Celery app
app = Celery('arnet')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Setup logging
logger = logging.getLogger(__name__)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Debug task to test Celery configuration.
    
    Usage:
    from core.celery import debug_task
    debug_task.delay()
    """
    logger.info(f'Request: {self.request!r}')
    return 'Celery is working!'


class TenantAwareTask:
    """
    Base class for tenant-aware Celery tasks.
    
    This ensures that background tasks maintain tenant context
    and can properly scope their operations to the correct organization.
    """
    
    def __init__(self):
        self.current_organization = None
        self.current_user = None
    
    def setup_tenant_context(self, organization_id: str, user_id: str = None):
        """
        Set up tenant context for the task.
        
        Call this at the beginning of your task to establish
        which organization's data you're working with.
        """
        try:
            from apps.organizations.models import Organization
            from apps.iam.models import User
            
            # Load organization
            if organization_id:
                self.current_organization = Organization.objects.get(id=organization_id)
            
            # Load user if provided
            if user_id:
                self.current_user = User.objects.get(id=user_id)
            
            logger.info(
                f"Task context: org={self.current_organization.slug if self.current_organization else None}, "
                f"user={self.current_user.email if self.current_user else None}"
            )
            
        except Exception as e:
            logger.error(f"Failed to setup tenant context: {e}")
            raise
    
    def log_task_audit(self, action: str, details: Dict[str, Any] = None):
        """
        Log task execution to audit trail.
        """
        try:
            from apps.audit.models import AuditLog
            
            AuditLog.objects.log(
                action=f"task_{action}",
                organization_id=self.current_organization.id if self.current_organization else None,
                actor_user_id=self.current_user.id if self.current_user else None,
                actor_type='system',
                details=details or {}
            )
        except Exception as e:
            logger.error(f"Failed to log task audit: {e}")


# Celery signal handlers for monitoring and debugging

@app.task(bind=True)
def handle_task_failure(self, task_id, error, traceback):
    """
    Handle task failures with proper logging and notifications.
    """
    logger.error(
        f"Task {task_id} failed with error: {error}\n"
        f"Traceback: {traceback}"
    )
    
    # TODO: Add failure notifications (email, Slack, etc.)
    # TODO: Add failure metrics for monitoring


@app.task(bind=True, ignore_result=True)
def cleanup_old_audit_logs(self, days: int = 90):
    """
    Cleanup old audit logs to manage database size.
    
    Args:
        days: Number of days to retain audit logs
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.audit.models import AuditLog
    
    # Calculate cutoff date
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Delete old audit logs
    deleted_count = AuditLog.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old audit logs older than {days} days")
    
    return {
        'deleted_count': deleted_count,
        'cutoff_date': cutoff_date.isoformat()
    }


@app.task(bind=True, ignore_result=True)
def send_notification_email(
    self,
    organization_id: str,
    recipient_email: str,
    subject: str,
    message: str,
    template_name: str = None,
    template_context: Dict[str, Any] = None
):
    """
    Send notification email with tenant context.
    
    This is a foundation task that will be extended with proper
    email templating and delivery logic.
    """
    task = TenantAwareTask()
    task.setup_tenant_context(organization_id)
    
    try:
        # TODO: Implement actual email sending logic
        # This would typically use Django's email backend
        # with proper templating and organization branding
        
        logger.info(
            f"Email notification sent to {recipient_email} "
            f"for organization {task.current_organization.slug if task.current_organization else 'unknown'}"
        )
        
        # Log the notification
        task.log_task_audit('email_sent', {
            'recipient': recipient_email,
            'subject': subject,
            'template': template_name
        })
        
        return {
            'status': 'sent',
            'recipient': recipient_email,
            'organization': task.current_organization.slug if task.current_organization else None
        }
        
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        raise


@app.task(bind=True, ignore_result=True)
def process_organization_data(self, organization_id: str, operation: str, data: Dict[str, Any]):
    """
    Generic task for processing organization-specific data.
    
    This can be used for various background operations like:
    - Data exports
    - Report generation
    - Bulk operations
    - AI processing
    """
    task = TenantAwareTask()
    task.setup_tenant_context(organization_id)
    
    try:
        logger.info(
            f"Processing {operation} for organization {task.current_organization.slug}"
        )
        
        # TODO: Implement specific operation handlers
        # This would dispatch to different processors based on operation type
        
        # Log the operation
        task.log_task_audit(f'data_processing_{operation}', {
            'operation': operation,
            'data_keys': list(data.keys()) if data else []
        })
        
        return {
            'status': 'completed',
            'operation': operation,
            'organization': task.current_organization.slug
        }
        
    except Exception as e:
        logger.error(f"Failed to process organization data: {e}")
        
        # Log the failure
        task.log_task_audit(f'data_processing_failed', {
            'operation': operation,
            'error': str(e)
        })
        
        raise


# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Cleanup old audit logs daily at 2 AM
    'cleanup-audit-logs': {
        'task': 'core.celery.cleanup_old_audit_logs',
        'schedule': 60.0 * 60.0 * 24.0,  # Daily
        'options': {'expires': 60.0 * 60.0},  # Expire after 1 hour if not executed
    },
    
    # Health check task every 5 minutes
    'health-check': {
        'task': 'core.celery.debug_task',
        'schedule': 60.0 * 5.0,  # Every 5 minutes
        'options': {'expires': 60.0},  # Expire after 1 minute
    },
}

# Additional Celery configuration
app.conf.update(
    # Task routing (can be used for different worker types)
    task_routes={
        'core.celery.send_notification_email': {'queue': 'notifications'},
        'core.celery.process_organization_data': {'queue': 'data_processing'},
        'core.celery.cleanup_old_audit_logs': {'queue': 'maintenance'},
    },
    
    # Task execution settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Worker settings
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
)