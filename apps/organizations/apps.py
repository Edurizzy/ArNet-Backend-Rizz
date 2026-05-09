"""
Organizations app configuration for ArNet platform.

This app manages tenant organizations and their settings,
subscription information, and organizational hierarchies.
"""

from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.organizations'
    verbose_name = 'Organizations'
    
    def ready(self):
        """
        Perform initialization tasks when the app is ready.
        """
        # Import signals to ensure they're registered
        # from . import signals  # Will be created later if needed
        pass