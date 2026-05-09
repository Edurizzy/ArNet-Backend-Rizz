"""
IAM app configuration for ArNet platform.

This app handles Identity and Access Management including:
- Custom user model
- Authentication
- Authorization
- Role-based access control (RBAC)
"""

from django.apps import AppConfig


class IamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.iam'
    verbose_name = 'Identity & Access Management'
    
    def ready(self):
        """
        Perform initialization tasks when the app is ready.
        """
        # Import signals to ensure they're registered
        # from . import signals  # Will be created later if needed
        pass