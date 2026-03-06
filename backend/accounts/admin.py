from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
	"""Admin configuration for custom User model."""

	# Fields shown on the user detail/edit page
	fieldsets = BaseUserAdmin.fieldsets + (
		('AnkiConnect Settings', {
			'fields': (
				'anki_connect_url',
				'anki_connect_api_key',
			),
		}),
		('Language Preferences', {
			'fields': (
				'default_target_language',
				'default_explanation_language',
				'default_deck_name',
			),
		}),
	)

	# Fields shown on the user creation page
	add_fieldsets = BaseUserAdmin.add_fieldsets + (
		('AnkiConnect Settings', {
			'fields': (
				'anki_connect_url',
			),
		}),
	)

	list_display = [
		'username',
		'email',
		'default_target_language',
		'default_explanation_language',
		'anki_connect_url',
		'is_active',
	]

	list_filter = BaseUserAdmin.list_filter + (
		'default_target_language',
	)
