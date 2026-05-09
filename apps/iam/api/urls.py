"""
URL patterns for IAM API endpoints.
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    # Authentication endpoints
    path('login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', views.logout, name='logout'),
    
    # User registration and management
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('me/', views.current_user, name='current_user'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    
    # Password management
    path('change-password/', views.change_password, name='change_password'),
    path('password-reset/', views.request_password_reset, name='password_reset'),
    path('password-reset/confirm/', views.confirm_password_reset, name='password_reset_confirm'),
    
    # Email verification
    path('verify-email/', views.verify_email, name='verify_email'),
]