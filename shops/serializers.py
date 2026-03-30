from rest_framework import serializers
from django.contrib.auth.models import User
from accounts.models import Role, UserProfile
from .models import Shop, Employee
import secrets
import string
import re
import uuid

class EmployeeCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role_id = serializers.UUIDField()  # This expects UUID format
    shop_id = serializers.UUIDField()
    employment_type = serializers.CharField(max_length=20, default='full_time')
    salary = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    send_credentials = serializers.BooleanField(default=True)

    def validate_role_id(self, value):
        """Ensure role_id is a valid UUID and exists"""
        try:
            # Convert string to UUID object
            if isinstance(value, str):
                # Try to parse as UUID
                role_uuid = uuid.UUID(value)
                return role_uuid
            return value
        except (ValueError, AttributeError):
            raise serializers.ValidationError("Must be a valid UUID.")
    
    def validate_email(self, value):
        """Validate email format and uniqueness"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, value):
            raise serializers.ValidationError("Please enter a valid email address")
        
        return value.lower()

    def validate_phone_number(self, value):
        """Validate international phone number format"""
        if not value:
            return value
        
        # Remove any non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', value)
        
        # Check if it starts with +
        if not cleaned.startswith('+'):
            raise serializers.ValidationError("Phone number must include country code (e.g., +254)")
        
        # Check length (minimum 10 digits including country code)
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise serializers.ValidationError("Phone number must be between 10 and 15 digits (including country code)")
        
        return value

    def generate_temporary_password(self):
        """Generate a secure temporary password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(12))