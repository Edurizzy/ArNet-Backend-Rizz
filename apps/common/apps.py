"""
Common app configuration for ArNet platform.

This app contains shared models, utilities, and base classes
that are used across multiple applications.
"""

from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    verbose_name = 'Common'
    
    def ready(self):
        """
        Perform initialization tasks when the app is ready.
        This is where we can register signals, perform setup tasks, etc.
        """
        pass