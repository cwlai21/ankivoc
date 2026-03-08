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
    background-color: #ffffff;
    padding: 0;
    line-height: 1.6;
}

/* Title Bar Styling */
.TitleBar {
    padding: 10px;
    font-weight: bold;
    font-size: 16px;
    border-radius: 8px 8px 0 0;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.title-r {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.title-l {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
}

/* Tags */
.Tag {
    padding: 8px;
    font-size: 12px;
    margin-bottom: 15px;
}

.light-r {
    background-color: #e8eaf6;
    color: #5c6bc0;
    border-radius: 4px;
}

/* Text Card Styling */
.Text_Card {
    background-color: #fafafa;
    padding: 20px;
    margin: 10px;
}

.radius {
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.Text_big {
    font-size: 36px;
    font-weight: bold;
    color: #1a237e;
    margin: 20px 0;
}

.Text-answer {
    font-size: 28px;
    color: #2e7d32;
    margin: 15px 0;
    font-weight: 600;
}

/* Grammar/Verb Form */
.Verbform {
    font-size: 16px;
    color: #757575;
    font-style: italic;
    margin: 10px 0;
}

/* Gender-specific styling */
.feminine {
    border-left: 5px solid #e91e63;
    padding-left: 15px;
}

.masculine {
    border-left: 5px solid #2196f3;
    padding-left: 15px;
}

.neuter {
    border-left: 5px solid #4caf50;
    padding-left: 15px;
}

/* Examples List */
.light-r2 {
    background-color: #f5f5f5;
    border-radius: 8px;
    padding: 15px 30px;
    margin: 15px 10px;
    text-align: left;
    list-style: none;
}

.eB {
    font-size: 18px;
    color: #1976d2;
    font-weight: 500;
    margin: 10px 0;
    padding: 8px;
    background-color: #e3f2fd;
    border-radius: 4px;
}

.eg {
    font-size: 16px;
    color: #616161;
    margin: 5px 0 15px 20px;
    font-style: italic;
}

/* Extend/Hint Section */
.extend {
    font-size: 14px;
    color: #6a1b9a;
    margin: 15px 10px;
    text-align: left;
    padding: 12px;
    background-color: #f3e5f5;
    border-left: 4px solid #9c27b0;
    border-radius: 4px;
}

/* HR Separator */
hr#answer {
    border: none;
    border-top: 3px solid #e0e0e0;
    margin: 20px 0;
}

/* Synonyme */
.card .Synonyme {
    font-size: 16px;
    color: #00796b;
    margin: 10px 0;
    font-style: italic;
}

/* No Replay Button */
.noreplaybutton {
    display: none;
}""",
		help_text='Anki card CSS styling'
	)
	front_template_card2 = models.TextField(
		blank=True,
		default='{{Audio}}',
		help_text='Anki card 2 (Listening/Spelling) front template (qfmt2)'
	)
	back_template_card2 = models.TextField(
		blank=True,
		default='{{FrontSide}}\n\n<hr id=answer>\n\n{{TARGET_LANGUAGE}}',
		help_text='Anki card 2 (Listening/Spelling) back template (afmt2)'
	)

	class Meta:
		db_table = 'card_templates'

	def __str__(self):
		return f'Template: {self.language.name}'
