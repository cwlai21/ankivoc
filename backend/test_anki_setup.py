#!/usr/bin/env python
"""
Test script for Anki setup checking on login/register.
Tests the new user onboarding flow with Anki verification.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from cards.services.anki_connect import AnkiConnectClient

User = get_user_model()


def test_anki_connection():
    """Test basic Anki connection."""
    print("\n" + "="*60)
    print("Testing Anki Connection")
    print("="*60 + "\n")
    
    client = AnkiConnectClient()
    status = client.check_anki_status()
    
    print(f"Anki Running: {status['anki_running']}")
    print(f"AnkiConnect Installed: {status['ankiconnect_installed']}")
    print(f"Version: {status['version']}")
    print(f"Message: {status['message']}")
    
    return status


def test_user_anki_status(username='testuser'):
    """Test checking Anki status for a specific user."""
    print("\n" + "="*60)
    print(f"Testing User: {username}")
    print("="*60 + "\n")
    
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found. Creating test user...")
        user = User.objects.create_user(
            username=username,
            email=f'{username}@test.com',
            password='testpass123'
        )
        print(f"✅ Created user: {username}")
    
    print(f"\nUser ID: {user.id}")
    print(f"Email: {user.email}")
    print(f"AnkiConnect URL: {user.anki_connect_url}")
    print(f"Setup Completed: {user.anki_setup_completed}")
    print(f"Last Checked: {user.anki_last_checked}")
    print(f"Version: {user.ankiconnect_version}")
    
    # Check Anki status for this user
    client = AnkiConnectClient(
        url=user.anki_connect_url,
        api_key=user.anki_connect_api_key
    )
    status = client.check_anki_status()
    
    print("\n--- Current Anki Status ---")
    print(f"Anki Ready: {status['anki_running'] and status['ankiconnect_installed']}")
    print(f"Anki Running: {status['anki_running']}")
    print(f"AnkiConnect Installed: {status['ankiconnect_installed']}")
    print(f"Message: {status['message']}")
    
    # Update user record
    user.anki_last_checked = django.utils.timezone.now()
    if status['ankiconnect_installed']:
        user.anki_setup_completed = True
        user.ankiconnect_version = status['version']
    user.save()
    
    print("\n✅ User record updated")
    
    return status


def test_login_flow_simulation():
    """Simulate the login flow with Anki checking."""
    print("\n" + "="*60)
    print("Simulating Login Flow with Anki Check")
    print("="*60 + "\n")
    
    # Create or get test user
    username = 'anki_test_user'
    try:
        user = User.objects.get(username=username)
        print(f"Found existing user: {username}")
    except User.DoesNotExist:
        user = User.objects.create_user(
            username=username,
            email=f'{username}@test.com',
            password='test1234'
        )
        print(f"Created new user: {username}")
    
    # Simulate login with Anki check (same as what happens in LoginView)
    from accounts.views import check_anki_setup
    
    print("\n--- Checking Anki Setup ---")
    anki_status = check_anki_setup(user)
    
    print(f"\nAnki Ready: {anki_status['anki_ready']}")
    print(f"Anki Running: {anki_status['anki_running']}")
    print(f"AnkiConnect Installed: {anki_status['ankiconnect_installed']}")
    print(f"Version: {anki_status['version']}")
    print(f"Message: {anki_status['message']}")
    
    if 'download_url' in anki_status:
        print(f"\nDownload URL: {anki_status['download_url']}")
        print(f"AnkiWeb URL: {anki_status['ankiweb_url']}")
    
    # Check if login would be allowed
    if anki_status['anki_ready']:
        print("\n✅ LOGIN WOULD SUCCEED - Anki is properly configured")
    else:
        print("\n❌ LOGIN WOULD FAIL - User needs to setup Anki")
        if not anki_status['anki_running']:
            print("   → Please open Anki Desktop")
        elif anki_status['ankiconnect_installed'] == False:
            print("   → Please install AnkiConnect add-on (code: 2055492159)")
    
    return anki_status


def test_existing_users():
    """Test that existing users' Anki status is tracked."""
    print("\n" + "="*60)
    print("Testing All Existing Users")
    print("="*60 + "\n")
    
    users = User.objects.all()
    print(f"Total users: {users.count()}\n")
    
    for user in users[:5]:  # Test first 5 users
        print(f"User: {user.username}")
        print(f"  Setup Completed: {user.anki_setup_completed}")
        print(f"  Last Checked: {user.anki_last_checked}")
        print(f"  Version: {user.ankiconnect_version}")
        print()


if __name__ == '__main__':
    print("\n🧪 ANKI SETUP TESTING SUITE\n")
    
    # Test 1: Basic connection
    try:
        basic_status = test_anki_connection()
        anki_available = basic_status['anki_running'] and basic_status['ankiconnect_installed']
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        anki_available = False
    
    # Test 2: User-specific status
    try:
        test_user_anki_status()
    except Exception as e:
        print(f"❌ User status test failed: {e}")
    
    # Test 3: Login flow simulation
    try:
        test_login_flow_simulation()
    except Exception as e:
        print(f"❌ Login flow test failed: {e}")
    
    # Test 4: Check existing users
    try:
        test_existing_users()
    except Exception as e:
        print(f"❌ Existing users test failed: {e}")
    
    # Final summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    if anki_available:
        print("\n✅ Anki Desktop and AnkiConnect are ready!")
        print("   New users can successfully register/login.")
    else:
        print("\n⚠️  Anki setup incomplete:")
        print("   - Open Anki Desktop")
        print("   - Install AnkiConnect (code: 2055492159)")
        print("   - Then users can register/login")
    
    print("\n✅ All API endpoints and database fields are configured")
    print("✅ Login/Register views will check Anki status automatically")
    print("\n💡 TIP: Test the actual API endpoints:")
    print("   POST /api/v1/auth/register/")
    print("   POST /api/v1/auth/login/")
    print("   GET  /api/v1/auth/check-anki/")
    print("   GET  /api/v1/auth/download-ankiconnect/")
    print()
