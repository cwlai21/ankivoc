from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models


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

	class Meta:
		db_table = 'users'
		verbose_name = 'User'
		verbose_name_plural = 'Users'

	def __str__(self):
		return self.username
