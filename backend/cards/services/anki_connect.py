import base64
import logging
import time
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class AnkiConnectError(Exception):
    """Raised when AnkiConnect returns an error."""
    pass


class AnkiConnectClient:
    """
    Client for communicating with AnkiConnect.

    AnkiConnect must be running on the user's machine.
    Default URL: http://localhost:8765

    API Reference: https://foosoft.net/projects/anki-connect/
    """

    def __init__(self, url='http://localhost:8765', api_key=''):
        self.url = url.rstrip('/')
        self.api_key = api_key

    def _invoke(self, action, **params):
        """
        Send a request to AnkiConnect.

        Args:
            action: AnkiConnect action name
            **params: Action parameters

        Returns:
            The result from AnkiConnect

        Raises:
            AnkiConnectError: If AnkiConnect returns an error
        """
        payload = {
            'action': action,
            'version': 6,
            'params': params,
        }

        if self.api_key:
            payload['key'] = self.api_key

        logger.debug(f'AnkiConnect request: {action} with params: {params.keys()}')

        try:
            response = requests.post(
                self.url,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.ConnectionError:
            raise AnkiConnectError(
                f'Cannot connect to AnkiConnect at {self.url}. '
                f'Is Anki running with AnkiConnect add-on installed?'
            )
        except requests.Timeout:
            raise AnkiConnectError(
                f'AnkiConnect request timed out at {self.url}.'
            )
        except requests.RequestException as e:
            raise AnkiConnectError(f'AnkiConnect request failed: {e}')

        result = response.json()

        if result.get('error'):
            raise AnkiConnectError(f'AnkiConnect error: {result["error"]}')

        return result.get('result')

    def test_connection(self):
        """
        Test the connection to AnkiConnect.

        Returns:
            AnkiConnect version number (int)
        """
        return self._invoke('version')

    def get_deck_names(self):
        """Get all deck names."""
        return self._invoke('deckNames')

    def get_model_names(self):
        """Get all note type (model) names."""
        return self._invoke('modelNames')

    def create_deck(self, deck_name):
        """
        Create a deck if it doesn't exist.

        Args:
            deck_name: Name of the deck, e.g. 'French::Vocabulary'
        """
        # Ask Anki to create the deck then poll until it appears in deckNames.
        try:
            self._invoke('createDeck', deck=deck_name)
        except Exception as e:
            raise

        # Poll for deck presence — small backoff to avoid race between createDeck and addNote
        attempts = 0
        max_attempts = getattr(settings, 'ANKI_CREATE_DECK_POLL_MAX', 8)
        delay = getattr(settings, 'ANKI_CREATE_DECK_POLL_DELAY', 0.25)
        while attempts < max_attempts:
            try:
                decks = self.get_deck_names()
                if deck_name in decks:
                    return True
            except Exception:
                # Ignore transient errors and retry
                pass
            time.sleep(delay)
            attempts += 1

        # If still not present, raise so caller can handle it
        raise AnkiConnectError(f'deck was not found after createDeck: {deck_name}')

    def create_model_if_missing(self, model_name, in_order_fields):
        """
        Create a simple Anki note type (model) if it does not already exist.

        Args:
            model_name: Name of the model to ensure exists
            in_order_fields: List of field names in order
        """
        existing = self.get_model_names()
        if model_name in existing:
            return True

        # Build dual card templates (Reading + Listening) using the provided fields
        if not in_order_fields:
            in_order_fields = ['Front', 'Back']

        first = in_order_fields[0]
        second = in_order_fields[1] if len(in_order_fields) > 1 else ''

        # Card 1: Reading card - show target word/phrase
        qfmt1 = f"<div style='font-size: 24px;'>{{{{{first}}}}}</div>"
        
        all_fields_html = ''.join([f"<div><b>{f}</b>: {{{{{f}}}}}</div>" for f in in_order_fields])
        afmt1 = "{{FrontSide}}<hr id=answer>" + all_fields_html

        # Card 2: Listening card - show audio prompt
        # Find 'Audio' field in the field list
        audio_field = None
        for f in in_order_fields:
            if 'audio' in f.lower() and 'exemple' not in f.lower():
                audio_field = f
                break
        
        if audio_field:
            # Listening card: play audio, then show answer
            qfmt2 = f"<div style='font-size: 14px; color: #666;'>🔊 Listen and identify:</div><br>{{{{{audio_field}}}}}"
            afmt2 = f"{{{{FrontSide}}}}<hr id=answer><div style='font-size: 24px;'>{{{{{first}}}}}</div>"
            if second:
                afmt2 += f"<br><div style='font-size: 18px;'>{{{{{second}}}}}</div>"
        else:
            # Fallback: Create a different Card 2 that shows translation first
            # This ensures Card 2 front is never identical to Card 1
            if second:
                qfmt2 = f"<div style='font-size: 20px; color: #666;'>Translate to {first}:</div><br><div style='font-size: 24px;'>{{{{{second}}}}}</div>"
                afmt2 = f"{{{{FrontSide}}}}<hr id=answer><div style='font-size: 24px;'>{{{{{first}}}}}</div>"
            else:
                # If only one field, make Card 2 show a hint
                qfmt2 = f"<div style='color: #999;'>What is:</div><br><div style='font-size: 18px;'>{{{{{first}}}}}</div>"
                afmt2 = "{{FrontSide}}<hr id=answer>" + all_fields_html

        # Universal CSS template for all languages
        css = """.card {
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
}
"""
        
        # Create dual card templates for Reading + Listening
        # AnkiConnect expects 'Name', 'Front', 'Back' (capitalized)
        card_templates = [
            {
                'Name': 'Card 1',
                'Front': qfmt1,
                'Back': afmt1,
            },
            {
                'Name': 'Card 2',
                'Front': qfmt2,
                'Back': afmt2,
            },
        ]

        # Try multiple candidate payload shapes to handle differing AnkiConnect versions
        candidates = [
            # Standard AnkiConnect format with capitalized template keys
            {
                'modelName': model_name,
                'inOrderFields': in_order_fields,
                'css': css,
                'cardTemplates': card_templates,
            },
            # Legacy lowercase format
            {
                'modelName': model_name,
                'inOrderFields': in_order_fields,
                'css': css,
                'cardTemplates': [
                    {
                        'name': 'Card 1',
                        'qfmt': qfmt1,
                        'afmt': afmt1,
                    },
                    {
                        'name': 'Card 2',
                        'qfmt': qfmt2,
                        'afmt': afmt2,
                    },
                ],
            },
        ]

        for params in candidates:
            try:
                logger.debug('Attempting createModel with keys: %s', list(params.keys()))
                # Attempt to create model
                self._invoke('createModel', **params)
                # After a successful createModel call, poll for model presence briefly
                poll_attempts = 0
                poll_max = getattr(settings, 'ANKI_CREATE_MODEL_POLL_MAX', 8)
                poll_delay = getattr(settings, 'ANKI_CREATE_MODEL_POLL_DELAY', 0.25)
                while poll_attempts < poll_max:
                    try:
                        existing = self.get_model_names()
                        if model_name in existing:
                            logger.info('Created model %s using keys: %s', model_name, list(params.keys()))
                            return True
                    except Exception:
                        # transient error listing models; retry
                        pass
                    poll_attempts += 1
                    time.sleep(poll_delay)
            except Exception as e:
                logger.warning('createModel attempt failed (keys=%s): %s', list(params.keys()), e)
            # Check if model was created
            try:
                existing = self.get_model_names()
                if model_name in existing:
                    logger.info('Created model %s using keys: %s', model_name, list(params.keys()))
                    return True
            except Exception:
                # If we cannot list models, continue trying other shapes
                pass

        logger.warning('Unable to create model %s with any known parameter shapes', model_name)
        return False

    def add_note(self, deck_name, model_name, fields, audio_files=None, tags=None):
        """
        Add a single note to Anki.

        Args:
            deck_name: Target deck name
            model_name: Note type (model) name
            fields: Dict of field name → value
            audio_files: Dict of field name → file path for audio fields
            tags: List of tags to add to the note

        Returns:
            Dict with noteId
        """
        # Ensure model exists; try to create a basic one if missing.
        try:
            created = self.create_model_if_missing(model_name, list(fields.keys()))
        except Exception:
            created = False
            logger.debug('create_model_if_missing failed or skipped')

        # If model still doesn't exist on the Anki side, fall back to 'Français-(R/L)'
        existing_models = self.get_model_names()
        if model_name not in existing_models:
            logger.warning(f'Model "{model_name}" not present in Anki; falling back to "Français-(R/L)"')
            model_name = 'Français-(R/L)'

        # Map fields to the target model's expected field names.
        #
        # For historical reasons, we supported a "legacy" mapping for the
        # 'Français-(R/L)' model where callers passed generic keys like
        # "Word", "Example 1", etc. The current pipeline already builds
        # fields using the real Anki field names ("Français", "English",
        # "Exemple-FR", ...), so blindly remapping here would erase all
        # values and produce an empty note.
        #
        # To remain backward compatible, only apply the legacy mapping when
        # we actually detect those old-style keys. Otherwise, keep the
        # provided fields as-is.

        note = {
            'deckName': deck_name,
            'modelName': model_name,
            'fields': fields,
            'options': {
                'allowDuplicate': False,
                'duplicateScope': 'deck',
            },
            'tags': tags or [],
        }

        # Handle audio files
        if audio_files:
            audio_list = []
            for field_name, file_path in audio_files.items():
                if file_path:
                    try:
                        # Read file and encode as base64
                        with open(str(file_path), 'rb') as f:
                            audio_data = base64.b64encode(f.read()).decode('utf-8')

                        filename = f'{field_name}_{file_path.name}' if hasattr(file_path, 'name') else f'{field_name}.mp3'

                        audio_list.append({
                            'data': audio_data,
                            'filename': filename,
                            'fields': [field_name],
                        })
                    except FileNotFoundError:
                        logger.warning(f'Audio file not found: {file_path}')
                    except Exception as e:
                        logger.warning(f'Error reading audio file {file_path}: {e}')

            if audio_list:
                # Let AnkiConnect handle inserting [sound:...] tags into the
                # appropriate fields. Manually appending tags here caused
                # duplicates like [sound:X][sound:X] in the stored field
                # value, because AnkiConnect also appends its own tag.
                note['audio'] = audio_list

        # Try adding the note, with remediation retries for deck/model race conditions.
        last_exc = None
        max_attempts = getattr(settings, 'ANKI_ADD_NOTE_MAX_ATTEMPTS', 4)
        backoff_base = getattr(settings, 'ANKI_ADD_NOTE_BACKOFF_BASE', 0.5)
        for attempt in range(1, max_attempts + 1):
            try:
                note_id = self._invoke('addNote', note=note)
                if note_id is None:
                    raise AnkiConnectError('Failed to add note. It may be a duplicate.')

                logger.info(f'Added note {note_id} to deck "{deck_name}"')
                return {'noteId': note_id}
            except AnkiConnectError as e:
                last_exc = e
                msg = str(e).lower()
                # Detect transient missing-deck/model errors and attempt remediation
                if ('deck was not found' in msg) or ('model was not found' in msg) or ('was not found' in msg):
                    logger.warning('addNote attempt %d failed due to missing deck/model: %s', attempt, e)
                    # Attempt to recreate deck and model, then retry after backoff
                    try:
                        try:
                            self._invoke('createDeck', deck=deck_name)
                        except Exception:
                            # create_deck wrapper will handle polling; call it if available
                            try:
                                self.create_deck(deck_name)
                            except Exception:
                                logger.debug('create_deck quick attempt failed; will continue')

                        try:
                            # Recreate model if possible
                            self.create_model_if_missing(model_name, list(fields.keys()))
                        except Exception:
                            logger.debug('create_model_if_missing attempt failed; will continue')
                    except Exception:
                        logger.debug('Remediation attempts failed; continuing to retry')

                    # Exponential backoff before retrying
                    backoff = backoff_base * (2 ** (attempt - 1))
                    time.sleep(backoff)
                    continue
                else:
                    # Non-transient error — re-raise
                    raise

        # If we get here, all attempts failed
        raise AnkiConnectError(f'Failed to add note after {max_attempts} attempts: {last_exc}')

    def add_notes(self, notes):
        """
        Add multiple notes at once.

        Args:
            notes: List of note dicts (same format as add_note)

        Returns:
            List of note IDs (None for failed ones)
        """
        return self._invoke('addNotes', notes=notes)

    def sync(self):
        """Trigger Anki sync."""
        return self._invoke('sync')
