"""
Management command to regenerate TTS audio for French cards whose target_word
starts with "de l'" — the audio should use "une/un xxx" for natural pronunciation.

Run:
    python manage.py fix_french_tts [--dry-run]
"""
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from cards.models import VocabularyCard
from cards.services.azure_tts import AzureTTSService, AzureTTSError


def get_tts_text(target_word, conjugaison_genre):
    """Return the TTS-friendly text for a "de l'xxx" word."""
    bare_word = target_word[5:]  # strip "de l'"
    conjugaison_lower = (conjugaison_genre or '').lower()
    is_feminin = any(t in conjugaison_lower for t in ('feminin', 'féminin', 'feminine', 'f.'))
    return f"une {bare_word}" if is_feminin else f"un {bare_word}"


class Command(BaseCommand):
    help = 'Regenerate TTS audio for French "de l\'" cards using un/une pronunciation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without regenerating audio',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        cards = VocabularyCard.objects.filter(
            batch__target_language__code='fr',
        ).exclude(target_word='').select_related(
            'batch__target_language'
        )

        affected = [
            c for c in cards
            if c.target_word.lower().startswith("de l'")
        ]

        self.stdout.write(f'Found {len(affected)} French "de l\'" cards to fix.\n')

        if dry_run:
            for card in affected:
                tts_text = get_tts_text(card.target_word, card.conjugaison_genre)
                self.stdout.write(
                    f'  Card #{card.id}: TTS would change from '
                    f'"{card.target_word}" → "{tts_text}"  '
                    f'[audio: {card.audio_file or "none"}]'
                )
            self.stdout.write(self.style.WARNING(
                f'\nDry run: {len(affected)} cards would have audio regenerated.'
            ))
            return

        try:
            tts = AzureTTSService()
        except AzureTTSError as e:
            self.stderr.write(self.style.ERROR(f'TTS service unavailable: {e}'))
            return

        media_root = Path(settings.MEDIA_ROOT)
        success = 0
        failed = 0

        for card in affected:
            tts_text = get_tts_text(card.target_word, card.conjugaison_genre)
            lang = card.batch.target_language
            voice = lang.azure_tts_voice
            locale = lang.azure_tts_locale

            self.stdout.write(
                f'  Card #{card.id}: regenerating TTS for "{tts_text}" '
                f'(was: "{card.target_word}")'
            )

            try:
                new_audio_path = tts.synthesize_word(
                    text=tts_text,
                    voice=voice,
                    locale=locale,
                    card_id=card.id,
                )
            except AzureTTSError as e:
                self.stderr.write(self.style.ERROR(f'    Failed: {e}'))
                failed += 1
                continue

            # Delete old audio file from disk
            if card.audio_file:
                old_path = media_root / str(card.audio_file)
                if old_path.exists():
                    try:
                        old_path.unlink()
                        self.stdout.write(f'    Deleted old audio: {old_path.name}')
                    except Exception as e:
                        self.stdout.write(f'    Warning: could not delete old audio: {e}')

            card.audio_file = new_audio_path
            card.save(update_fields=['audio_file', 'updated_at'])
            self.stdout.write(self.style.SUCCESS(f'    New audio: {new_audio_path}'))
            success += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {success} regenerated, {failed} failed.'
        ))
