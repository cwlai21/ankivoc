from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from django.utils import timezone
from django.contrib.auth import get_user_model

from languages.models import Language

User = get_user_model()

ANKI_READY = {
    'anki_running': True,
    'ankiconnect_installed': True,
    'version': 6,
    'message': 'Anki and AnkiConnect are ready.',
}

ANKI_NOT_READY = {
    'anki_running': False,
    'ankiconnect_installed': False,
    'version': None,
    'message': 'Anki is not running.',
}


def _make_user(username='testuser', email='test@example.com', password='TestPass123!',
               verified=False, language=None):
    user = User.objects.create_user(username=username, email=email, password=password)
    user.email_verified = verified
    if language:
        user.default_target_language = language
    user.save()
    return user


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class RegisterViewTests(TestCase):
    """Tests for RegisterView (web HTML form at /accounts/register/)."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts-web:register')
        self.lang = Language.objects.create(code='en', name='English', native_name='English')

    def test_get_renders_form(self):
        resp = self.client.get(self.url, HTTP_ACCEPT='text/html')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Register')

    @patch('accounts.views.AnkiConnectClient')
    def test_register_success_sends_email_and_shows_verify_form(self, mock_cls):
        mock_cls.return_value.check_anki_status.return_value = ANKI_READY

        resp = self.client.post(self.url, {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongPass1!',
            'password_confirm': 'StrongPass1!',
            'language_preference': self.lang.id,
        }, HTTP_ACCEPT='text/html')

        # Should stay on register page with verification card shown
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Verify Your Email')
        # Email should have been sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('newuser@example.com', mail.outbox[0].to)
        # User should exist in DB but not yet verified
        user = User.objects.get(username='newuser')
        self.assertFalse(user.email_verified)
        self.assertIsNotNone(user.verification_code)

    @patch('accounts.views.AnkiConnectClient')
    def test_register_anki_not_ready_blocks_creation(self, mock_cls):
        mock_cls.return_value.check_anki_status.return_value = ANKI_NOT_READY

        resp = self.client.post(self.url, {
            'username': 'blocked',
            'email': 'blocked@example.com',
            'password': 'StrongPass1!',
            'password_confirm': 'StrongPass1!',
            'language_preference': self.lang.id,
        }, HTTP_ACCEPT='text/html')

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='blocked').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_register_password_mismatch_shows_error(self):
        resp = self.client.post(self.url, {
            'username': 'mismatch',
            'email': 'mismatch@example.com',
            'password': 'StrongPass1!',
            'password_confirm': 'WrongPass1!',
            'language_preference': self.lang.id,
        }, HTTP_ACCEPT='text/html')

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='mismatch').exists())

    @patch('accounts.views.AnkiConnectClient')
    def test_register_duplicate_username_shows_error(self, mock_cls):
        mock_cls.return_value.check_anki_status.return_value = ANKI_READY
        _make_user(username='dupuser', email='dup@example.com')

        resp = self.client.post(self.url, {
            'username': 'dupuser',
            'email': 'other@example.com',
            'password': 'StrongPass1!',
            'password_confirm': 'StrongPass1!',
            'language_preference': self.lang.id,
        }, HTTP_ACCEPT='text/html')

        self.assertEqual(resp.status_code, 200)
        # Only the original user should exist
        self.assertEqual(User.objects.filter(username='dupuser').count(), 1)


# ---------------------------------------------------------------------------
# Email verification tests
# ---------------------------------------------------------------------------

class VerifyCodeViewTests(TestCase):
    """Tests for VerifyCodeView at /accounts/verify-code/."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts-web:verify-code')
        self.lang = Language.objects.create(code='en', name='English', native_name='English')
        self.user = _make_user()
        # Generate a fresh code
        self.code = self.user.generate_verification_code()
        # Set session as if registration just happened
        session = self.client.session
        session['pending_verification_user_id'] = self.user.id
        session['pending_verification_email'] = self.user.email
        session.save()

    def test_correct_code_verifies_user_and_redirects_to_login(self):
        resp = self.client.post(self.url, {'verification_code': self.code})
        self.assertRedirects(resp, reverse('accounts-web:login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertIsNone(self.user.verification_code)

    def test_wrong_code_shows_error(self):
        resp = self.client.post(self.url, {'verification_code': '000000'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid or expired')
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_expired_code_shows_error(self):
        # Manually expire the code
        self.user.verification_code_expires = timezone.now() - timezone.timedelta(minutes=1)
        self.user.save(update_fields=['verification_code_expires'])

        resp = self.client.post(self.url, {'verification_code': self.code})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid or expired')
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_no_session_redirects_to_register(self):
        # Clear the session
        session = self.client.session
        session.pop('pending_verification_user_id', None)
        session.save()

        resp = self.client.post(self.url, {'verification_code': self.code})
        self.assertRedirects(resp, reverse('accounts-web:register'))

    def test_short_code_shows_validation_error(self):
        resp = self.client.post(self.url, {'verification_code': '123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'valid 6-digit')

    def test_already_verified_redirects_to_login(self):
        self.user.email_verified = True
        self.user.save(update_fields=['email_verified'])

        resp = self.client.post(self.url, {'verification_code': self.code})
        self.assertRedirects(resp, reverse('accounts-web:login'))


# ---------------------------------------------------------------------------
# Resend code tests
# ---------------------------------------------------------------------------

class ResendCodeViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts-web:resend-code')
        self.user = _make_user()
        session = self.client.session
        session['pending_verification_user_id'] = self.user.id
        session['pending_verification_email'] = self.user.email
        session.save()

    def test_resend_sends_new_email(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.verification_code)

    def test_resend_no_session_redirects_to_register(self):
        session = self.client.session
        session.pop('pending_verification_user_id', None)
        session.save()

        resp = self.client.post(self.url)
        self.assertRedirects(resp, reverse('accounts-web:register'))


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------

class WebLoginViewTests(TestCase):
    """Tests for WebLoginView at /accounts/login/."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts-web:login')
        self.user = _make_user(verified=True)

    def test_get_renders_login_form(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Login')

    @patch('accounts.views.check_anki_setup')
    def test_login_success_redirects(self, mock_anki):
        mock_anki.return_value = {
            'anki_ready': True, 'anki_running': True,
            'ankiconnect_installed': True, 'version': 6,
            'message': 'Ready',
        }
        resp = self.client.post(self.url, {
            'username': 'testuser',
            'password': 'TestPass123!',
        })
        self.assertRedirects(resp, '/cards/batches/create/', fetch_redirect_response=False)

    def test_login_wrong_password_shows_error(self):
        resp = self.client.post(self.url, {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid username or password')

    def test_login_unverified_email_blocked(self):
        unverified = _make_user(username='unverified', email='unv@example.com', verified=False)
        resp = self.client.post(self.url, {
            'username': 'unverified',
            'password': 'TestPass123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'verify your email')

    @patch('accounts.views.check_anki_setup')
    def test_login_anki_not_ready_blocked(self, mock_anki):
        mock_anki.return_value = {
            'anki_ready': False, 'anki_running': False,
            'ankiconnect_installed': False, 'version': None,
            'message': 'Anki is not running.',
        }
        resp = self.client.post(self.url, {
            'username': 'testuser',
            'password': 'TestPass123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Anki is not running')
        # Should not be logged in
        self.assertFalse(resp.wsgi_request.user.is_authenticated)


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------

class WebLogoutViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = _make_user(verified=True)
        self.client.force_login(self.user)
        self.url = reverse('accounts-web:logout')

    def test_get_logout_redirects_to_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, reverse('accounts-web:login'))

    def test_post_logout_redirects_to_login(self):
        resp = self.client.post(self.url)
        self.assertRedirects(resp, reverse('accounts-web:login'))
