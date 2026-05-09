"""
API serializers for Organizations app.
"""

from rest_framework import serializers
from ..models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    """
    Standard serializer for Organization model.
    """
    
    user_count = serializers.SerializerMethodField()
    can_add_user = serializers.SerializerMethodField()
    features_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'slug',
            'display_name',
            'description',
            'admin_email',
            'website',
            'phone',
            'status',
            'is_active',
            'subscription_tier',
            'trial_ends_at',
            'user_count',
            'can_add_user',
            'features',
            'features_summary',
            'limits',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'slug',
            'user_count',
            'can_add_user',
            'features_summary',
            'created_at',
            'updated_at',
        ]
    
    def get_user_count(self, obj):
        """Get current user count for the organization."""
        return obj.get_user_count()
    
    def get_can_add_user(self, obj):
        """Check if organization can add more users."""
        return obj.can_add_user()
    
    def get_features_summary(self, obj):
        """Get a summary of enabled features."""
        enabled_features = [
            feature for feature, enabled in obj.features.items() 
            if enabled
        ]
        return enabled_features


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new organizations.
    """
    
    class Meta:
        model = Organization
        fields = [
            'name',
            'display_name',
            'description',
            'admin_email',
            'website',
            'phone',
            'address_line_1',
            'address_line_2',
            'city',
            'state_province',
            'postal_code',
            'country',
            'email_domains',
        ]
    
    def create(self, validated_data):
        """
        Create organization using the manager method.
        """
        admin_email = validated_data.pop('admin_email')
        name = validated_data.pop('name')
        
        return Organization.objects.create_organization(
            name=name,
            admin_email=admin_email,
            **validated_data
        )


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating organizations.
    Limited fields that can be updated by organization admins.
    """
    
    class Meta:
        model = Organization
        fields = [
            'display_name',
            'description',
            'website',
            'phone',
            'address_line_1',
            'address_line_2',
            'city',
            'state_province',
            'postal_code',
            'country',
        ]


class OrganizationDetailSerializer(OrganizationSerializer):
    """
    Detailed serializer with additional information.
    """
    
    address = serializers.SerializerMethodField()
    usage_stats = serializers.SerializerMethodField()
    
    class Meta(OrganizationSerializer.Meta):
        fields = OrganizationSerializer.Meta.fields + [
            'address_line_1',
            'address_line_2',
            'city',
            'state_province',
            'postal_code',
            'country',
            'address',
            'email_domains',
            'usage_stats',
            'metadata',
        ]
    
    def get_address(self, obj):
        """Format full address."""
        address_parts = [
            obj.address_line_1,
            obj.address_line_2,
            obj.city,
            obj.state_province,
            obj.postal_code,
            obj.country,
        ]
        return ', '.join(filter(None, address_parts))
    
    def get_usage_stats(self, obj):
        """Get usage statistics for the organization."""
        return {
            'users': {
                'current': obj.get_user_count(),
                'limit': obj.get_limit('max_users'),
            },
            'storage': {
                'current_mb': 0,  # TODO: Implement actual storage calculation
                'limit_mb': obj.get_limit('max_storage_mb'),
            },
            'api_calls': {
                'current_month': 0,  # TODO: Implement actual API call tracking
                'limit_per_month': obj.get_limit('max_api_calls_per_month'),
            },
        }