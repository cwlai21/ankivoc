from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User
 
 
class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
 
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text='Minimum 8 characters'
    )
    password_confirm = serializers.CharField(
        write_only=True,
        help_text='Must match password'
    )
 
    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'password',
            'password_confirm',
        ]
 
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value
 
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match.'
            })
        return data
 
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        return user
 
 
class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
 
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
 
    def validate(self, data):
        user = authenticate(
            username=data['username'],
            password=data['password'],
        )
        if not user:
            raise serializers.ValidationError('Invalid username or password.')
        if not user.is_active:
            raise serializers.ValidationError('This account is disabled.')
        data['user'] = user
        return data
 
 
class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for viewing and updating user profile."""
 
    default_target_language_name = serializers.SerializerMethodField()
    default_explanation_language_name = serializers.SerializerMethodField()
 
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'anki_connect_url',
            'anki_connect_api_key',
            'default_target_language',
            'default_target_language_name',
            'default_explanation_language',
            'default_explanation_language_name',
            'default_deck_name',
            'date_joined',
            'anki_setup_completed',
            'anki_last_checked',
            'ankiconnect_version',
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'anki_setup_completed', 
                           'anki_last_checked', 'ankiconnect_version']
 
    def get_default_target_language_name(self, obj):
        if obj.default_target_language:
            return obj.default_target_language.name
        return None
 
    def get_default_explanation_language_name(self, obj):
        if obj.default_explanation_language:
            return obj.default_explanation_language.name
        return None
 
 
class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
 
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)
 
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value
 
    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'New passwords do not match.'
            })
        return data
 
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
