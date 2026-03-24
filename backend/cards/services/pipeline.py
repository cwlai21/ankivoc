import logging
import re
import time
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
 
        # Get or auto-create card template for target language
        try:
            self.template = self.target_lang.card_template
        except Exception:
            # Auto-generate default template for this language
            logger.info(f'No template found for {self.target_lang.name}, generating default template')
            self.template = self._create_default_template()

        # Thread pool for running blocking I/O (LLM, TTS) with timeouts
        # Use a small pool per pipeline instance to avoid blocking the main thread.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Timeouts (seconds) for external calls — configurable via settings
        # Increased to 120s to accommodate slow LLM providers and network delays
        self._llm_timeout = getattr(settings, 'LLM_CALL_TIMEOUT_SECONDS', 120)
        self._tts_timeout = getattr(settings, 'TTS_CALL_TIMEOUT_SECONDS', 30)

    def _create_default_template(self):
        """
        Auto-generate a default CardTemplate for the target language.
        Creates a template following the model: <NativeLanguageName>-(R/L)
        with dual card types (Reading + Listening).
        
        Returns:
            CardTemplate instance
        """
        from languages.models import CardTemplate
        
        # Get native name for deck/model naming
        native_name = self.target_lang.native_name or self.target_lang.name
        explanation_name = self.explanation_lang.name
        
        # Build model name: <NativeLanguageName>-(R/L), e.g., Español-(R/L)
        model_name = f"{native_name}-(R/L)"
        
        # Build deck name: <NativeLanguageName>::Vocabulary
        deck_name = f"{native_name}::Vocabulary"
        
        # Define field list using generic names (explanation-language agnostic)
        # This ensures the same model works with different explanation languages
        fields = [
            native_name,  # Target language word (e.g., "Español")
            'Explanation',  # Generic explanation field (works with any language)
            'Synonyme',
            'Conjugaison/Gender',
            'Audio',
            f'exemple-{self.target_lang.code.upper()}',  # e.g., exemple-ES
            'exemple-Explanation',  # Generic example translation
            'exemple1-Audio',
            f'exemple2-{self.target_lang.code.upper()}',
            'exemple2-Explanation',  # Generic example2 translation
            'exemple2-Audio',
            'Extend',
            'Hint',
            'No Spell',  # Controls whether typing practice is disabled
        ]
        
        # Get language-specific flag emoji (no external images needed)
        lang_flag_map = {
            'fr': '🇫🇷',
            'en': '🇬🇧',
            'zh': '🇨🇳',
            'es': '🇪🇸',
            'de': '🇩🇪',
            'ja': '🇯🇵',
            'ko': '🇰🇷',
        }
        lang_flag = lang_flag_map.get(self.target_lang.code, '🌐')
        
        # Card 1 template (Reading): Rich format with title bar and styling
        front_template = f"""<div class="TitleBar title-r">
<span style="font-size: 18px; padding-right: 5px;">{lang_flag}</span>
Reading 
<span style="font-size: 18px; padding-left: 5px;">{lang_flag}</span>
</div>
<div class="Tag light-r">
{{{{#Tags}}}} &nbsp; {{{{Tags}}}} {{{{/Tags}}}}</div> 

<div class="Text_Card radius">
<div id="register" class="Text_big">{{{{{native_name}}}}}</div>
{{{{#Conjugaison/Gender}}}}<div class="Verbform">{{{{Conjugaison/Gender}}}}{{{{/Conjugaison/Gender}}}}</br>{{{{Audio}}}}
</div>
</div>

<script>
{self._get_language_specific_script(self.target_lang.code, native_name)}
</script>"""
        
        # Card 1 back: Show everything with rich formatting
        back_template = f"""{{{{FrontSide}}}}
<div class="noreplaybutton"> [sound:silence1.mp3] </div>
<div class="Text_Card radius"><hr id=answer>
<div class="Text-answer">
{{{{Explanation}}}}
</div>
{{{{Synonyme}}}}
</div>

{{{{#exemple-{self.target_lang.code.upper()}}}}}
<ul class="light-r2">
					<li class="eB">{{{{exemple-{self.target_lang.code.upper()}}}}}{{{{exemple1-Audio}}}}
{{{{/exemple-{self.target_lang.code.upper()}}}}}
{{{{#exemple-{self.target_lang.code.upper()}}}}}
					<li class="eg">{{{{exemple-Explanation}}}}
{{{{/exemple-{self.target_lang.code.upper()}}}}}

{{{{#exemple2-{self.target_lang.code.upper()}}}}}
					<li class="eB">{{{{exemple2-{self.target_lang.code.upper()}}}}}{{{{exemple2-Audio}}}}
{{{{/exemple2-{self.target_lang.code.upper()}}}}}{{{{#exemple2-Explanation}}}}
					<li class="eg">{{{{exemple2-Explanation}}}}
{{{{/exemple2-Explanation}}}}
</ul>

{{{{#Extend}}}}
<div class="extend">
{{{{Extend}}}}
</div>
{{{{/Extend}}}}"""
        
        # Card 2 front: Listening/Spelling card with conditional display
        # If Audio exists: Listening & Spelling mode
        # If no Audio: Reading & Spelling mode with Explanation shown
        front_template_card2 = f"""{{{{#Audio}}}}
<div class="TitleBar title-l">
<span style="font-size: 18px; padding-right: 5px;">{lang_flag}</span>
Listening & Spelling
<span style="font-size: 18px; padding-left: 5px;">{lang_flag}</span>
</div>
<div class="Tag light-r">
{{{{#Tags}}}} &nbsp; {{{{Tags}}}} {{{{/Tags}}}}</div>

<div class="Text_Card radius">
<div class="Text_big">{{{{Audio}}}}</div>
{{{{#Hint}}}}<div class="Verbform" style="color: #818cf8; font-size: 14px;">💡 {{{{Hint}}}}</div>{{{{/Hint}}}}
</div>
{{{{/Audio}}}}

{{{{^Audio}}}}
<div class="TitleBar title-l">
<span style="font-size: 18px; padding-right: 5px;">{lang_flag}</span>
Reading & Spelling
<span style="font-size: 18px; padding-left: 5px;">{lang_flag}</span>
</div>
<div class="Tag light-r">
{{{{#Tags}}}} &nbsp; {{{{Tags}}}} {{{{/Tags}}}}</div>

<div class="Text_Card radius">
<div class="Text-answer">{{{{Explanation}}}}</div>
{{{{#Hint}}}}<div class="Verbform" style="color: #818cf8; font-size: 14px;">💡 {{{{Hint}}}}</div>{{{{/Hint}}}}
</div>
{{{{/Audio}}}}"""
        
        # Card 2 back: Show the front side with full answer - aligned with Card 1 format
        back_template_card2 = f"""{{{{FrontSide}}}}
<div class="noreplaybutton"> [sound:silence1.mp3] </div>
<div class="Text_Card radius"><hr id=answer>
<div class="Text-answer">
{{{{Explanation}}}}
</div>
{{{{Synonyme}}}}
</div>

{{{{#exemple-{self.target_lang.code.upper()}}}}}
<ul class="light-r2">
					<li class="eB">{{{{exemple-{self.target_lang.code.upper()}}}}}{{{{exemple1-Audio}}}}
{{{{/exemple-{self.target_lang.code.upper()}}}}}
{{{{#exemple-{self.target_lang.code.upper()}}}}}
					<li class="eg">{{{{exemple-Explanation}}}}
{{{{/exemple-{self.target_lang.code.upper()}}}}}

{{{{#exemple2-{self.target_lang.code.upper()}}}}}
					<li class="eB">{{{{exemple2-{self.target_lang.code.upper()}}}}}{{{{exemple2-Audio}}}}
{{{{/exemple2-{self.target_lang.code.upper()}}}}}{{{{#exemple2-Explanation}}}}
					<li class="eg">{{{{exemple2-Explanation}}}}
{{{{/exemple2-Explanation}}}}
</ul>

{{{{#Extend}}}}
<div class="extend">
{{{{Extend}}}}
</div>
{{{{/Extend}}}}"""
        
        # CSS styling - Dark theme optimized for better readability
        css_style = """
.card {
    font-family: 'Segoe UI', 'Microsoft YaHei', '微軟正黑體', Arial, sans-serif;
    font-size: 20px;
    text-align: center;
    color: #e0e0e0;
    background-color: #1e1e1e;
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
    background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3);
}

.title-l {
    background: linear-gradient(135deg, #ec4899 0%, #f43f5e 100%);
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(236, 72, 153, 0.3);
}

/* Tags */
.Tag {
    padding: 8px;
    font-size: 12px;
    margin-bottom: 15px;
}

.light-r {
    background-color: #2d2d44;
    color: #9ca3ff;
    border-radius: 4px;
}

/* Text Card Styling */
.Text_Card {
    background-color: #2a2a2a;
    padding: 20px;
    margin: 10px;
}

.radius {
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}

.Text_big {
    font-size: 36px;
    font-weight: bold;
    color: #a5b4fc;
    margin: 20px 0;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.Text-answer {
    font-size: 28px;
    color: #86efac;
    margin: 15px 0;
    font-weight: 600;
}

/* Grammar/Verb Form */
.Verbform {
    font-size: 20px;
    color: #9ca3af;
    font-style: italic;
    margin: 10px 0;
    max-width: 800px;
    line-height: 1.5;
    word-wrap: break-word;
}

/* Gender-specific styling */
.feminine {
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
}

/* Examples List */
.light-r2 {
    background-color: #2d2d2d;
    border-radius: 8px;
    padding: 15px 30px;
    margin: 15px 10px;
    text-align: left;
    list-style: none;
    border: 1px solid #404040;
}

.eB {
    font-size: 22px;
    color: #93c5fd;
    font-weight: 500;
    margin: 10px 0;
    padding: 8px;
    background-color: transparent;
    border-radius: 4px;
    max-width: 800px;
    line-height: 1.4;
    word-wrap: break-word;
}

.eg {
    font-size: 20px;
    color: #a1a1aa;
    margin: 5px 0 15px 20px;
    font-style: italic;
    max-width: 800px;
    line-height: 1.4;
    word-wrap: break-word;
}

/* Extend/Hint Section */
.extend {
    font-size: 18px;
    color: #c084fc;
    margin: 15px 10px;
    text-align: left;
    padding: 12px;
    background-color: transparent;
    border-left: 4px solid #a855f7;
    border-radius: 4px;
    line-height: 1.6;
    max-width: 800px;
    word-wrap: break-word;
}

/* HR Separator */
hr#answer {
    border: none;
    border-top: 3px solid #404040;
    margin: 20px 0;
}

/* Synonyme */
.card .Synonyme {
    font-size: 16px;
    color: #5eead4;
    margin: 10px 0;
    font-style: italic;
}

/* No Replay Button */
.noreplaybutton {
    display: none;
}
"""
        
        # Create and save the template
        template = CardTemplate.objects.create(
            language=self.target_lang,
            anki_model_name=model_name,
            default_deck_name=deck_name,
            fields_definition=fields,
            front_template=front_template,
            back_template=back_template,
            css_style=css_style,
            front_template_card2=front_template_card2,
            back_template_card2=back_template_card2,
        )
        
        logger.info(f'Created default template for {self.target_lang.name}: {model_name}')
        return template

    def _get_language_specific_script(self, lang_code, field_name):
        """
        Generate language-specific JavaScript logic for card front.
        
        Args:
            lang_code: Language code (e.g., 'fr', 'zh', 'es')
            field_name: The field name to check (e.g., 'Français', '中文')
            
        Returns:
            JavaScript code string
        """
        if lang_code == 'fr':
            # French: Detect gender by article (de la, du, des)
            return f'''
if ("{{{{{field_name}}}}}".startsWith('de la ')){{
    document.getElementById('register').classList.add('feminine');
}}
else if ("{{{{{field_name}}}}}".startsWith('du ')){{
    document.getElementById('register').classList.add('masculine');
}}
else if ("{{{{{field_name}}}}}".startsWith('des ')){{
    document.getElementById('register').classList.add('neuter');
}}
else if ("{{{{{field_name}}}}}".startsWith('la ')){{
    document.getElementById('register').classList.add('feminine');
}}
else if ("{{{{{field_name}}}}}".startsWith('le ')){{
    document.getElementById('register').classList.add('masculine');
}}
else if ("{{{{{field_name}}}}}".startsWith('les ')){{
    document.getElementById('register').classList.add('neuter');
}}
'''
        elif lang_code == 'es':
            # Spanish: Detect gender by article (la, el, las, los)
            return f'''
if ("{{{{{field_name}}}}}".startsWith('la ')){{
    document.getElementById('register').classList.add('feminine');
}}
else if ("{{{{{field_name}}}}}".startsWith('el ')){{
    document.getElementById('register').classList.add('masculine');
}}
else if ("{{{{{field_name}}}}}".startsWith('las ')){{
    document.getElementById('register').classList.add('feminine');
}}
else if ("{{{{{field_name}}}}}".startsWith('los ')){{
    document.getElementById('register').classList.add('masculine');
}}
'''
        elif lang_code == 'de':
            # German: Detect gender by article (die, der, das)
            return f'''
if ("{{{{{field_name}}}}}".startsWith('die ')){{
    document.getElementById('register').classList.add('feminine');
}}
else if ("{{{{{field_name}}}}}".startsWith('der ')){{
    document.getElementById('register').classList.add('masculine');
}}
else if ("{{{{{field_name}}}}}".startsWith('das ')){{
    document.getElementById('register').classList.add('neuter');
}}
'''
        elif lang_code == 'zh':
            # Chinese: Detect measure words (個/个, 位, 本, 張/张, etc.)
            return f'''
var word = "{{{{{field_name}}}}}";
// Common measure words highlighting
if (word.includes('\u500b') || word.includes('\u4e2a')){{ // 個/个 (general)
    document.getElementById('register').classList.add('masculine');
}}
else if (word.includes('\u4f4d')){{ // 位 (people, polite)
    document.getElementById('register').classList.add('feminine');
}}
else if (word.includes('\u672c')){{ // 本 (books)
    document.getElementById('register').classList.add('neuter');
}}
'''
        elif lang_code == 'ja':
            # Japanese: Detect particles or word types
            return f'''
var word = "{{{{{field_name}}}}}";
// Basic particle detection (hiragana particles)
if (word.includes('\u306f') || word.includes('\u304c')){{ // は or が
    document.getElementById('register').classList.add('masculine');
}}
else if (word.includes('\u3092')){{ // を
    document.getElementById('register').classList.add('feminine');
}}
'''
        elif lang_code == 'ko':
            # Korean: Detect particles
            return f'''
var word = "{{{{{field_name}}}}}";
// Korean particles
if (word.includes('\uc740') || word.includes('\ub294')){{ // 은/는
    document.getElementById('register').classList.add('masculine');
}}
else if (word.includes('\uc744') || word.includes('\ub97c')){{ // 을/를
    document.getElementById('register').classList.add('feminine');
}}
'''
        else:
            # Default: No specific logic
            return '// No language-specific logic'

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
 
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                result = self._run_with_timeout(
                    self.translator.translate,
                    self._llm_timeout,
                    card.input_text,
                    self.target_lang.code,
                    self.explanation_lang.code,
                )
                break  # Success, exit loop
            except concurrent.futures.TimeoutError:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"LLM call timed out after {self._llm_timeout}s. Retrying in {retry_delay} seconds... "
                        f"(Attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)
                else:
                    raise LLMTranslationError(f'LLM call timed out after {self._llm_timeout}s (failed after {max_retries} attempts)')
            except LLMTranslationError as e:
                error_msg = str(e).lower()
                # Retry on 503, 429 (rate limit), timeout, or connection errors
                should_retry = any(code in error_msg for code in ['503', '429', 'timeout', 'timed out', 'connection'])

                if should_retry and attempt < max_retries - 1:
                    logger.warning(
                        f"LLM error: {e}. Retrying in {retry_delay} seconds... "
                        f"(Attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)
                else:
                    raise  # Re-raise the exception if not retryable or it's the last attempt
        else:
            # This block executes if the loop completes without a `break`
            raise LLMTranslationError(f"LLM translation failed after {max_retries} attempts.")
 
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

        # Apply language-specific preprocessing rules before TTS
        # Currently supports French article/preposition addition
        # Can be extended for other languages as needed
        if self.target_lang.code == 'fr':
            # French-specific: Add appropriate article (du/de la/de l') based on gender
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
                    "un ", "une ",
                ]
                lower_front = front.lower()
                if any(lower_front.startswith(p) for p in preposition_prefixes):
                    logger.info(
                        "Detected existing French preposition/article prefix, "
                        "keeping original: '%s'", front
                    )
                else:
                    # Check and remove simple existing articles before recomputing
                    existing_articles = ["l'", "le ", "la ", "les ", "un ", "une "]
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
                    is_adjectif = 'adjectif' in conjugaison_lower
                    is_masculin = 'masculin' in conjugaison_lower or 'masculine' in conjugaison_lower or 'm.' in conjugaison_lower
                    is_feminin = 'feminin' in conjugaison_lower or 'féminin' in conjugaison_lower or 'feminine' in conjugaison_lower or 'f.' in conjugaison_lower
                    
                    # New logic to handle incorrect 'pluriel' from AI
                    ignore_pluriel = False
                    if 'pluriel' in conjugaison_lower:
                        # Extract the word from 'pluriel: ...'
                        plural_form_match = re.search(r'pluriel\s*:\s*(\w+)', conjugaison_lower)
                        if plural_form_match:
                            plural_form = plural_form_match.group(1)
                            # Check if the plural form is just the cleaned word + 's' or 'x'
                            if plural_form.startswith(cleaned_word.lower()) and plural_form.endswith(('s', 'x')):
                                # This is likely a case like "égout" -> "égouts"
                                # where the base word is singular.
                                ignore_pluriel = True
                                logger.info(
                                    "Detected a potentially incorrect 'pluriel' for '%s' (plural form: '%s'). "
                                    "Ignoring 'pluriel' and using gender.",
                                    cleaned_word, plural_form
                                )

                    is_plural = 'pluriel' in conjugaison_lower and not ignore_pluriel

                    # Check if the original word already starts with a plural article
                    original_is_plural = target_word.lower().startswith(('des ', 'les '))

                    article = ''
                    if not is_adjectif:
                        if is_plural and not original_is_plural:
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
        
        # Get language names for field mapping
        native_name = self.target_lang.native_name or self.target_lang.name
        explanation_name = self.explanation_lang.name
        target_code = self.target_lang.code.upper()
        explanation_code = self.explanation_lang.code.upper()
        
        # Query Anki for the actual model field names for this model.
        try:
            actual_model_fields = self.anki._invoke('modelFieldNames', modelName=model_name) or []
        except Exception:
            actual_model_fields = list(self.template.fields_definition or [])

        # Build case-insensitive lookup: lowercase → actual field name
        # Only keep the FIRST occurrence for each lowercase key to prefer
        # original fields over polluted duplicates (e.g. 'Exemple-FR' over 'exemple-FR+').
        model_map = {}
        for f in actual_model_fields:
            lk = f.lower()
            if lk not in model_map:
                model_map[lk] = f

        def resolve_field(*candidates):
            """Return the actual Anki model field name for the first matching candidate."""
            for c in candidates:
                actual = model_map.get(c.lower())
                if actual:
                    return actual
            return candidates[0] if candidates else None

        # Map pipeline values directly to actual Anki model field names.
        # Try multiple candidate names for each field to handle both legacy
        # models (e.g. 'English', 'Exemple-EN') and new generic models
        # (e.g. 'Explanation', 'exemple-Explanation').
        fields = {}

        # Target word
        fields[resolve_field(native_name)] = card.target_word or ''

        # Explanation: prefer language-specific name (e.g. 'English'), fallback to generic
        expl_field = resolve_field(explanation_name, 'Explanation')
        fields[expl_field] = card.explanation_word or ''
        # Also populate generic 'Explanation' if it exists as a separate field
        expl_generic = model_map.get('explanation')
        if expl_generic and expl_generic != expl_field:
            fields[expl_generic] = card.explanation_word or ''

        fields[resolve_field('Synonyme')] = card.synonyme or ''
        fields[resolve_field('Conjugaison/Gender')] = card.conjugaison_genre or ''
        fields[resolve_field('Audio')] = ''  # Filled by AnkiConnect audio attachment

        # Example 1 target: try 'Exemple-FR' (legacy) then 'exemple-FR' (generic)
        fields[resolve_field(f'Exemple-{target_code}', f'exemple-{target_code}')] = card.exemple_target or ''

        # Example 1 explanation: try 'Exemple-EN' (legacy) then 'exemple-Explanation' (generic)
        fields[resolve_field(
            f'Exemple-{explanation_code}', f'exemple-{explanation_code}',
            'exemple-Explanation'
        )] = card.exemple_explanation or ''

        # Example 1 audio
        fields[resolve_field('Exemple1-Audio', 'exemple1-Audio')] = ''

        # Example 2 target
        fields[resolve_field(f'Exemple2-{target_code}', f'exemple2-{target_code}')] = card.exemple2_target or ''

        # Example 2 explanation
        fields[resolve_field(
            f'Exemple2-{explanation_code}', f'exemple2-{explanation_code}',
            'exemple2-Explanation'
        )] = card.exemple2_explanation or ''

        # Example 2 audio
        fields[resolve_field('Exemple2-Audio', 'exemple2-Audio')] = ''

        fields[resolve_field('Extend')] = card.extend or ''
        fields[resolve_field('Hint')] = card.hint or ''

        logger.info(f'  Field mapping for card #{card.id}: {list(fields.keys())}')
 
        # Build audio files dict
        # Determine the exact field names from the template so AnkiConnect
        # inserts audio into the correct Anki note fields (matching is
        # case-insensitive and robust to variations like 'Audio',
        # 'exemple1-Audio', etc.).
        audio_files = {}
        from django.conf import settings
        from pathlib import Path
        media_root = Path(settings.MEDIA_ROOT)

        # Use actual model fields for audio mapping (not template fields)
        # to avoid case mismatches between template and Anki model.

        # Word audio: the 'Audio' field
        if card.audio_file:
            audio_field = resolve_field('Audio')
            audio_files[audio_field] = media_root / str(card.audio_file)

        # Example 1 audio
        if card.exemple1_audio:
            ex1_audio_field = resolve_field('Exemple1-Audio', 'exemple1-Audio')
            if ex1_audio_field:
                audio_files[ex1_audio_field] = media_root / str(card.exemple1_audio)

        # Example 2 audio
        if card.exemple2_audio:
            ex2_audio_field = resolve_field('Exemple2-Audio', 'exemple2-Audio')
            if ex2_audio_field:
                audio_files[ex2_audio_field] = media_root / str(card.exemple2_audio)

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

                # rebuild audio_files mapping using resolve_field
                audio_files = {}
                if card.audio_file:
                    audio_files[resolve_field('Audio')] = media_root / str(card.audio_file)

                if card.exemple1_audio:
                    ex1_af = resolve_field('Exemple1-Audio', 'exemple1-Audio')
                    if ex1_af:
                        audio_files[ex1_af] = media_root / str(card.exemple1_audio)

                if card.exemple2_audio:
                    ex2_af = resolve_field('Exemple2-Audio', 'exemple2-Audio')
                    if ex2_af:
                        audio_files[ex2_af] = media_root / str(card.exemple2_audio)
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
            if field_name in fields and fields[field_name]:
                fields[field_name] = re.sub(r'\[sound:.*?\]', '', fields[field_name]).strip()

        # Push to Anki
        result = self.anki.add_note(
            deck_name=deck_name,
            model_name=model_name,
            fields=fields,
            audio_files=audio_files if audio_files else None,
            tags=['vocab-builder'],
            card_template=self.template,
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
