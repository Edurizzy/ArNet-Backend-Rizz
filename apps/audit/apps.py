"""
Audit app configuration for ArNet platform.

This app handles audit logging, compliance tracking, and security monitoring
for all actions performed within the platform.
"""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit'
    verbose_name = 'Audit & Compliance'
    
    def ready(self):
        """
        Perform initialization tasks when the app is ready.
        """
        # Import signals to ensure they're registered
        # from . import signals  # Will be created later if needed
        pass