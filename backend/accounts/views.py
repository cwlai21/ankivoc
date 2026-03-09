from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.utils import timezone
from django.db import transaction
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as django_login
from django.views import View
from languages.models import Language
from cards.services.anki_connect import AnkiConnectClient
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
)
 
 
class RegisterView(APIView):
    """
    GET  /register/ or /api/v1/auth/register/    → Render registration form
    POST /api/v1/auth/register/                   → Create a new user account and return auth token
    Also checks Anki desktop and AnkiConnect status.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Render HTML registration form"""
        # If request is for HTML (from browser), render template
        if 'text/html' in request.headers.get('Accept', ''):
            languages = Language.objects.all().order_by('name')
            return render(request, 'accounts/register.html', {
                'languages': languages,
                'form': {},  # Empty form for initial render
            })
        
        # Otherwise return API message
        return Response({
            'message': 'POST to this endpoint with username, email, password, and password_confirm to register.'
        })
 
    def post(self, request):
        # Check if this is an HTML form submission
        is_html_form = 'text/html' in request.headers.get('Accept', '')
        
        serializer = RegisterSerializer(data=request.data)
        
        # Validate form
        if not serializer.is_valid():
            if is_html_form:
                languages = Language.objects.all().order_by('name')
                for field, errors in serializer.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                return render(request, 'accounts/register.html', {
                    'languages': languages,
                    'form': request.data,
                })
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Create temporary client with default settings to check Anki first
        temp_client = AnkiConnectClient()
        anki_status_dict = temp_client.check_anki_status()
        
        # Build full response with download info if needed
        anki_status = {
            'anki_ready': anki_status_dict['anki_running'] and anki_status_dict['ankiconnect_installed'],
            'anki_running': anki_status_dict['anki_running'],
            'ankiconnect_installed': anki_status_dict['ankiconnect_installed'],
            'version': anki_status_dict['version'],
            'message': anki_status_dict['message']
        }
        
        # Add download URL if AnkiConnect needs to be installed
        if not anki_status_dict['ankiconnect_installed'] and anki_status_dict['ankiconnect_installed'] is not None:
            anki_status['download_url'] = '/api/v1/auth/download-ankiconnect/'
            anki_status['ankiweb_url'] = 'https://ankiweb.net/shared/info/2055492159'
        
        # If Anki is not ready, return error WITHOUT creating user
        if not anki_status['anki_ready']:
            if is_html_form:
                messages.error(request, anki_status['message'])
                languages = Language.objects.all().order_by('name')
                return render(request, 'accounts/register.html', {
                    'languages': languages,
                    'form': request.data,
                })
            else:
                return Response({
                    'error': 'Anki setup required',
                    'message': anki_status['message'],
                    'anki_status': anki_status,
                }, status=status.HTTP_424_FAILED_DEPENDENCY)
        
        # Anki is ready - proceed with user creation
        user = serializer.save()
        
        # Update user Anki status
        user.anki_last_checked = timezone.now()
        user.anki_setup_completed = True
        user.ankiconnect_version = anki_status['version']
        user.save(update_fields=['anki_last_checked', 'anki_setup_completed', 'ankiconnect_version'])
        
        # Create auth token
        token, _ = Token.objects.get_or_create(user=user)

        # Handle HTML form submission
        if is_html_form:
            messages.success(request, 'Registration successful! You can now log in.')
            return redirect('accounts-web:login')
        
        # Handle API request
        return Response({
            'message': 'Registration successful.',
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'anki_status': anki_status,
        }, status=status.HTTP_201_CREATED)
 
 
class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticate user and return auth token.
    Also checks Anki desktop and AnkiConnect status.
    """
    permission_classes = [permissions.AllowAny]
 
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
 
        # Check Anki setup status
        anki_status = check_anki_setup(user)
        
        # If Anki is not ready, return error and prevent login
        if not anki_status['anki_ready']:
            return Response({
                'error': 'Anki setup required',
                'message': anki_status['message'],
                'anki_status': anki_status,
            }, status=status.HTTP_424_FAILED_DEPENDENCY)
        
        # Get or create auth token
        token, _ = Token.objects.get_or_create(user=user)
 
        return Response({
            'message': 'Login successful.',
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'anki_status': anki_status,
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


class WebLoginView(View):
    """
    Web login view that checks Anki status before allowing login.
    GET  /accounts/login/  → Render login form
    POST /accounts/login/  → Process login with Anki check
    """
    
    def get(self, request):
        """Render login form"""
        # If already authenticated, redirect to home
        if request.user.is_authenticated:
            return redirect('/')
        return render(request, 'accounts/login.html')
    
    def post(self, request):
        """Process login with Anki check"""
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'accounts/login.html')
        
        # Check Anki setup status
        anki_status = check_anki_setup(user, save_status=True)
        
        # If Anki is not ready, block login and show error
        if not anki_status['anki_ready']:
            messages.error(request, anki_status['message'])
            if 'download_url' in anki_status:
                messages.info(request, f'Need to install AnkiConnect? Use add-on code: 2055492159')
            return render(request, 'accounts/login.html')
        
        # Anki is ready - proceed with login
        django_login(request, user)
        messages.success(request, f'Welcome back, {user.username}!')
        
        # Redirect to next page or home
        next_url = request.GET.get('next', '/')
        return redirect(next_url)
 
 
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


def check_anki_setup(user, save_status=True):
    """
    Helper function to check if user's Anki desktop and AnkiConnect are ready.
    
    Args:
        user: User instance
        save_status: If True, save the check results to user record
        
    Returns:
        dict: {
            'anki_ready': bool,
            'anki_running': bool,
            'ankiconnect_installed': bool,
            'version': int or None,
            'message': str,
            'download_url': str (if AnkiConnect not installed)
        }
    """
    client = AnkiConnectClient(
        url=user.anki_connect_url,
        api_key=user.anki_connect_api_key
    )
    
    status = client.check_anki_status()
    
    # Update user's last checked time and version (only if save_status=True)
    if save_status:
        user.anki_last_checked = timezone.now()
        
        if status['ankiconnect_installed']:
            user.anki_setup_completed = True
            user.ankiconnect_version = status['version']
        
        user.save(update_fields=['anki_last_checked', 'anki_setup_completed', 'ankiconnect_version'])
    
    # Build response
    result = {
        'anki_ready': status['anki_running'] and status['ankiconnect_installed'],
        'anki_running': status['anki_running'],
        'ankiconnect_installed': status['ankiconnect_installed'],
        'version': status['version'],
        'message': status['message']
    }
    
    # Add download URL if AnkiConnect needs to be installed
    if not status['ankiconnect_installed'] and status['ankiconnect_installed'] is not None:
        result['download_url'] = '/api/v1/auth/download-ankiconnect/'
        result['ankiweb_url'] = 'https://ankiweb.net/shared/info/2055492159'
    
    return result


class CheckAnkiStatusView(APIView):
    """
    GET /api/v1/auth/check-anki/
    Check if Anki desktop is running and AnkiConnect is installed.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        result = check_anki_setup(request.user)
        return Response(result)


class DownloadAnkiConnectView(APIView):
    """
    GET /api/v1/auth/download-ankiconnect/
    Provide download information and installation guide for AnkiConnect.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response({
            'add_on_code': '2055492159',
            'ankiweb_url': 'https://ankiweb.net/shared/info/2055492159',
            'github_url': 'https://github.com/FooSoft/anki-connect',
            'installation_steps': [
                'Open Anki desktop application',
                'Go to Tools → Add-ons → Get Add-ons...',
                'Enter code: 2055492159',
                'Click OK and restart Anki',
                'After restart, return here and try logging in again'
            ],
            'manual_install': {
                'description': 'If the code installation fails, download manually:',
                'steps': [
                    'Download AnkiConnect from: https://github.com/FooSoft/anki-connect/releases/latest',
                    'Open Anki → Tools → Add-ons → Install from file...',
                    'Select the downloaded .ankiaddon file',
                    'Restart Anki'
                ]
            },
            'verification': {
                'description': 'After installing AnkiConnect, verify it works:',
                'test_url': 'http://localhost:8765',
                'next_step': 'Return to this app and try logging in again'
            }
        })


# Views for `accounts` app (placeholder).

# Implement view functions or class-based views when needed.
