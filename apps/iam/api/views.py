"""
Authentication and user management API views.
"""

from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, extend_schema_view

from ..models import User
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserProfileSerializer,
    PasswordChangeSerializer,
    EmailVerificationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view with tenant claims.
    
    This endpoint is like the "front desk" of a secure building -
    it checks your credentials and gives you a key card that works
    for your specific floor (organization).
    """
    serializer_class = CustomTokenObtainPairSerializer
    
    @extend_schema(
        description="Login with email and password to get JWT tokens with tenant information",
        summary="User login",
        responses={200: CustomTokenObtainPairSerializer}
    )
    def post(self, request, *args, **kwargs):
        """
        Login user and return JWT tokens with tenant claims.
        """
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Update user's last login info
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.user
            
            # Get IP address for logging
            ip_address = self.get_client_ip(request)
            user.update_login_info(ip_address=ip_address)
        
        return response
    
    def get_client_ip(self, request):
        """
        Get client IP address from request.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@extend_schema_view(
    post=extend_schema(
        description="Register a new user account",
        summary="User registration",
        responses={201: UserSerializer}
    )
)
class UserRegistrationView(generics.CreateAPIView):
    """
    User registration endpoint.
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        """
        Create new user account.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        # Generate tokens for immediate login (optional)
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': 'User registered successfully. Please verify your email.'
        }, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        description="Get current user profile",
        summary="Get user profile"
    ),
    patch=extend_schema(
        description="Update current user profile",
        summary="Update user profile"
    )
)
class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    User profile management.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """
        Return the current user.
        """
        return self.request.user
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on request method.
        """
        if self.request.method == 'GET':
            return UserSerializer
        return UserProfileSerializer


@extend_schema(
    description="Change user password",
    summary="Change password",
    request=PasswordChangeSerializer,
    responses={200: {"message": "Password changed successfully"}}
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    """
    Change user password.
    """
    serializer = PasswordChangeSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Password changed successfully.'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    description="Verify user email address",
    summary="Verify email",
    request=EmailVerificationSerializer,
    responses={200: {"message": "Email verified successfully"}}
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_email(request):
    """
    Verify user email address.
    """
    serializer = EmailVerificationSerializer(data=request.data)
    
    if serializer.is_valid():
        # TODO: Implement actual email verification logic
        # This would involve validating the token and updating user
        
        return Response({
            'message': 'Email verified successfully.'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    description="Request password reset email",
    summary="Request password reset",
    request=PasswordResetRequestSerializer,
    responses={200: {"message": "Password reset email sent"}}
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def request_password_reset(request):
    """
    Request password reset email.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if serializer.is_valid():
        # TODO: Implement password reset email sending
        # This would involve generating a secure token and sending email
        
        return Response({
            'message': 'If an account with that email exists, a password reset email has been sent.'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    description="Confirm password reset with token",
    summary="Confirm password reset",
    request=PasswordResetConfirmSerializer,
    responses={200: {"message": "Password reset successfully"}}
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def confirm_password_reset(request):
    """
    Confirm password reset with token.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if serializer.is_valid():
        # TODO: Implement password reset confirmation logic
        # This would involve validating token and updating password
        
        return Response({
            'message': 'Password reset successfully.'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    description="Logout user and blacklist refresh token",
    summary="User logout",
    responses={200: {"message": "Logged out successfully"}}
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    """
    Logout user by blacklisting the refresh token.
    """
    try:
        refresh_token = request.data.get("refresh_token")
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        
        return Response({
            'message': 'Logged out successfully.'
        })
    except Exception as e:
        return Response({
            'error': 'Invalid token.'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    description="Get current user info from JWT token",
    summary="Get current user",
    responses={200: UserSerializer}
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    """
    Get current authenticated user information.
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)