import logging
import concurrent.futures
from django.conf import settings
from .llm_translator import LLMTranslator, LLMTranslationError
from .azure_tts import AzureTTSService, AzureTTSError
from .anki_connect import AnkiConnectClient, AnkiConnectError
from cards.models import VocabularyBatch, VocabularyCard
 
logger = logging.getLogger(__name__)
 
 
class CardPipeline:
    """
    Orchestrates the 3-stage card generation pipeline:
 
      1. LLM Translation  → Generates all text fields
      2. Azure TTS         → Generates audio files
      3. AnkiConnect Push  → Adds card to Anki
 
    Each card is processed independently so one failure
    doesn't block the others.
    """
    def __init__(self, batch):
        """
        Args:
            batch: VocabularyBatch instance to process
        """
        self.batch = batch
        self.user = batch.user
        self.target_lang = batch.target_language
        self.explanation_lang = batch.explanation_language
 
        # Initialize services
        self.translator = LLMTranslator()
        self.tts = AzureTTSService()
        self.anki = AnkiConnectClient(
            url=self.user.anki_connect_url,
            api_key=self.user.anki_connect_api_key,
        )
 
        # Get the card template for target language
        try:
            self.template = self.target_lang.card_template
        except Exception:
            raise ValueError(
                f'No card template found for {self.target_lang.name}. '
                f'Please ask an admin to create one.'
            )

        # Thread pool for running blocking I/O (LLM, TTS) with timeouts
        # Use a small pool per pipeline instance to avoid blocking the main thread.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Timeouts (seconds) for external calls — configurable via settings
        self._llm_timeout = getattr(settings, 'LLM_CALL_TIMEOUT_SECONDS', 20)
        self._tts_timeout = getattr(settings, 'TTS_CALL_TIMEOUT_SECONDS', 15)

    def _run_with_timeout(self, func, timeout, *args, **kwargs):
        """Run a blocking function in a thread and enforce a timeout."""
        fut = self._executor.submit(func, *args, **kwargs)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            fut.cancel()
            raise
        except Exception:
            # Re-raise to let caller handle/log the exception
            raise
 
    def process(self):
        """
        Main entry point. Processes all pending cards in the batch
        through the 3 stages.
        """
        logger.info(f'Starting pipeline for batch #{self.batch.id}')
 
        # Get only pending cards (supports retry of failed cards)
        pending_cards = self.batch.cards.filter(
            status=VocabularyCard.Status.PENDING
        )
 
        if not pending_cards.exists():
            logger.info(f'No pending cards in batch #{self.batch.id}')
            return
 
        # Ensure the deck exists in Anki
        try:
            deck_name = self._get_deck_name()
            self.anki.create_deck(deck_name)
            logger.info(f'Ensured deck exists: {deck_name}')
        except AnkiConnectError as e:
            logger.error(f'Cannot create deck: {e}')
            self.batch.status = VocabularyBatch.Status.FAILED
            self.batch.save()
            # Mark all cards as failed
            pending_cards.update(
                status=VocabularyCard.Status.FAILED,
                error_message=f'AnkiConnect error: {e}',
            )
            return
 
        # Before processing each card individually, attempt a batch TTS
        # pass that pre-generates audio for all pending cards that lack audio.
        cards_list = list(pending_cards)

        # Build items map: key -> text. Keys use '<card_id>.<kind>' where
        # kind is one of 'word', 'ex1', 'ex2'. synthesize_batch will dedupe
        # by text+voice and return filename map.
        items = {}
        for card in cards_list:
            if card.target_word and not card.audio_file:
                items[f'{card.id}.word'] = card.target_word
            if card.exemple_target and not card.exemple1_audio:
                items[f'{card.id}.ex1'] = card.exemple_target
            if card.exemple2_target and not card.exemple2_audio:
                items[f'{card.id}.ex2'] = card.exemple2_target

        if items:
            logger.info(f'Prefilling TTS for batch #{self.batch.id} with {len(items)} items')
            try:
                voice = self.target_lang.azure_tts_voice
                locale = self.target_lang.azure_tts_locale
                batch_timeout = getattr(settings, 'TTS_BATCH_TIMEOUT_SECONDS', 120)
                # Run batch synthesize with a bounded timeout; if it fails or
                # times out we fall back to per-card generation below.
                batch_result = self._run_with_timeout(
                    self.tts.synthesize_batch,
                    batch_timeout,
                    items,
                    voice,
                    locale,
                    6,
                )

                # batch_result maps key -> filename (or None). Reconstruct
                # relative paths using the same heuristic as synthesize_batch
                # (short text -> words, else -> examples).
                from pathlib import Path
                media_root = Path(settings.MEDIA_ROOT)
                for key, filename in (batch_result or {}).items():
                    if not filename:
                        continue
                    try:
                        cid_s, kind = key.split('.', 1)
                        cid = int(cid_s)
                    except Exception:
                        continue
                    # find card object
                    card_obj = next((c for c in cards_list if c.id == cid), None)
                    if not card_obj:
                        continue
                    text = items.get(key, '')
                    subfolder = 'words' if len(str(text)) <= 6 else 'examples'
                    rel = f'tts/{subfolder}/{filename}'
                    if kind == 'word':
                        card_obj.audio_file = rel
                    elif kind == 'ex1':
                        card_obj.exemple1_audio = rel
                    elif kind == 'ex2':
                        card_obj.exemple2_audio = rel

                # Persist any new audio paths
                for c in cards_list:
                    c.save()

            except concurrent.futures.TimeoutError:
                logger.warning(f'Batch TTS timed out after {batch_timeout}s; falling back to per-card TTS')
            except Exception as e:
                logger.warning(f'Batch TTS failed: {e}; falling back to per-card TTS')

        # Process each card through all 3 stages (use the materialized list)
        for card in cards_list:
            self._process_single_card(card)
 
        # Update batch status based on card results
        self._update_batch_status()
 
        logger.info(
            f'Pipeline complete for batch #{self.batch.id}: '
            f'{self.batch.pushed_cards} pushed, '
            f'{self.batch.failed_cards} failed'
        )
 
    def _get_deck_name(self):
        """
        Determine which Anki deck to use.
        Priority: user default > template default
        """
        if self.user.default_deck_name:
            return self.user.default_deck_name

        # Prefer a localized deck name using the language native name, with
        # an English suffix 'Vocabulary': <NativeLanguageName>::Vocabulary
        # e.g. Français::Vocabulary for French. Falls back to template value.
        try:
            native = self.target_lang.native_name or self.target_lang.name
            label = getattr(self.target_lang, 'vocab_label', None) or 'Vocabulary'
            return f"{native}::{label}"
        except Exception:
            return self.template.default_deck_name
 
    def _process_single_card(self, card):
        """
        Process a single card through all 3 stages.
        If any stage fails, the card is marked as failed
        and we move on to the next card.
 
        Args:
            card: VocabularyCard instance
        """
        logger.info(f'Processing card #{card.id}: "{card.input_text}"')
 
        # ── Stage 1: LLM Translation ──
        try:
            self._stage_translate(card)
        except LLMTranslationError as e:
            self._mark_card_failed(card, f'Translation failed: {e}')
            return
        except Exception as e:
            self._mark_card_failed(card, f'Unexpected translation error: {e}')
            return
 
        # ── Stage 2: Azure TTS ──
        try:
            self._stage_generate_tts(card)
        except AzureTTSError as e:
            self._mark_card_failed(card, f'TTS failed: {e}')
            return
        except Exception as e:
            self._mark_card_failed(card, f'Unexpected TTS error: {e}')
            return
 
        # ── Stage 3: Push to Anki ──
        try:
            self._stage_push_to_anki(card)
        except AnkiConnectError as e:
            self._mark_card_failed(card, f'AnkiConnect failed: {e}')
            return
        except Exception as e:
            self._mark_card_failed(card, f'Unexpected Anki error: {e}')
            return
 
        # Success
        card.status = VocabularyCard.Status.PUSHED
        card.save()
        logger.info(f'Card #{card.id} successfully pushed to Anki (note: {card.anki_note_id})')
 
    def _stage_translate(self, card):
        """
        Stage 1: Translate the input text using LLM.
        Populates all text fields on the card.
        """
        logger.info(f'  Stage 1 — Translating: "{card.input_text}"')
 
        self.batch.status = VocabularyBatch.Status.TRANSLATING
        self.batch.save()
 
        try:
            result = self._run_with_timeout(
                self.translator.translate,
                self._llm_timeout,
                card.input_text,
                self.target_lang.code,
                self.explanation_lang.code,
            )
        except concurrent.futures.TimeoutError:
            raise LLMTranslationError(f'LLM call timed out after {self._llm_timeout}s')
 
        # Populate card fields from LLM result
        card.target_word = result.get('target_word', card.input_text)
        card.explanation_word = result.get('explanation_word', '')
        card.synonyme = result.get('synonyme', '')
        card.conjugaison_genre = result.get('conjugaison_genre', '')
        card.exemple_target = result.get('exemple_target', '')
        card.exemple_explanation = result.get('exemple_explanation', '')
        card.exemple2_target = result.get('exemple2_target', '')
        card.exemple2_explanation = result.get('exemple2_explanation', '')
        card.extend = result.get('extend', '')
        card.hint = result.get('hint', '')

        # Apply French article rules before TTS
        if self.target_lang.code == 'fr':
            conjugaison_genre = card.conjugaison_genre
            target_word = card.target_word

            if conjugaison_genre and target_word:
                logger.info(f"--- Applying French Article Rules for word: {target_word} ---")

                front = target_word.strip()
                original_front = front

                # If the word already starts with a contracted preposition/article
                # like "du", "de la", "de l'", "des", "au", "aux", keep it as-is
                # to avoid duplicating (e.g. "du cabaret" -> "du du cabaret").
                preposition_prefixes = [
                    "du ", "de la ", "de l'", "des ", "au ", "aux ",
                ]
                lower_front = front.lower()
                if any(lower_front.startswith(p) for p in preposition_prefixes):
                    logger.info(
                        "Detected existing French preposition/article prefix, "
                        "keeping original: '%s'", front
                    )
                else:
                    # Check and remove simple existing articles before recomputing
                    existing_articles = ["l'", "le ", "la ", "les "]
                    for existing_article in existing_articles:
                        if lower_front.startswith(existing_article):
                            front = front[len(existing_article):].lstrip()
                            lower_front = front.lower()
                            break

                    cleaned_word = front.split(":")[-1].strip()
                    starts_with_vowel = (
                        cleaned_word.lower()
                        and cleaned_word.lower()[0] in 'aeiouhâêîôûàéèù'
                    )

                    conjugaison_lower = conjugaison_genre.lower()
                    is_masculin = 'masculin' in conjugaison_lower or 'masculine' in conjugaison_lower or 'm.' in conjugaison_lower
                    is_feminin = 'feminin' in conjugaison_lower or 'féminin' in conjugaison_lower or 'feminine' in conjugaison_lower or 'f.' in conjugaison_lower
                    is_pluriel = 'pluriel' in conjugaison_lower or 'plural' in conjugaison_lower

                    article = ''
                    if is_pluriel:
                        article = 'des'
                    elif is_masculin:
                        if starts_with_vowel:
                            article = "de l'"
                        else:
                            article = 'du'
                    elif is_feminin:
                        if starts_with_vowel:
                            article = "de l'"
                        else:
                            article = 'de la'

                    final_text = f"{article} {front}".strip() if article else front

                    if final_text != original_front:
                        logger.info(
                            "Text changed from '%s' to '%s' for TTS", original_front, final_text
                        )
                        card.target_word = final_text
        
        card.status = VocabularyCard.Status.TRANSLATED
        card.save()
 
        logger.info(f'  Translation done: "{card.input_text}" → "{card.target_word}"')
 
    def _stage_generate_tts(self, card):
        """
        Stage 2: Generate TTS audio files for:
          - The target word
          - Example sentence 1
          - Example sentence 2
        """
        logger.info(f'  Stage 2 — Generating TTS for card #{card.id}')
 
        self.batch.status = VocabularyBatch.Status.GENERATING_TTS
        self.batch.save()
 
        voice = self.target_lang.azure_tts_voice
        locale = self.target_lang.azure_tts_locale
 
        # Word audio (skip if already populated by batch TTS)
        if card.target_word and not card.audio_file:
            try:
                audio_path = self._run_with_timeout(
                    self.tts.synthesize_word,
                    self._tts_timeout,
                    text=card.target_word,
                    voice=voice,
                    locale=locale,
                    card_id=card.id,
                )
            except concurrent.futures.TimeoutError:
                raise AzureTTSError(f'TTS timed out after {self._tts_timeout}s')
            if audio_path:
                card.audio_file = audio_path
 
        # Example 1 audio (skip if already populated by batch TTS)
        if card.exemple_target and not card.exemple1_audio:
            try:
                ex1_path = self._run_with_timeout(
                    self.tts.synthesize_example,
                    self._tts_timeout,
                    text=card.exemple_target,
                    voice=voice,
                    locale=locale,
                    card_id=card.id,
                    example_number=1,
                )
            except concurrent.futures.TimeoutError:
                raise AzureTTSError(f'TTS example1 timed out after {self._tts_timeout}s')
            if ex1_path:
                card.exemple1_audio = ex1_path
 
        # Example 2 audio (skip if already populated by batch TTS)
        if card.exemple2_target and not card.exemple2_audio:
            try:
                ex2_path = self._run_with_timeout(
                    self.tts.synthesize_example,
                    self._tts_timeout,
                    text=card.exemple2_target,
                    voice=voice,
                    locale=locale,
                    card_id=card.id,
                    example_number=2,
                )
            except concurrent.futures.TimeoutError:
                raise AzureTTSError(f'TTS example2 timed out after {self._tts_timeout}s')
            if ex2_path:
                card.exemple2_audio = ex2_path
 
        card.status = VocabularyCard.Status.TTS_DONE
        card.save()
 
        logger.info(f'  TTS done for card #{card.id}')
 
    def _stage_push_to_anki(self, card):
        """
        Stage 3: Push the completed card to Anki via AnkiConnect.
        Maps card fields to the Anki note template fields.
        """
        logger.info(f'  Stage 3 — Pushing card #{card.id} to Anki')
 
        self.batch.status = VocabularyBatch.Status.PUSHING_TO_ANKI
        self.batch.save()
 
        deck_name = self._get_deck_name()

        # Build model name as <NativeLanguageName>-(R/L), e.g. Français-(R/L)
        # Default to 'Français-(R/L)' if not specified
        try:
            native = self.target_lang.native_name or self.target_lang.name
            model_name = f"{native}-(R/L)"
        except Exception:
            model_name = 'Français-(R/L)'
 
        # Build the fields dict matching the Anki note type.
        # Some Anki models use different casing (e.g. 'Exemple-FR' vs 'exemple-FR'),
        # so query Anki for the actual model field names and use those exact
        # names when constructing the payload.
        # Prepare a canonical mapping we expect from the pipeline -> model fields
        desired_keys = {
            'français': 'Français',
            'english': 'English',
            'synonyme': 'Synonyme',
            'conjugaison/gender': 'Conjugaison/Gender',
            'exemple-fr': 'exemple-FR',
            'exemple-en': 'exemple-EN',
            'exemple2-fr': 'exemple2-FR',
            'exemple2-en': 'exemple2-EN',
            'extend': 'Extend',
            'hint': 'Hint',
        }

        # Query Anki for the actual model field names for this model.
        try:
            actual_model_fields = self.anki._invoke('modelFieldNames', modelName=model_name) or []
        except Exception:
            actual_model_fields = list(self.template.fields_definition or [])

        # Build case-insensitive lookup
        model_map = {f.lower(): f for f in actual_model_fields}

        def pick_actual(key_variants):
            for v in key_variants:
                if v.lower() in model_map:
                    return model_map[v.lower()]
            # substring fallback
            for v in key_variants:
                lv = v.lower()
                for lower, real in model_map.items():
                    if lv in lower:
                        return real
            return None

        # Map pipeline values into the exact model field names
        fields = {}
        mapping = {
            'Français': card.target_word,
            'English': card.explanation_word,
            'Synonyme': card.synonyme,
            'Conjugaison/Gender': card.conjugaison_genre,
            'exemple-FR': card.exemple_target,
            'exemple-EN': card.exemple_explanation,
            'exemple2-FR': card.exemple2_target,
            'exemple2-EN': card.exemple2_explanation,
            'Extend': card.extend,
            'Hint': card.hint,
        }

        for k, v in mapping.items():
            actual = pick_actual([k, desired_keys.get(k.lower(), k)]) or k
            fields[actual] = v
 
        # Build audio files dict
        # Determine the exact field names from the template so AnkiConnect
        # inserts audio into the correct Anki note fields (matching is
        # case-insensitive and robust to variations like 'Audio',
        # 'exemple1-Audio', etc.).
        audio_files = {}
        from django.conf import settings
        from pathlib import Path
        media_root = Path(settings.MEDIA_ROOT)

        template_fields = []
        try:
            template_fields = [f for f in self.template.fields_definition]
        except Exception:
            template_fields = list(fields.keys())

        def find_field(containing=None, not_containing=None):
            """Return first template field name that contains all substrings
            in `containing` (case-insensitive) and does not contain any of
            `not_containing`. Returns None if not found."""
            lc = [t.lower() for t in template_fields]
            if containing:
                for i, t in enumerate(lc):
                    if all(p.lower() in t for p in containing):
                        if not not_containing or all(n.lower() not in t for n in not_containing):
                            return template_fields[i]
            else:
                for i, t in enumerate(lc):
                    if not not_containing or all(n.lower() not in t for n in not_containing):
                        return template_fields[i]
            return None

        # Word audio: prefer a field that contains 'audio' but not 'exemple'
        if card.audio_file:
            word_field = find_field(containing=['audio'], not_containing=['exemple'])
            if not word_field:
                # fallback to any field named like 'audio' or to the French text field
                word_field = find_field(containing=['audio']) or 'Français'
            # map template field -> actual model field name when possible
            actual_word_field = pick_actual([word_field]) or model_map.get(word_field.lower()) or word_field
            audio_files[actual_word_field] = media_root / str(card.audio_file)

        # Example 1 audio: look for 'exemple1' + 'audio', then 'exemple'+'audio', then any 'exemple'
        if card.exemple1_audio:
            ex1_field = find_field(containing=['exemple1', 'audio'])
            if not ex1_field:
                ex1_field = find_field(containing=['exemple', 'audio'])
            if not ex1_field:
                ex1_field = find_field(containing=['exemple'])
            if ex1_field:
                actual_ex1 = pick_actual([ex1_field]) or model_map.get(ex1_field.lower()) or ex1_field
                audio_files[actual_ex1] = media_root / str(card.exemple1_audio)

        # Example 2 audio: similar logic to example 1
        if card.exemple2_audio:
            ex2_field = find_field(containing=['exemple2', 'audio'])
            if not ex2_field:
                ex2_field = find_field(containing=['exemple2'])
            if not ex2_field:
                ex2_field = find_field(containing=['exemple', 'audio'])
            if not ex2_field:
                ex2_field = find_field(containing=['exemple'])
            if ex2_field:
                actual_ex2 = pick_actual([ex2_field]) or model_map.get(ex2_field.lower()) or ex2_field
                audio_files[actual_ex2] = media_root / str(card.exemple2_audio)

        # If no audio files were prepared, retry TTS generation once and rebuild
        # the `audio_files` mapping. This helps when transient TTS failures
        # resulted in empty audio fields earlier in the pipeline.
        if not audio_files:
            logger.warning('No audio files for card #%d; retrying TTS generation once', card.id)
            try:
                voice = self.target_lang.azure_tts_voice
                locale = self.target_lang.azure_tts_locale
                # Retry word
                if card.target_word and not card.audio_file:
                    try:
                        audio_path = self._run_with_timeout(
                            self.tts.synthesize_word,
                            self._tts_timeout,
                            text=card.target_word,
                            voice=voice,
                            locale=locale,
                            card_id=card.id,
                        )
                        if audio_path:
                            card.audio_file = audio_path
                    except concurrent.futures.TimeoutError:
                        logger.warning('TTS retry timed out for word on card #%d', card.id)

                # Retry example1
                if card.exemple_target and not card.exemple1_audio:
                    try:
                        ex1_path = self._run_with_timeout(
                            self.tts.synthesize_example,
                            self._tts_timeout,
                            text=card.exemple_target,
                            voice=voice,
                            locale=locale,
                            card_id=card.id,
                            example_number=1,
                        )
                        if ex1_path:
                            card.exemple1_audio = ex1_path
                    except concurrent.futures.TimeoutError:
                        logger.warning('TTS retry timed out for example1 on card #%d', card.id)

                # Retry example2
                if card.exemple2_target and not card.exemple2_audio:
                    try:
                        ex2_path = self._run_with_timeout(
                            self.tts.synthesize_example,
                            self._tts_timeout,
                            text=card.exemple2_target,
                            voice=voice,
                            locale=locale,
                            card_id=card.id,
                            example_number=2,
                        )
                        if ex2_path:
                            card.exemple2_audio = ex2_path
                    except concurrent.futures.TimeoutError:
                        logger.warning('TTS retry timed out for example2 on card #%d', card.id)

                # Persist any new audio paths and rebuild mapping
                card.save()

                # rebuild audio_files mapping
                audio_files = {}
                if card.audio_file:
                    word_field = find_field(containing=['audio'], not_containing=['exemple'])
                    if not word_field:
                        word_field = find_field(containing=['audio']) or 'Français'
                    actual_word_field = pick_actual([word_field]) or model_map.get(word_field.lower()) or word_field
                    audio_files[actual_word_field] = media_root / str(card.audio_file)

                if card.exemple1_audio:
                    ex1_field = find_field(containing=['exemple1', 'audio'])
                    if not ex1_field:
                        ex1_field = find_field(containing=['exemple', 'audio'])
                    if not ex1_field:
                        ex1_field = find_field(containing=['exemple'])
                    if ex1_field:
                        actual_ex1 = pick_actual([ex1_field]) or model_map.get(ex1_field.lower()) or ex1_field
                        audio_files[actual_ex1] = media_root / str(card.exemple1_audio)

                if card.exemple2_audio:
                    ex2_field = find_field(containing=['exemple2', 'audio'])
                    if not ex2_field:
                        ex2_field = find_field(containing=['exemple2'])
                    if not ex2_field:
                        ex2_field = find_field(containing=['exemple', 'audio'])
                    if not ex2_field:
                        ex2_field = find_field(containing=['exemple'])
                    if ex2_field:
                        actual_ex2 = pick_actual([ex2_field]) or model_map.get(ex2_field.lower()) or ex2_field
                        audio_files[actual_ex2] = media_root / str(card.exemple2_audio)
            except Exception as e:
                logger.warning('TTS retry failed for card #%d: %s', card.id, e)
 
        # Before pushing to Anki, verify expected audio files actually exist.
        # If any expected audio file is missing on disk, fail the card so it can
        # be investigated and retried (prevents pushing notes with empty audio
        # fields which break template rendering).
        missing = []
        for field_name, file_path in list(audio_files.items()):
            try:
                # audio_files values may be Path or string
                p = file_path if hasattr(file_path, 'exists') else media_root / str(file_path)
                if not p.exists():
                    missing.append((field_name, str(p)))
            except Exception:
                missing.append((field_name, str(file_path)))

        if missing:
            # Log and mark card failed so user can inspect / rerun later
            msgs = ", ".join([f"{f} -> {p}" for f, p in missing])
            err = f'Missing audio files for card {card.id}: {msgs}'
            logger.error(err)
            self._mark_card_failed(card, err)
            return

        import re

        # Defensive cleaning: Ensure audio fields are clean before passing to AnkiConnect.
        # This prevents duplicate [sound:...] tags if the field was somehow polluted before.
        for field_name in audio_files.keys():
            if field_name in fields:
                fields[field_name] = re.sub(r'\[sound:.*?\]', '', fields[field_name]).strip()

        # Push to Anki
        result = self.anki.add_note(
            deck_name=deck_name,
            model_name=model_name,
            fields=fields,
            audio_files=audio_files if audio_files else None,
            tags=['vocab-builder'],
        )
 
        card.anki_note_id = result['noteId']
        card.save()
 
    def _mark_card_failed(self, card, error_message):
        """Mark a card as failed with an error message."""
        logger.error(f'  Card #{card.id} failed: {error_message}')
        card.status = VocabularyCard.Status.FAILED
        card.error_message = error_message
        card.save()
 
    def _update_batch_status(self):
        """Update the batch status based on individual card results."""
        total = self.batch.cards.count()
        pushed = self.batch.cards.filter(status=VocabularyCard.Status.PUSHED).count()
        failed = self.batch.cards.filter(status=VocabularyCard.Status.FAILED).count()
 
        if pushed == total:
            self.batch.status = VocabularyBatch.Status.COMPLETED
        elif failed == total:
            self.batch.status = VocabularyBatch.Status.FAILED
        elif failed > 0:
            self.batch.status = VocabularyBatch.Status.PARTIAL_FAILURE
        else:
            self.batch.status = VocabularyBatch.Status.COMPLETED
 
        self.batch.save()
