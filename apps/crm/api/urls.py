"""
CRM API URL Configuration for ArNet Platform.

This module defines the URL routes for CRM API endpoints using Django REST Framework's
router system. The router automatically creates standard REST URL patterns:

Customer Endpoints:
- GET    /customers/                     - List customers (with filtering)
- POST   /customers/                     - Create new customer
- GET    /customers/{id}/                - Retrieve specific customer
- PUT    /customers/{id}/                - Update customer (full)
- PATCH  /customers/{id}/                - Update customer (partial)  
- DELETE /customers/{id}/                - Delete customer (soft delete)
- POST   /customers/bulk-update-status/  - Bulk update customer status

Subscription Endpoints:
- GET    /subscriptions/                 - List subscriptions (with filtering)
- POST   /subscriptions/                 - Create new subscription
- GET    /subscriptions/{id}/            - Retrieve specific subscription
- PUT    /subscriptions/{id}/            - Update subscription
- PATCH  /subscriptions/{id}/            - Update subscription (partial)
- POST   /subscriptions/{id}/cancel/     - Cancel subscription
- POST   /subscriptions/{id}/renew/      - Renew subscription

Why DRF Router?
- Automatically generates RESTful URL patterns
- Consistent URL structure across all resources
- Easy to extend with custom actions
- Integrates seamlessly with API documentation
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet, SubscriptionViewSet


# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

# Create the main router for CRM API endpoints
router = DefaultRouter()

# Register ViewSets with the router
# The first parameter is the URL prefix, the second is the ViewSet class
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

# The router automatically creates these URL patterns:
#
# Customer URLs:
# ^customers/$                     [name='customer-list']           (GET, POST)
# ^customers/(?P<pk>[^/.]+)/$      [name='customer-detail']         (GET, PUT, PATCH, DELETE)
# ^customers/bulk-update-status/$  [name='customer-bulk-update-status'] (POST)
#
# Subscription URLs:  
# ^subscriptions/$                 [name='subscription-list']       (GET, POST)
# ^subscriptions/(?P<pk>[^/.]+)/$  [name='subscription-detail']     (GET, PUT, PATCH, DELETE)
# ^subscriptions/(?P<pk>[^/.]+)/cancel/$ [name='subscription-cancel'] (POST)
# ^subscriptions/(?P<pk>[^/.]+)/renew/$  [name='subscription-renew']  (POST)


# =============================================================================
# URL PATTERNS
# =============================================================================

# Main URL patterns for the CRM API
urlpatterns = [
    # Include all router-generated URLs
    # This creates all the endpoints listed above under the /api/v1/crm/ prefix
    path('', include(router.urls)),
]

# Final URL structure when integrated with core URLs:
# 
# Base: /api/v1/crm/
#
# Customers:
# GET    /api/v1/crm/customers/                     - List customers
# POST   /api/v1/crm/customers/                     - Create customer
# GET    /api/v1/crm/customers/{uuid}/              - Get customer
# PUT    /api/v1/crm/customers/{uuid}/              - Update customer (full)
# PATCH  /api/v1/crm/customers/{uuid}/              - Update customer (partial)
# DELETE /api/v1/crm/customers/{uuid}/              - Delete customer
# POST   /api/v1/crm/customers/bulk-update-status/  - Bulk status update
#
# Subscriptions:
# GET    /api/v1/crm/subscriptions/                 - List subscriptions  
# POST   /api/v1/crm/subscriptions/                 - Create subscription
# GET    /api/v1/crm/subscriptions/{uuid}/          - Get subscription
# PUT    /api/v1/crm/subscriptions/{uuid}/          - Update subscription
# PATCH  /api/v1/crm/subscriptions/{uuid}/          - Update subscription (partial)
# POST   /api/v1/crm/subscriptions/{uuid}/cancel/   - Cancel subscription
# POST   /api/v1/crm/subscriptions/{uuid}/renew/    - Renew subscription
#
# Query Parameters (for list endpoints):
# 
# Customers:
# ?status=active                    - Filter by status
# ?search=john                      - Search in name/email/document
# ?tags=vip,premium                 - Filter by tags
# ?page=2&page_size=20             - Pagination
#
# Subscriptions:
# ?status=active                    - Filter by status  
# ?customer_id={uuid}               - Filter by customer
# ?plan_name=premium                - Filter by plan name
# ?expiring_soon=true               - Filter expiring subscriptions
# ?page=2&page_size=20             - Pagination


# =============================================================================
# API DOCUMENTATION METADATA
# =============================================================================

# This metadata is used by DRF Spectacular for API documentation generation
app_name = 'crm'

# Optional: Custom URL patterns for specific use cases
# You can add custom URLs here if needed, outside of the standard REST patterns

# Example of adding a custom analytics endpoint:
# urlpatterns += [
#     path('analytics/customer-stats/', CustomerStatsView.as_view(), name='customer-stats'),
#     path('analytics/subscription-metrics/', SubscriptionMetricsView.as_view(), name='subscription-metrics'),
# ]

# Example of version-specific URLs:
# urlpatterns = [
#     path('v1/', include(router.urls)),
#     path('v2/', include('apps.crm.api.v2.urls')),  # Future API version
# ]

# For now, we keep it simple with just the standard REST endpoints
# generated by the router. This provides a clean, predictable API structure
# that follows REST conventions and integrates well with frontend applications.