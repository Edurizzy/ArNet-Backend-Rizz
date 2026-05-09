"""
API serializers for Audit app.
"""

from rest_framework import serializers
from ..models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for AuditLog model.
    """
    
    actor_display = serializers.SerializerMethodField()
    is_high_risk = serializers.SerializerMethodField()
    is_failure = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'created_at',
            'action',
            'action_category',
            'entity_type',
            'entity_id',
            'entity_name',
            'actor_display',
            'outcome',
            'risk_score',
            'is_high_risk',
            'is_failure',
            'is_sensitive',
            'correlation_id',
            'ip_address',
            'duration_ms',
            'duration_display',
            'details',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_actor_display(self, obj):
        """Get human-readable actor display."""
        return obj.get_actor_display()
    
    def get_is_high_risk(self, obj):
        """Check if this is a high-risk action."""
        return obj.is_high_risk
    
    def get_is_failure(self, obj):
        """Check if this action failed."""
        return obj.is_failure
    
    def get_duration_display(self, obj):
        """Format duration for display."""
        if obj.duration_ms is None:
            return None
        
        if obj.duration_ms < 1000:
            return f"{obj.duration_ms}ms"
        else:
            return f"{obj.duration_ms / 1000:.2f}s"


class AuditLogDetailSerializer(AuditLogSerializer):
    """
    Detailed serializer with additional fields.
    """
    
    class Meta(AuditLogSerializer.Meta):
        fields = AuditLogSerializer.Meta.fields + [
            'user_agent',
            'session_id',
            'status_code',
            'changes',
            'metadata',
            'updated_at',
        ]


class AuditLogFilterSerializer(serializers.Serializer):
    """
    Serializer for audit log filtering parameters.
    """
    
    action = serializers.CharField(required=False, help_text="Filter by action")
    action_category = serializers.CharField(required=False, help_text="Filter by action category")
    entity_type = serializers.CharField(required=False, help_text="Filter by entity type")
    outcome = serializers.ChoiceField(
        choices=['success', 'failure', 'error', 'denied'],
        required=False,
        help_text="Filter by outcome"
    )
    actor_user_id = serializers.UUIDField(required=False, help_text="Filter by actor user ID")
    correlation_id = serializers.CharField(required=False, help_text="Filter by correlation ID")
    is_sensitive = serializers.BooleanField(required=False, help_text="Filter by sensitive actions")
    min_risk_score = serializers.IntegerField(required=False, help_text="Minimum risk score")
    max_risk_score = serializers.IntegerField(required=False, help_text="Maximum risk score")
    start_date = serializers.DateTimeField(required=False, help_text="Start date for filtering")
    end_date = serializers.DateTimeField(required=False, help_text="End date for filtering")
    
    def validate(self, data):
        """Validate filter parameters."""
        if 'min_risk_score' in data and 'max_risk_score' in data:
            if data['min_risk_score'] > data['max_risk_score']:
                raise serializers.ValidationError(
                    "min_risk_score cannot be greater than max_risk_score"
                )
        
        if 'start_date' in data and 'end_date' in data:
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError(
                    "start_date cannot be after end_date"
                )
        
        return data