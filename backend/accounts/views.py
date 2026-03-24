import os
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.utils import timezone
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.views import View
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from languages.models import Language
from cards.services.anki_connect import AnkiConnectClient
from .models import User
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
            print(f"✗ Anki not ready: {anki_status['message']}")
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
        
        # Generate verification code
        verification_code = user.generate_verification_code()

        # Send verification email with retry logic
        email_sent = False
        max_email_retries = 3

        try:
            email_html = render_to_string('accounts/verification_email.html', {
                'user': user,
                'verification_code': verification_code,
            })
            email_text = render_to_string('accounts/verification_email.txt', {
                'user': user,
                'verification_code': verification_code,
            })

            print(f"Attempting to send email to {user.email}...")
            print(f"Email backend: {settings.EMAIL_BACKEND}")
            print(f"Email host: {settings.EMAIL_HOST}")
            print(f"From email: {settings.DEFAULT_FROM_EMAIL}")

            for attempt in range(1, max_email_retries + 1):
                try:
                    msg = EmailMultiAlternatives(
                        subject='Anki Vocabulary Builder Email Verification Code',
                        body=email_text,
                        from_email=f'Anki Vocabulary Builder <{settings.DEFAULT_FROM_EMAIL}>',
                        to=[user.email],
                        reply_to=[settings.DEFAULT_REPLY_TO],
                    )
                    msg.attach_alternative(email_html, "text/html")
                    result = msg.send(fail_silently=False)
                    print(f"✓ Verification email sent to {user.email} with code: {verification_code}")
                    print(f"  send_mail returned: {result} (1 = success) on attempt {attempt}")
                    email_sent = True
                    break
                except Exception as e:
                    print(f"✗ Email send attempt {attempt}/{max_email_retries} failed: {type(e).__name__}: {e}")
                    if attempt < max_email_retries:
                        import time
                        time.sleep(2)  # Wait 2 seconds before retry
                    else:
                        import traceback
                        traceback.print_exc()
        except Exception as e:
            print(f"✗ Failed to prepare verification email: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

        if not email_sent:
            print(f"⚠️  Warning: Could not send verification email to {user.email}")
            print(f"   Verification code (for console): {verification_code}")
            # Continue anyway - user can resend code later via the resend button
        
        # Create auth token
        token, _ = Token.objects.get_or_create(user=user)

        # Handle HTML form submission
        if is_html_form:
            # Store user_id in session for verification
            request.session['pending_verification_user_id'] = user.id
            request.session['pending_verification_email'] = user.email
            messages.success(request, 'Registration successful! Please check your email for the verification code.')
            print(f"✓ Registration successful for {user.username}. Showing verification form.")
            # Don't redirect - stay on the page to show verification code form
            languages = Language.objects.all().order_by('name')
            return render(request, 'accounts/register.html', {
                'languages': languages,
                'show_verification': True,
                'user_email': user.email,
            })
        
        # Handle API request
        return Response({
            'message': 'Registration successful. Please check your email to verify your account.',
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'email_verified': user.email_verified,
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
        
        # Check if email is verified
        if not user.email_verified:
            return Response({
                'error': 'Email not verified',
                'message': 'Please verify your email address before logging in. Check your inbox for the verification code.',
            }, status=status.HTTP_403_FORBIDDEN)
 
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


class VerifyCodeView(View):
    """
    POST /web/accounts/verify-code/
    Verify user's email address using the 6-digit code.
    """
    
    def post(self, request):
        verification_code = request.POST.get('verification_code', '').strip()
        user_id = request.session.get('pending_verification_user_id')
        
        if not user_id:
            messages.error(request, 'No pending verification found. Please register again.')
            return redirect('accounts-web:register')
        
        if not verification_code or len(verification_code) != 6:
            messages.error(request, 'Please enter a valid 6-digit verification code.')
            languages = Language.objects.all().order_by('name')
            return render(request, 'accounts/register.html', {
                'languages': languages,
                'show_verification': True,
                'user_email': request.session.get('pending_verification_email'),
            })
        
        try:
            user = User.objects.get(id=user_id)
            
            # Check if already verified
            if user.email_verified:
                messages.info(request, 'Your email is already verified. You can log in now.')
                # Clear session
                request.session.pop('pending_verification_user_id', None)
                request.session.pop('pending_verification_email', None)
                return redirect('accounts-web:login')
            
            # Verify code
            print(f"Verifying code for {user.username}: received='{verification_code}', stored='{user.verification_code}', expires={user.verification_code_expires}")
            if user.is_verification_code_valid(verification_code):
                user.email_verified = True
                user.verification_code = None  # Clear the code after successful verification
                user.save(update_fields=['email_verified', 'verification_code'])

                # Clear session
                request.session.pop('pending_verification_user_id', None)
                request.session.pop('pending_verification_email', None)

                print(f"✓ Email verified successfully for {user.username}")
                messages.success(request, 'Email verified successfully! You can now log in.')
                return redirect('accounts-web:login')
            else:
                print(f"✗ Verification failed for {user.username}")
                messages.error(request, 'Invalid or expired verification code. Please try again or request a new code.')
                languages = Language.objects.all().order_by('name')
                return render(request, 'accounts/register.html', {
                    'languages': languages,
                    'show_verification': True,
                    'user_email': user.email,
                })
            
        except User.DoesNotExist:
            messages.error(request, 'User not found. Please register again.')
            request.session.pop('pending_verification_user_id', None)
            request.session.pop('pending_verification_email', None)
            return redirect('accounts-web:register')


class ResendCodeView(View):
    """
    POST /web/accounts/resend-code/
    Resend verification code to user.
    """
    
    def post(self, request):
        user_id = request.session.get('pending_verification_user_id')
        
        if not user_id:
            messages.error(request, 'No pending verification found. Please register again.')
            return redirect('accounts-web:register')
        
        try:
            user = User.objects.get(id=user_id)
            
            # Check if already verified
            if user.email_verified:
                messages.info(request, 'Your email is already verified. You can log in now.')
                request.session.pop('pending_verification_user_id', None)
                request.session.pop('pending_verification_email', None)
                return redirect('accounts-web:login')
            
            # Generate new verification code
            verification_code = user.generate_verification_code()

            # Send verification email with retry logic
            email_sent = False
            max_email_retries = 3

            try:
                email_html = render_to_string('accounts/verification_email.html', {
                    'user': user,
                    'verification_code': verification_code,
                })
                email_text = render_to_string('accounts/verification_email.txt', {
                    'user': user,
                    'verification_code': verification_code,
                })

                for attempt in range(1, max_email_retries + 1):
                    try:
                        msg = EmailMultiAlternatives(
                            subject='Anki Vocabulary Builder Email Verification Code',
                            body=email_text,
                            from_email=f'Anki Vocabulary Builder <{settings.DEFAULT_FROM_EMAIL}>',
                            to=[user.email],
                            reply_to=[settings.DEFAULT_REPLY_TO],
                        )
                        msg.attach_alternative(email_html, "text/html")
                        msg.send(fail_silently=False)
                        print(f"✓ Resend verification email sent to {user.email} (attempt {attempt})")
                        email_sent = True
                        break
                    except Exception as e:
                        print(f"✗ Resend email attempt {attempt}/{max_email_retries} failed: {e}")
                        if attempt < max_email_retries:
                            import time
                            time.sleep(2)
            except Exception as e:
                print(f"✗ Failed to prepare resend email: {e}")

            if email_sent:
                messages.success(request, 'A new verification code has been sent to your email. Please check your inbox.')
            else:
                messages.warning(request, 'Could not send email. Please try again in a moment, or contact support.')
                print(f"⚠️  Resend failed. Verification code (for console): {verification_code}")

            languages = Language.objects.all().order_by('name')
            return render(request, 'accounts/register.html', {
                'languages': languages,
                'show_verification': True,
                'user_email': user.email,
            })
            
        except User.DoesNotExist:
            messages.error(request, 'User not found. Please register again.')
            request.session.pop('pending_verification_user_id', None)
            request.session.pop('pending_verification_email', None)
            return redirect('accounts-web:register')
        except Exception as e:
            messages.error(request, 'Failed to send verification code. Please try again later.')
            languages = Language.objects.all().order_by('name')
            return render(request, 'accounts/register.html', {
                'languages': languages,
                'show_verification': True,
                'user_email': request.session.get('pending_verification_email'),
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
        
        # Check if email is verified
        if not user.email_verified:
            messages.error(request, 'Please verify your email address before logging in. Check your inbox for the verification code.')
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
        next_url = request.GET.get('next', '/cards/batches/create/')
        return redirect(next_url)


class WebLogoutView(View):
    """
    GET/POST /accounts/logout/
    Logs the user out.
    """
    def get(self, request):
        django_logout(request)
        messages.success(request, "You have been successfully logged out.")
        return redirect('accounts-web:login')

    def post(self, request):
        django_logout(request)
        messages.success(request, "You have been successfully logged out.")
        return redirect('accounts-web:login')


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
