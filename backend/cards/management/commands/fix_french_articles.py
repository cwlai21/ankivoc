"""
Management command to fix French article prefixes on existing VocabularyCards.

Rules applied:
  - Féminin singular + starts with vowel  → "de l'xxx"
  - Féminin singular + starts with consonant → "de la xxx"
  - Masculin singular + starts with vowel  → "de l'xxx"
  - Masculin singular + starts with consonant → "du xxx"
  - Plural (truly plural, not just grammar note) → "des xxx"
  - Adjectives → no article
  - "de l'xxx" display form: no space after apostrophe

Run:
    python manage.py fix_french_articles [--dry-run]
"""
import re
from django.core.management.base import BaseCommand
from cards.models import VocabularyCard


def compute_french_article(target_word, conjugaison_genre):
    """
    Return the corrected target_word with the proper French article prefix.
    Returns the original if no change is needed.
    """
    front = target_word.strip()
    conjugaison_lower = conjugaison_genre.lower() if conjugaison_genre else ''

    # Already has a de/du/des/au/aux/un/une prefix — check if it's correct, then leave alone
    preposition_prefixes = [
        "du ", "de la ", "de l'", "des ", "au ", "aux ",
        "un ", "une ",
    ]
    lower_front = front.lower()
    if any(lower_front.startswith(p) for p in preposition_prefixes):
        # Still validate "de l'" — ensure no space after apostrophe
        if lower_front.startswith("de l' "):
            # e.g. "de l' engueulade" → "de l'engueulade"
            fixed = "de l'" + front[6:]
            return fixed
        return front  # already correct

    # Strip simple articles before recomputing
    existing_articles = ["l'", "le ", "la ", "les ", "un ", "une "]
    for art in existing_articles:
        if lower_front.startswith(art):
            front = front[len(art):].lstrip()
            lower_front = front.lower()
            break

    cleaned_word = front.split(":")[-1].strip()
    starts_with_vowel = (
        cleaned_word and cleaned_word.lower()[0] in 'aeiouhâêîôûàéèù'
    )

    is_adjectif = 'adjectif' in conjugaison_lower
    is_masculin = any(t in conjugaison_lower for t in ('masculin', 'masculine', 'm.'))
    is_feminin = any(t in conjugaison_lower for t in ('feminin', 'féminin', 'feminine', 'f.'))

    # Determine if truly plural (ignore when plural form is just base word + s/x)
    ignore_pluriel = False
    if 'pluriel' in conjugaison_lower:
        plural_form_match = re.search(r'pluriel\s*:\s*(\w+)', conjugaison_lower)
        if plural_form_match:
            plural_form = plural_form_match.group(1)
            first_word = cleaned_word.lower().split()[0] if cleaned_word else ''
            if plural_form.startswith(first_word) and plural_form.endswith(('s', 'x')):
                ignore_pluriel = True

    is_plural = 'pluriel' in conjugaison_lower and not ignore_pluriel
    original_is_plural = target_word.lower().startswith(('des ', 'les '))

    article = ''
    if not is_adjectif:
        if is_plural and not original_is_plural:
            article = 'des'
        elif is_masculin:
            article = "de l'" if starts_with_vowel else 'du'
        elif is_feminin:
            article = "de l'" if starts_with_vowel else 'de la'

    if article:
        sep = '' if article.endswith("'") else ' '
        return f"{article}{sep}{front}".strip()
    return front


class Command(BaseCommand):
    help = 'Fix French article prefixes on existing VocabularyCards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        french_cards = VocabularyCard.objects.filter(
            batch__target_language__code='fr'
        ).exclude(target_word='').select_related('batch__target_language')

        total = french_cards.count()
        self.stdout.write(f'Scanning {total} French cards...\n')

        changed = 0
        for card in french_cards:
            if not card.conjugaison_genre:
                continue

            corrected = compute_french_article(card.target_word, card.conjugaison_genre)

            if corrected != card.target_word:
                self.stdout.write(
                    f'  Card #{card.id}: "{card.target_word}" → "{corrected}"'
                    f'  [{card.conjugaison_genre[:60]}]'
                )
                changed += 1
                if not dry_run:
                    card.target_word = corrected
                    card.save(update_fields=['target_word', 'updated_at'])

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDry run: {changed}/{total} cards would be updated.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nDone: {changed}/{total} cards updated.'
            ))
