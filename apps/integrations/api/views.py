"""REST API for organization-scoped connected accounts."""

from __future__ import annotations

from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from apps.integrations.models import ConnectedAccount
from core.tenancy.middleware import TenantAwareViewMixin, get_current_tenant

from .serializers import ConnectedAccountSerializer


class ConnectedAccountViewSet(TenantAwareViewMixin, viewsets.ModelViewSet):
    """
    CRUD for integration channels (tokens are write-only; responses use masked hints).

    Organization is taken from JWT tenant context; non-superusers cannot cross tenants.
    """

    queryset = ConnectedAccount.objects.select_related("organization")
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConnectedAccountSerializer
    http_method_names = ["get", "post", "head", "options", "patch", "delete"]

    def perform_create(self, serializer):
        tenant = get_current_tenant(self.request)
        if not tenant or not tenant.organization:
            raise PermissionDenied("Organization context is required.")
        serializer.save(organization=tenant.organization)

    def perform_destroy(self, instance):
        instance.delete()
