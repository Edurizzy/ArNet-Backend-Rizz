"""
Authentication and user serializers for ArNet platform.

These serializers handle JWT token generation with tenant claims,
user registration, profile management, and authentication flows.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _

from ..models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token serializer that includes tenant information.
    
    This is like creating a "smart ID badge" that not only identifies
    who you are, but also which company you work for and what your
    role is within that company.
    """
    
    def validate(self, attrs):
        """
        Validate credentials and generate token with custom claims.
        """
        # Perform standard authentication
        data = super().validate(attrs)
        
        # Add custom claims to the token
        refresh = self.get_token(self.user)
        
        # Add user and organization information
        data.update({
            'user': UserSerializer(self.user).data,
            'organization': self.user.organization.slug if self.user.organization else None,
        })
        
        return data
    
    @classmethod
    def get_token(cls, user):
        """
        Generate token with custom claims.
        
        These claims will be available in every request, allowing us
        to automatically scope data to the correct tenant.
        """
        token = super().get_token(user)
        
        # Add custom claims
        token['user_id'] = str(user.id)
        token['email'] = user.email
        token['display_name'] = user.get_display_name()
        
        # Organization (tenant) claims - CRITICAL for multi-tenancy
        if user.organization:
            token['org_id'] = str(user.organization.id)
            token['org_slug'] = user.organization.slug
            token['org_name'] = user.organization.name
            token['subscription_tier'] = user.organization.subscription_tier
        else:
            token['org_id'] = None
            token['org_slug'] = None
            token['org_name'] = None
            token['subscription_tier'] = None
        
        # Role and permission claims (for future RBAC)
        token['role'] = user.get_organization_role()
        token['is_admin'] = user.is_organization_admin()
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        
        # Feature access claims (based on subscription)
        if user.organization:
            token['features'] = list(user.organization.features.keys()) if user.organization.features else []
        
        return token


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """
    
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
            'password',
            'password_confirm',
            'phone',
            'timezone',
            'language'
        ]
    
    def validate(self, attrs):
        """
        Validate password confirmation and other registration data.
        """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': _('Passwords do not match.')
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Create new user with proper setup.
        """
        # Remove password_confirm from validated data
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')
        
        # Create user
        user = User.objects.create_user(password=password, **validated_data)
        
        return user


class UserSerializer(serializers.ModelSerializer):
    """
    Standard user serializer for API responses.
    """
    
    full_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    organization_id = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    can_login = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'display_name',
            'name',
            'full_name',
            'phone',
            'avatar',
            'timezone',
            'language',
            'status',
            'is_active',
            'email_verified',
            'two_factor_enabled',
            'organization_name',
            'organization_id',
            'role',
            'can_login',
            'last_login',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'email_verified',
            'last_login',
            'created_at',
            'updated_at'
        ]
    
    def get_full_name(self, obj):
        """Get user's full name."""
        return obj.get_full_name()

    def get_name(self, obj):
        """Get stable display name for frontend identity."""
        return obj.get_display_name()

    def get_organization_id(self, obj):
        """Expose tenant ID required by realtime and REST isolation."""
        return str(obj.organization_id) if obj.organization_id else None
    
    def get_organization_name(self, obj):
        """Get organization name."""
        return obj.organization.name if obj.organization else None
    
    def get_role(self, obj):
        """Get user's role."""
        return obj.get_organization_role()
    
    def get_can_login(self, obj):
        """Check if user can log in."""
        return obj.can_login


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile updates.
    """
    
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'display_name',
            'phone',
            'avatar',
            'timezone',
            'language',
            'preferences'
        ]
    
    def update(self, instance, validated_data):
        """
        Update user profile with validation.
        """
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change.
    """
    
    current_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate_current_password(self, value):
        """
        Validate current password.
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_('Current password is incorrect.'))
        return value
    
    def validate(self, attrs):
        """
        Validate password confirmation.
        """
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': _('Passwords do not match.')
            })
        return attrs
    
    def save(self):
        """
        Change user password.
        """
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for email verification.
    """
    
    token = serializers.CharField()
    
    def validate_token(self, value):
        """
        Validate email verification token.
        """
        # TODO: Implement token validation logic
        # This would typically involve checking a signed token or database record
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting password reset.
    """
    
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """
        Validate that user exists with this email.
        """
        try:
            User.objects.get(email=value, is_active=True)
        except User.DoesNotExist:
            # Don't reveal whether user exists for security
            pass
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming password reset.
    """
    
    token = serializers.CharField()
    new_password = serializers.CharField(
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """
        Validate password reset data.
        """
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': _('Passwords do not match.')
            })
        return attrs