from django.apps import AppConfig


class MetaIntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations.meta"
    label = "meta_integration"
    verbose_name = "Meta Integration"
