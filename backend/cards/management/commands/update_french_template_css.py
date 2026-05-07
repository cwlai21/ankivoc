"""
Management command to update the French card template CSS with gender coloring
(masculine=blue, feminine=red) and push the updated CSS to Anki.

Run:
    python manage.py update_french_template_css [--dry-run]
"""
from django.core.management.base import BaseCommand
from languages.models import CardTemplate
from cards.services.anki_connect import AnkiConnectClient, AnkiConnectError
from cards.models import VocabularyCard

GENDER_CSS = """
/* Gender-specific word coloring */
.Text_big.feminine {
    color: #f87171;
}

.Text_big.masculine {
    color: #60a5fa;
}

.Text_big.neuter {
    color: #818cf8;
}"""

# Old patterns that may exist in the DB template (to replace or remove)
OLD_PATTERNS = [
    """.feminine {
    border-left: 5px solid #f472b6;
    padding-left: 15px;
}

.masculine {
    border-left: 5px solid #60a5fa;
    padding-left: 15px;
}

.neuter {
    border-left: 5px solid #6ee7b7;
    padding-left: 15px;
}""",
    """.feminine {
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
}""",
    """/* Gender-specific word coloring */
.Text_big.feminine {
    color: #f87171;
}

.Text_big.masculine {
    color: #60a5fa;
}

.Text_big.neuter {
    color: #818cf8;
}""",
]


def apply_gender_css(css):
    """Remove any existing gender CSS blocks and append the new one."""
    for old in OLD_PATTERNS:
        if old in css:
            css = css.replace(old, '', 1)

    # Strip trailing whitespace and append new rules before the last closing block
    css = css.rstrip()
    css += '\n' + GENDER_CSS
    return css


class Command(BaseCommand):
    help = 'Update French card template CSS with gender coloring and push to Anki'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        try:
            template = CardTemplate.objects.get(language__code='fr')
        except CardTemplate.DoesNotExist:
            self.stderr.write(self.style.ERROR('No French CardTemplate found in DB.'))
            return

        new_css = apply_gender_css(template.css_style)

        if new_css == template.css_style:
            self.stdout.write('CSS already up to date — no changes needed.')
        else:
            self.stdout.write(f'Updating CSS for template: {template.anki_model_name}')
            if not dry_run:
                template.css_style = new_css
                template.save(update_fields=['css_style'])
                self.stdout.write(self.style.SUCCESS('  DB template CSS updated.'))
            else:
                self.stdout.write(self.style.WARNING('  [dry-run] Would update DB template CSS.'))

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run complete — Anki not touched.'))
            return

        # Push updated CSS to Anki via updateModelStyling
        card = VocabularyCard.objects.filter(
            batch__target_language__code='fr',
            anki_note_id__isnull=False,
        ).select_related('batch__user').first()

        if not card:
            self.stderr.write(self.style.WARNING('No pushed French cards found — skipping Anki update.'))
            return

        user = card.batch.user
        anki = AnkiConnectClient(url=user.anki_connect_url, api_key=user.anki_connect_api_key)

        try:
            version = anki.test_connection()
            self.stdout.write(f'Connected to AnkiConnect v{version}')
        except AnkiConnectError as e:
            self.stderr.write(self.style.ERROR(f'Cannot connect to AnkiConnect: {e}'))
            return

        try:
            anki._invoke(
                'updateModelStyling',
                model={
                    'name': template.anki_model_name,
                    'css': new_css,
                }
            )
            self.stdout.write(self.style.SUCCESS(
                f'  Pushed CSS to Anki model "{template.anki_model_name}".'
            ))
        except AnkiConnectError as e:
            self.stderr.write(self.style.ERROR(f'  Failed to push to Anki: {e}'))
