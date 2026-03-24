from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone
from datetime import timedelta
import random
import string


class User(AbstractUser):
	"""
	Custom user model.
	Each user has their own AnkiConnect configuration
	and language preferences.
	"""

	# ── AnkiConnect Settings ──
	# Override relation names to avoid reverse-accessor clashes when using a
	# custom user model alongside Django's auth app in some migration states.
	groups = models.ManyToManyField(
		Group,
		related_name='accounts_users',
		blank=True,
		help_text='The groups this user belongs to.',
		verbose_name='groups',
	)
	user_permissions = models.ManyToManyField(
		Permission,
		related_name='accounts_user_permissions',
		blank=True,
		help_text='Specific permissions for this user.',
		verbose_name='user permissions',
	)

	# (end override)

	anki_connect_url = models.URLField(
		default='http://localhost:8765',
		help_text='Your AnkiConnect endpoint URL. '
				  'Anki desktop must be running with AnkiConnect add-on.'
	)
	anki_connect_api_key = models.CharField(
		max_length=255,
		blank=True,
		default='',
		help_text='AnkiConnect API key (leave blank if not configured)'
	)

	# ── Language Preferences ──
	default_target_language = models.ForeignKey(
		'languages.Language',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='users_learning',
		help_text='The language you want to learn'
	)
	default_explanation_language = models.ForeignKey(
		'languages.Language',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='users_explaining',
		help_text='The language used for explanations'
	)
	default_deck_name = models.CharField(
		max_length=255,
		blank=True,
		default='',
		help_text='Default Anki deck name, e.g. French::Vocabulary'
	)

	# ── Anki Setup Status ──
	anki_setup_completed = models.BooleanField(
		default=False,
		help_text='Whether user has completed Anki desktop + AnkiConnect setup'
	)
	anki_last_checked = models.DateTimeField(
		null=True,
		blank=True,
		help_text='Last time Anki connection was verified'
	)
	ankiconnect_version = models.IntegerField(
		null=True,
		blank=True,
		help_text='Detected AnkiConnect version number'
	)

	# ── Email Verification ──
	email_verified = models.BooleanField(
		default=False,
		help_text='Whether user has verified their email address'
	)
	verification_code = models.CharField(
		max_length=6,
		blank=True,
		null=True,
		help_text='6-digit code for email verification'
	)
	verification_code_created = models.DateTimeField(
		null=True,
		blank=True,
		help_text='When the verification code was created'
	)
	verification_code_expires = models.DateTimeField(
		null=True,
		blank=True,
		help_text='When the verification code expires'
	)

	class Meta:
		db_table = 'users'
		verbose_name = 'User'
		verbose_name_plural = 'Users'

	def __str__(self):
		return self.username
	
	def generate_verification_code(self):
		"""Generate a 6-digit verification code and set expiration time"""
		self.verification_code = ''.join(random.choices(string.digits, k=6))
		self.verification_code_created = timezone.now()
		# Code expires in 15 minutes
		self.verification_code_expires = timezone.now() + timedelta(minutes=15)
		self.save(update_fields=['verification_code', 'verification_code_created', 'verification_code_expires'])
		return self.verification_code
	
	def is_verification_code_valid(self, code):
		"""Check if the provided code matches and hasn't expired"""
		if not self.verification_code or not self.verification_code_expires:
			return False
		if self.verification_code != code:
			return False
		if timezone.now() > self.verification_code_expires:
			return False
		return True
