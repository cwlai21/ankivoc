from django.db import models
from django.conf import settings


class VocabularyBatch(models.Model):
    """A batch of vocabulary words submitted by a user."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        TRANSLATING = 'translating', 'Translating'
        GENERATING_TTS = 'generating_tts', 'Generating TTS'
        PUSHING_TO_ANKI = 'pushing_to_anki', 'Pushing to Anki'
        COMPLETED = 'completed', 'Completed'
        PARTIAL_FAILURE = 'partial_failure', 'Partial Failure'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='batches',
        help_text='The user who submitted this batch'
    )
    target_language = models.ForeignKey(
        'languages.Language',
        on_delete=models.CASCADE,
        related_name='target_batches',
        help_text='The language being learned'
    )
    explanation_language = models.ForeignKey(
        'languages.Language',
        on_delete=models.CASCADE,
        related_name='explanation_batches',
        help_text='The language used for explanations'
    )
    raw_input = models.TextField(
        help_text='Raw vocabulary input from user, one word/phrase per line'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    error_message = models.TextField(
        blank=True,
        default='',
        help_text='Global error message if the whole batch fails'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vocabulary_batches'
        ordering = ['-created_at']
        verbose_name = 'Vocabulary Batch'
        verbose_name_plural = 'Vocabulary Batches'

    def __str__(self):
        return f'Batch #{self.id} by {self.user.username} ({self.status})'

    @property
    def total_cards(self):
        return self.cards.count()

    @property
    def pushed_cards(self):
        return self.cards.filter(status=VocabularyCard.Status.PUSHED).count()

    @property
    def failed_cards(self):
        return self.cards.filter(status=VocabularyCard.Status.FAILED).count()


class VocabularyCard(models.Model):
    """Individual card within a batch."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        TRANSLATED = 'translated', 'Translated'
        TTS_DONE = 'tts_done', 'TTS Done'
        PUSHED = 'pushed', 'Pushed to Anki'
        FAILED = 'failed', 'Failed'

    batch = models.ForeignKey(
        VocabularyBatch,
        on_delete=models.CASCADE,
        related_name='cards',
        help_text='The batch this card belongs to'
    )

    # ── Raw Input ──
    input_text = models.CharField(
        max_length=500,
        help_text='Original vocabulary input, e.g. de la pomme'
    )

    # ── Card Fields (matching your Anki template) ──
    target_word = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Word in target language (Français field)'
    )
    explanation_word = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Translation/explanation (English field)'
    )
    synonyme = models.TextField(
        blank=True,
        default='',
        help_text='Synonyms in target language'
    )
    conjugaison_genre = models.TextField(
        blank=True,
        default='',
        help_text='Conjugation tables or gender information'
    )
    audio_file = models.FileField(
        upload_to='tts/words/',
        blank=True,
        null=True,
        help_text='TTS audio of the target word'
    )
    exemple_target = models.TextField(
        blank=True,
        default='',
        help_text='Example sentence in target language'
    )
    exemple_explanation = models.TextField(
        blank=True,
        default='',
        help_text='Example sentence translation'
    )
    exemple1_audio = models.FileField(
        upload_to='tts/examples/',
        blank=True,
        null=True,
        help_text='TTS audio of example sentence 1'
    )
    exemple2_target = models.TextField(
        blank=True,
        default='',
        help_text='Second example in target language'
    )
    exemple2_explanation = models.TextField(
        blank=True,
        default='',
        help_text='Second example translation'
    )
    exemple2_audio = models.FileField(
        upload_to='tts/examples/',
        blank=True,
        null=True,
        help_text='TTS audio of example sentence 2'
    )
    extend = models.TextField(
        blank=True,
        default='',
        help_text='Additional notes, usage, cultural context'
    )
    hint = models.TextField(
        blank=True,
        default='',
        help_text='Memory hint or mnemonic'
    )

    # ── Status & Meta ──
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    anki_note_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='Note ID returned by AnkiConnect after successful push'
    )
    error_message = models.TextField(
        blank=True,
        default='',
        help_text='Error message if card processing failed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vocabulary_cards'
        ordering = ['id']
        verbose_name = 'Vocabulary Card'
        verbose_name_plural = 'Vocabulary Cards'

    def __str__(self):
        return f'{self.input_text} → {self.target_word} ({self.status})'# Models placeholder for `cards` app.

# Add model classes here when implemented.
