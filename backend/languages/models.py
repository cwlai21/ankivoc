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
	front_template = models.TextField(
		blank=True,
		default='{{Français}}',
		help_text='Anki card front template (qfmt)'
	)
	back_template = models.TextField(
		blank=True,
		default='{{FrontSide}}\n\n<hr id=answer>\n\n{{English}}',
		help_text='Anki card back template (afmt)'
	)
	css_style = models.TextField(
		blank=True,
		default=""".card {
    font-family: 'Segoe UI', 'Microsoft YaHei', '微軟正黑體', Arial, sans-serif;
    font-size: 20px;
    text-align: center;
    color: #2c3e50;
    background-color: #f9f9f9;
    padding: 20px;
    line-height: 1.6;
}

.card .front {
    font-size: 28px;
    font-weight: bold;
    color: #2980b9;
    margin-bottom: 15px;
}

.card .translation {
    font-size: 22px;
    color: #27ae60;
    margin: 15px 0;
}

.card .grammar,
.card .synonym {
    font-size: 16px;
    color: #7f8c8d;
    margin: 10px 0;
    font-style: italic;
}

.card .example {
    font-size: 18px;
    color: #34495e;
    margin: 12px 0;
    padding: 8px;
    background-color: #ecf0f1;
    border-radius: 4px;
}

.card .example-translation {
    font-size: 16px;
    color: #95a5a6;
    margin-top: 5px;
}

.card hr {
    border: none;
    border-top: 2px solid #bdc3c7;
    margin: 20px 0;
}

.card .audio {
    margin: 15px 0;
}

.card .hint,
.card .extend {
    font-size: 14px;
    color: #8e44ad;
    margin: 10px 0;
    text-align: left;
    padding: 10px;
    background-color: #f4ecf7;
    border-left: 3px solid #9b59b6;
    border-radius: 3px;
}""",
		help_text='Anki card CSS styling'
	)

	class Meta:
		db_table = 'card_templates'

	def __str__(self):
		return f'Template: {self.language.name}'
