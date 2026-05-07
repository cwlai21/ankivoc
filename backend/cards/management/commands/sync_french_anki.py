"""
Management command to sync fixed French "de l'" cards back to Anki via AnkiConnect.

For each French card in the DB whose target_word starts with "de l'":
  1. Updates the Français field in the Anki note (removes the space: "de l' x" → "de l'x")
  2. Replaces the Audio field with the new TTS file (une/un pronunciation)

Run:
    python manage.py sync_french_anki [--dry-run]
"""
import base64
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from cards.models import VocabularyCard
from cards.services.anki_connect import AnkiConnectClient, AnkiConnectError


class Command(BaseCommand):
    help = 'Sync fixed French "de l\'" cards (text + audio) back to Anki'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without touching Anki',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        media_root = Path(settings.MEDIA_ROOT)

        cards = VocabularyCard.objects.filter(
            batch__target_language__code='fr',
            anki_note_id__isnull=False,
        ).exclude(target_word='').select_related(
            'batch__target_language', 'batch__user'
        )

        affected = [c for c in cards if c.target_word.lower().startswith("de l'")]
        self.stdout.write(f'Found {len(affected)} French "de l\'" cards with Anki notes.\n')

        if not affected:
            self.stdout.write('Nothing to do.')
            return

        if dry_run:
            for card in affected:
                audio_path = media_root / str(card.audio_file) if card.audio_file else None
                audio_exists = audio_path.exists() if audio_path else False
                self.stdout.write(
                    f'  Card #{card.id} (note {card.anki_note_id}): '
                    f'text="{card.target_word}"  '
                    f'audio={"OK" if audio_exists else "MISSING"} ({card.audio_file})'
                )
            self.stdout.write(self.style.WARNING(
                f'\nDry run: {len(affected)} notes would be updated in Anki.'
            ))
            return

        # Connect to AnkiConnect using the first affected card's user settings
        first_user = affected[0].batch.user
        anki = AnkiConnectClient(
            url=first_user.anki_connect_url,
            api_key=first_user.anki_connect_api_key,
        )

        try:
            version = anki.test_connection()
            self.stdout.write(f'Connected to AnkiConnect v{version}\n')
        except AnkiConnectError as e:
            self.stderr.write(self.style.ERROR(f'Cannot connect to AnkiConnect: {e}'))
            return

        success = 0
        failed = 0

        for card in affected:
            note_id = card.anki_note_id
            lang = card.batch.target_language
            native_name = lang.native_name or lang.name  # e.g. "Français"

            self.stdout.write(
                f'  Card #{card.id} (note {note_id}): '
                f'"{card.target_word}"  audio={card.audio_file}'
            )

            # Build updateNoteFields payload
            update_payload = {
                'id': note_id,
                'fields': {
                    native_name: card.target_word,  # corrected text (no space after l')
                },
            }

            # Attach new audio if the file exists on disk
            if card.audio_file:
                audio_path = media_root / str(card.audio_file)
                if audio_path.exists():
                    try:
                        audio_data = base64.b64encode(audio_path.read_bytes()).decode('utf-8')
                        update_payload['audio'] = [{
                            'data': audio_data,
                            'filename': audio_path.name,
                            'fields': ['Audio'],
                        }]
                        # Clear the Audio field text first so AnkiConnect replaces it cleanly
                        update_payload['fields']['Audio'] = ''
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f'    Warning: could not read audio file: {e}'
                        ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'    Warning: audio file not found on disk: {audio_path}'
                    ))

            try:
                anki._invoke('updateNoteFields', note=update_payload)
                self.stdout.write(self.style.SUCCESS(f'    Updated note {note_id}'))
                success += 1
            except AnkiConnectError as e:
                self.stderr.write(self.style.ERROR(f'    Failed to update note {note_id}: {e}'))
                failed += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {success} notes updated in Anki, {failed} failed.'
        ))
