from django.db import models


class Language(models.Model):
	"""A supported language for learning or explanation."""

	name = models.CharField(
		max_length=100,
		help_text='Display name, e.g. French'
	)
	code = models.CharField(
		max_length=10,
		unique=True,
		help_text='ISO 639-1 code, e.g. fr'
	)
	native_name = models.CharField(
		max_length=100,
		blank=True,
		default='',
		help_text='Name in native script, e.g. Français'
	)
	azure_tts_voice = models.CharField(
		max_length=255,
		blank=True,
		default='',
		help_text='Azure TTS voice, e.g. fr-FR-DeniseNeural'
	)
	azure_tts_locale = models.CharField(
		max_length=20,
		blank=True,
		default='',
		help_text='Azure TTS locale, e.g. fr-FR'
	)

	vocab_label = models.CharField(
		max_length=100,
		blank=True,
		default='Vocabulary',
		help_text='Label to use for vocabulary decks (e.g. "Vocabulary" or localized word)'
	)
	is_active = models.BooleanField(
		default=True,
		help_text='Whether this language is available for selection'
	)

	class Meta:
		db_table = 'languages'
		ordering = ['name']

	def __str__(self):
		return f'{self.name} ({self.code})'


class CardTemplate(models.Model):
	"""
	Anki card template definition for a target language.
	Each language has one template that defines the Anki note structure.
	"""

	language = models.OneToOneField(
		Language,
		on_delete=models.CASCADE,
		related_name='card_template'
	)
	anki_model_name = models.CharField(
		max_length=255,
		help_text='Anki note type name, e.g. French Vocabulary'
	)
	default_deck_name = models.CharField(
		max_length=255,
		help_text='Default Anki deck name, e.g. French::Vocabulary'
	)
	fields_definition = models.JSONField(
		default=list,
		help_text='Ordered list of Anki note field names as JSON array'
	)
	llm_prompt_template = models.TextField(
		blank=True,
		default='',
		help_text='Prompt template for LLM. Use {input_text}, {target_lang}, {explanation_lang}'
	)

	class Meta:
		db_table = 'card_templates'

	def __str__(self):
		return f'Template: {self.language.name}'
