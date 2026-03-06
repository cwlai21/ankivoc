from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
)
 
 
class RegisterView(APIView):
    """
    POST /api/v1/auth/register/
    Create a new user account and return auth token.
    """
    permission_classes = [permissions.AllowAny]
 
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
 
        # Create auth token
        token, _ = Token.objects.get_or_create(user=user)
 
        return Response({
            'message': 'Registration successful.',
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            }
        }, status=status.HTTP_201_CREATED)
 
 
class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticate user and return auth token.
    """
    permission_classes = [permissions.AllowAny]
 
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
 
        # Get or create auth token
        token, _ = Token.objects.get_or_create(user=user)
 
        return Response({
            'message': 'Login successful.',
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            }
        })
 
 
class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Delete the user's auth token.
    """
    permission_classes = [permissions.IsAuthenticated]
 
    def post(self, request):
        # Delete the token to force re-login
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
 
        return Response({
            'message': 'Logout successful.'
        })
 
 
class ProfileView(APIView):
    """
    GET  /api/v1/auth/profile/    → Get profile
    PATCH /api/v1/auth/profile/   → Update profile
    """
    permission_classes = [permissions.IsAuthenticated]
 
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
 
    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Profile updated successfully.',
            'user': serializer.data,
        })
 
 
class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/
    Change the user's password.
    """
    permission_classes = [permissions.IsAuthenticated]
 
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
 
        # Delete old token and create new one
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        token = Token.objects.create(user=request.user)
 
        return Response({
            'message': 'Password changed successfully.',
            'token': token.key,
        })
# Views for `accounts` app (placeholder).

# Implement view functions or class-based views when needed.
