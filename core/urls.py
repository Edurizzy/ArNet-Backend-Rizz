"""
URL Configuration for ArNet project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# Core URL patterns
urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # Health check endpoint
    path('health/', include('health_check.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API endpoints
    path('api/v1/', include([
        # Authentication & User Management
        path('auth/', include('apps.iam.api.urls')),
        
        # Organizations
        path('organizations/', include('apps.organizations.api.urls')),
        
        # Audit logs
        path('audit/', include('apps.audit.api.urls')),
        
        # CRM (Customer Relationship Management)
        path('crm/', include('apps.crm.api.urls')),
        
        # Helpdesk (Support Operations & Communication)
        path('helpdesk/', include('apps.helpdesk.api.urls')),
    ])),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug toolbar for development
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

# Customize admin site
admin.site.site_header = "ArNet Administration"
admin.site.site_title = "ArNet Admin Portal"
admin.site.index_title = "Welcome to ArNet Administration"