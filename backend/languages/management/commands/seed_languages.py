from django.core.management.base import BaseCommand
from languages.models import Language, CardTemplate


class Command(BaseCommand):
    help = 'Seed the database with initial languages and templates'

    def handle(self, *args, **options):
        # ── Create Languages ──
        languages_data = [
            {
                'name': 'French',
                'code': 'fr',
                'native_name': 'Français',
                'azure_tts_voice': 'fr-FR-DeniseNeural',
                'azure_tts_locale': 'fr-FR',
                'is_active': True,
            },
            {
                'name': 'English',
                'code': 'en',
                'native_name': 'English',
                'azure_tts_voice': 'en-US-JennyNeural',
                'azure_tts_locale': 'en-US',
                'is_active': True,
            },
            {
                'name': 'Chinese (Mandarin)',
                'code': 'zh',
                'native_name': '中文',
                'azure_tts_voice': 'zh-TW-HsiaoChenNeural',
                'azure_tts_locale': 'zh-TW',
                'is_active': True,
            },
            {
                'name': 'Spanish',
                'code': 'es',
                'native_name': 'Español',
                'azure_tts_voice': 'es-ES-ElviraNeural',
                'azure_tts_locale': 'es-ES',
                'is_active': False,
            },
            {
                'name': 'German',
                'code': 'de',
                'native_name': 'Deutsch',
                'azure_tts_voice': 'de-DE-KatjaNeural',
                'azure_tts_locale': 'de-DE',
                'is_active': False,
            },
            {
                'name': 'Japanese',
                'code': 'ja',
                'native_name': '日本語',
                'azure_tts_voice': 'ja-JP-NanamiNeural',
                'azure_tts_locale': 'ja-JP',
                'is_active': False,
            },
            {
                'name': 'Korean',
                'code': 'ko',
                'native_name': '한국어',
                'azure_tts_voice': 'ko-KR-SunHiNeural',
                'azure_tts_locale': 'ko-KR',
                'is_active': False,
            },
        ]

        for lang_data in languages_data:
            lang, created = Language.objects.update_or_create(
                code=lang_data['code'],
                defaults=lang_data
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'  {status}: {lang.name}')

        # ── Create French Card Template ──
        french = Language.objects.get(code='fr')
        template, created = CardTemplate.objects.get_or_create(
            language=french,
            defaults={
                'anki_model_name': 'French Vocabulary',
                'default_deck_name': 'French::Vocabulary',
                'fields_definition': [
                    'Français',
                    'English',
                    'Synonyme',
                    'Conjugaison/Gender',
                    'audio',
                    'exemple-FR',
                    'exemple-EN',
                    'exemple1-Audio',
                    'exemple2-FR',
                    'exemple2-EN',
                    'exemple2-Audio',
                    'Extend',
                    'Hint',
                ],
                'llm_prompt_template': (
                    'You are a French language teacher. '
                    'Given the input vocabulary "{input_text}", generate a complete '
                    'flashcard in JSON format with these fields:\n'
                    '- target_word: the French word/phrase\n'
                    '- explanation_word: English translation\n'
                    '- synonyme: French synonyms\n'
                    '- conjugaison_genre: conjugation or gender info\n'
                    '- exemple_target: example sentence in French\n'
                    '- exemple_explanation: same sentence in English\n'
                    '- exemple2_target: second example in French\n'
                    '- exemple2_explanation: second example in English\n'
                    '- extend: additional usage notes\n'
                    '- hint: a short hint for remembering\n'
                    'Return ONLY valid JSON.'
                ),
            }
        )
        status = 'Created' if created else 'Already exists'
        self.stdout.write(f'  {status}: French template')

        self.stdout.write(self.style.SUCCESS('\nSeeding complete!'))
