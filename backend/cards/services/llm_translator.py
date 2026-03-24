import os
import json
import logging
import requests
import re
 
logger = logging.getLogger(__name__)
 
 
class LLMTranslationError(Exception):
    """Raised when LLM translation fails."""
    pass
 
 
class LLMTranslator:
    """
    Translates vocabulary and generates complete card content using an LLM.
 
    Supports: OpenAI, Groq (OpenAI-compatible), Gemini
    """
 
    # Map provider to base URL
    PROVIDER_URLS = {
        'openai': 'https://api.openai.com/v1',
        'groq': 'https://api.groq.com/openai/v1',
        'gemini': 'https://generativelanguage.googleapis.com/v1',
    }
 
    # Map provider to default model
    PROVIDER_MODELS = {
        'openai': 'gpt-4o-mini',
        'groq': 'llama-3.3-70b-versatile',
        'gemini': 'gemini-2.5-flash',
    }
 
    def __init__(self):
        # Do not require an API key at init time; keys are fetched lazily per-provider
        self.provider = os.getenv('LLM_PROVIDER', 'gemini')
        self.base_url = self.PROVIDER_URLS.get(self.provider)
        # default model selection (may be overridden per provider later)
        self.model = os.getenv('LLM_MODEL', self.PROVIDER_MODELS.get(self.provider))
        self.client = None

    def _get_api_key_for(self, provider):
        """Return API key for a given provider or None if not set."""
        key_map = {
            'openai': 'OPENAI_API_KEY',
            'groq': 'GROQ_API_KEY',
            'gemini': 'GOOGLE_API_KEY',
        }
        env_var = key_map.get(provider)
        if not env_var:
            return None
        return os.getenv(env_var)
 
    def _build_system_prompt(self, target_lang_name, explanation_lang_name):
        """Build the system prompt for card generation.

        Prefer loading a project-level `backend/config/system_prompt.md` file
        (same behavior as `anki_voc.py`). If the file exists, use its
        contents as the system prompt and attempt simple formatting with
        language names. Otherwise fall back to the built-in prompt.
        """
        # Look for backend/config/system_prompt.md relative to this file
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parents[2].joinpath('config', 'system_prompt.md')
        if cfg_path.exists():
            try:
                text = cfg_path.read_text(encoding='utf-8')
                # Allow templates in the system prompt like {target_lang} etc.
                try:
                    text = text.format(
                        target_lang=target_lang_name,
                        explanation_lang=explanation_lang_name,
                        target_lang_name=target_lang_name,
                        explanation_lang_name=explanation_lang_name,
                    )
                except Exception:
                    # If formatting fails, use raw text
                    pass
                logger.debug('Loaded system prompt from %s', cfg_path)
                return text
            except Exception as e:
                logger.warning('Failed to read system_prompt.md (%s): %s — falling back to builtin prompt', cfg_path, e)

        # Fallback built-in prompt
        return f"""You are an expert {target_lang_name} language teacher.

Your job is to take a vocabulary input and generate a complete flashcard.

RULES:
1. The input may be in ANY language. Identify it and translate appropriately.
2. The input may include articles or prepositions (e.g., "de la pomme"). Keep them in the target word.
3. Generate TWO different example sentences that clearly demonstrate usage.
4. Synonyms should be in {target_lang_name}.
5. For nouns: include gender (masculin/féminin) and plural form.
6. For verbs: include key conjugations (présent, passé composé, futur).
7. For adjectives: include masculine/feminine forms.
8. The "extend" field must be written entirely in {explanation_lang_name} and should contain useful notes like common expressions, etymology, or usage tips.
9. The "hint" field must be written entirely in {explanation_lang_name} and should be a short mnemonic or memory aid.

You MUST return ONLY valid JSON with exactly these fields:
{{
    "target_word": "word/phrase in {target_lang_name} (with article/preposition if applicable)",
    "explanation_word": "translation/meaning in {explanation_lang_name}",
    "synonyme": "synonyms in {target_lang_name}, comma separated",
    "conjugaison_genre": "conjugation table or gender info",
    "exemple_target": "example sentence in {target_lang_name}",
    "exemple_explanation": "same sentence translated to {explanation_lang_name}",
    "exemple2_target": "second example sentence in {target_lang_name}",
    "exemple2_explanation": "second sentence translated to {explanation_lang_name}",
    "extend": "additional notes, expressions, usage tips, written in {explanation_lang_name}",
    "hint": "short memory aid or mnemonic, written in {explanation_lang_name}"
}}

Return ONLY the JSON object. No markdown, no code blocks, no extra text."""
 
    def _build_user_prompt(self, input_text, target_lang_name, explanation_lang_name):
        """Build the user prompt for a single vocabulary word."""
        return (
            f'Generate a complete {target_lang_name} flashcard for: "{input_text}"\n'
            f'Target language: {target_lang_name}\n'
            f'Explanation language: {explanation_lang_name}\n'
            f'All explanation-related fields (explanation_word, exemple_explanation, '
            f'exemple2_explanation, extend, hint) MUST be written in {explanation_lang_name} only.'
        )
 
    def translate(self, text, target_lang_code, explanation_lang_code):
        """
        Translate a single vocabulary word and generate all card fields.
 
        Args:
            text: The input vocabulary (any language)
            target_lang_code: Target language code (e.g., 'fr')
            explanation_lang_code: Explanation language code (e.g., 'en')
 
        Returns:
            Dict with all card fields
 
        Raises:
            LLMTranslationError: If translation fails
        """
        from languages.models import Language
 
        try:
            target_lang = Language.objects.get(code=target_lang_code)
            explanation_lang = Language.objects.get(code=explanation_lang_code)
        except Language.DoesNotExist as e:
            raise LLMTranslationError(f'Language not found: {e}')
 
        target_lang_name = target_lang.name
        explanation_lang_name = explanation_lang.name
 
        system_prompt = self._build_system_prompt(target_lang_name, explanation_lang_name)
        user_prompt = self._build_user_prompt(text, target_lang_name, explanation_lang_name)
 
        logger.info(f'Translating "{text}" → {target_lang_name} (explain in {explanation_lang_name})')
 
        # Try providers in preferred order: Gemini -> OpenAI -> Groq
        providers_order = ['gemini', 'openai', 'groq']
        content = None
        last_exception = None

        for prov in providers_order:
            api_key = self._get_api_key_for(prov)
            if not api_key:
                logger.debug('Skipping provider %s — API key not set', prov)
                continue

            logger.info('Attempting LLM generation with provider: %s', prov)

            try:
                if prov == 'openai':
                    # Try official OpenAI client if available, else fall back to REST
                    model = os.getenv('LLM_MODEL', self.PROVIDER_MODELS.get('openai'))
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=api_key, base_url=self.PROVIDER_URLS['openai'])
                        resp = client.chat.completions.create(
                            model=model,
                            messages=[
                                {'role': 'system', 'content': system_prompt},
                                {'role': 'user', 'content': user_prompt},
                            ],
                            temperature=0.3,
                            max_tokens=1000,
                        )
                        content = resp.choices[0].message.content.strip()
                    except Exception:
                        # REST fallback
                        url = f"{self.PROVIDER_URLS['openai']}/chat/completions"
                        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
                        payload = {
                            'model': model,
                            'messages': [
                                {'role': 'system', 'content': system_prompt},
                                {'role': 'user', 'content': user_prompt},
                            ],
                            'temperature': 0.3,
                            'max_tokens': 1000,
                        }
                        r = requests.post(url, headers=headers, json=payload, timeout=(10, 90))
                        if r.status_code == 200:
                            j = r.json()
                            content = j['choices'][0]['message']['content'].strip()
                        else:
                            raise Exception(f'OpenAI request failed: {r.status_code} {r.text}')

                elif prov == 'gemini':
                    model = os.getenv('LLM_MODEL', self.PROVIDER_MODELS.get('gemini'))
                    # Try official client first
                    try:
                        from google.ai import generativelanguage_v1alpha as gl
                        from google.api_core.client_options import ClientOptions

                        client_opts = ClientOptions(api_key=api_key)
                        client = gl.GenerativeServiceClient(client_options=client_opts)
                        part = gl.Part(text=system_prompt + '\n\n' + user_prompt)
                        content_obj = gl.Content(parts=[part])
                        logger.debug('Using official Gemini client to generate content (model=%s)', model)
                        model_name = f"models/{model}" if not model.startswith('models/') else model
                        resp = client.generate_content(model=model_name, contents=[content_obj])
                        
                        # Handle cases where resp.candidates might not be a simple list
                        if hasattr(resp, 'candidates') and resp.candidates:
                            first_candidate = resp.candidates[0]
                            if hasattr(first_candidate, 'content') and hasattr(first_candidate.content, 'parts') and first_candidate.content.parts:
                                content = first_candidate.content.parts[0].text
                            else:
                                content = None
                        else:
                            content = None

                        if not content:
                            # Fallback to recursive search if direct access fails
                            def find_text_proto(obj):
                                if hasattr(obj, 'text') and getattr(obj, 'text'):
                                    return getattr(obj, 'text')
                                if hasattr(obj, 'parts'):
                                    for p in getattr(obj, 'parts'):
                                        t = find_text_proto(p)
                                        if t:
                                            return t
                                if hasattr(obj, 'candidates'):
                                    # Handle both list and non-list candidates
                                    candidates = getattr(obj, 'candidates')
                                    if isinstance(candidates, list):
                                        for c in candidates:
                                            t = find_text_proto(c)
                                            if t:
                                                return t
                                    else: # Assuming it's an object with parts/content
                                        t = find_text_proto(candidates)
                                        if t:
                                            return t
                                return None
                            content = find_text_proto(resp)
                    except Exception as e:
                        logger.debug('Official Gemini client failed or unavailable: %s', e)
                        # REST fallback to Gemini
                        url = f"{self.PROVIDER_URLS['gemini']}/models/{model}:generateContent?key={api_key}"
                        payload = {
                            'contents': [
                                {
                                    'parts': [
                                        {'text': system_prompt + '\n\n' + user_prompt}
                                    ]
                                }
                            ]
                        }
                        headers = {'Content-Type': 'application/json'}
                        r = requests.post(url, headers=headers, json=payload, timeout=(10, 90))
                        if r.status_code == 200:
                            j = r.json()
                            try:
                                content = j['candidates'][0]['content']['parts'][0]['text']
                            except Exception:
                                def find_text(obj):
                                    if isinstance(obj, str):
                                        return obj
                                    if isinstance(obj, dict):
                                        for v in obj.values():
                                            t = find_text(v)
                                            if t:
                                                return t
                                    if isinstance(obj, list):
                                        for item in obj:
                                            t = find_text(item)
                                            if t:
                                                return t
                                    return None
                                content = find_text(j)
                        else:
                            raise Exception(f'Gemini request failed: {r.status_code} {r.text}')

                elif prov == 'groq':
                    model = os.getenv('LLM_MODEL', self.PROVIDER_MODELS.get('groq'))
                    url = f"{self.PROVIDER_URLS['groq']}/chat/completions"
                    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
                    payload = {
                        'model': model,
                        'messages': [
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': user_prompt},
                        ],
                        'temperature': 0.3,
                        'max_tokens': 1000,
                    }
                    r = requests.post(url, headers=headers, json=payload, timeout=(5, 60))
                    if r.status_code == 200:
                        j = r.json()
                        content = j['choices'][0]['message']['content'].strip()
                    else:
                        raise Exception(f'Groq request failed: {r.status_code} {r.text}')

                # If we got content, break out and use it
                if content:
                    logger.debug('Received content from provider %s', prov)
                    break

            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning('Provider %s timed out: %s — falling back to next provider', prov, e)
                continue
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning('Provider %s network error: %s — falling back to next provider', prov, e)
                continue
            except Exception as e:
                last_exception = e
                msg = str(e).lower()
                # If it's a quota/rate-limit style error, try next provider
                if '429' in msg or 'quota' in msg or 'resource_exhausted' in msg or 'too many requests' in msg:
                    logger.warning('Provider %s returned quota/rate error: %s — falling back', prov, e)
                    continue
                # If it's a timeout or connection error, try next provider
                if 'timeout' in msg or 'timed out' in msg or 'connection' in msg:
                    logger.warning('Provider %s connection/timeout error: %s — falling back', prov, e)
                    continue
                # Otherwise surface the error
                logger.exception('Provider %s failed with error: %s', prov, e)
                raise LLMTranslationError(f'LLM provider {prov} failed: {e}')

        if not content:
            raise LLMTranslationError(f'All LLM providers failed: {last_exception}')

        # Clean up response — remove markdown code blocks if present and parse JSON
        try:
            if content.startswith('```'):
                # Remove code fence markers
                lines = content.split('\n')
                lines = [line for line in lines if not line.strip().startswith('```')]
                content = '\n'.join(lines)

            parsed = json.loads(content)

            # Handle both array and object responses from LLM
            # Some prompts ask for JSON array, others for object
            if isinstance(parsed, list):
                if len(parsed) == 0:
                    raise LLMTranslationError('LLM returned empty array')
                result = parsed[0]  # Take first element if array
            elif isinstance(parsed, dict):
                result = parsed
            else:
                raise LLMTranslationError(f'Unexpected JSON type: {type(parsed).__name__}')

            # Map alternative field names to expected field names
            # Build dynamic field mapping based on target/explanation language names
            # The LLM returns language-specific field names (e.g., "Spanish", "Exemple-Spanish")
            # which we map to our internal normalized field names
            field_mapping = {
                # Dynamic mappings based on actual language names
                target_lang_name: 'target_word',
                explanation_lang_name: 'explanation_word',
                f'Exemple-{target_lang_name}': 'exemple_target',
                f'Exemple-{explanation_lang_name}': 'exemple_explanation',
                f'Exemple2-{target_lang_name}': 'exemple2_target',
                f'Exemple2-{explanation_lang_name}': 'exemple2_explanation',
                
                # Legacy support for French
                'French': 'target_word',
                'English': 'explanation_word',
                'Français': 'target_word',
                'Exemple-French': 'exemple_target',
                'Exemple-English': 'exemple_explanation',
                'Exemple-FR': 'exemple_target',
                'Exemple-EN': 'exemple_explanation',
                'Exemple2-French': 'exemple2_target',
                'Exemple2-English': 'exemple2_explanation',
                'Exemple2-FR': 'exemple2_target',
                'Exemple2-EN': 'exemple2_explanation',
                
                # Common field names (language-agnostic)
                'Synonyme': 'synonyme',
                'Synonym': 'synonyme',
                'Synonyms': 'synonyme',
                'Conjugaison/Gender': 'conjugaison_genre',
                'Conjugaison/Féminin ou Masculin': 'conjugaison_genre',  # Legacy
                'Grammar': 'conjugaison_genre',
                'Audio': 'audio',
                'Exemple1-Audio': 'exemple1_audio',
                'Exemple2-Audio': 'exemple2_audio',
                'Extend': 'extend',
                'Hint': 'hint',
            }

            # Create normalized result with expected field names
            normalized_result = {}
            for french_key, english_key in field_mapping.items():
                if french_key in result:
                    normalized_result[english_key] = result[french_key]

            # Also copy any fields that already use expected names
            for key in result:
                if key not in field_mapping:
                    # Convert to lowercase and replace spaces/special chars
                    normalized_key = key.lower().replace(' ', '_').replace('-', '_').replace('/', '_')
                    normalized_result[normalized_key] = result[key]

            # Merge: prefer normalized but keep original if no mapping found
            for key, value in result.items():
                snake_key = key.lower().replace(' ', '_').replace('-', '_').replace('/', '_')
                if snake_key not in normalized_result:
                    normalized_result[snake_key] = value

            result = normalized_result

            # Validate required fields exist
            required_fields = [
                'target_word', 'explanation_word', 'synonyme',
                'conjugaison_genre', 'exemple_target', 'exemple_explanation',
                'exemple2_target', 'exemple2_explanation', 'extend', 'hint'
            ]

            for field in required_fields:
                if field not in result:
                    result[field] = ''
                    logger.warning(f'Missing field "{field}" in LLM response for "{text}"')

            # Fallback: if the model failed to provide a target word,
            # at least use the original input so the note is never empty.
            if not str(result.get('target_word', '')).strip():
                result['target_word'] = text

            logger.info(f'Successfully translated "{text}" → "{result.get("target_word", text)}"')
            return result

        except json.JSONDecodeError as e:
            raise LLMTranslationError(
                f'Failed to parse LLM response as JSON: {e}\nRaw response: {content}'
            )
        except Exception as e:
            raise LLMTranslationError(f'LLM API call failed: {e}')
 
    def translate_batch(self, texts, target_lang_code, explanation_lang_code):
        """
        Translate multiple vocabulary words.
 
        Args:
            texts: List of input vocabulary strings
            target_lang_code: Target language code
            explanation_lang_code: Explanation language code
 
        Returns:
            List of dicts with card fields (or error dicts)
        """
        results = []
        for text in texts:
            try:
                result = self.translate(text, target_lang_code, explanation_lang_code)
                result['_status'] = 'success'
                results.append(result)
            except LLMTranslationError as e:
                logger.error(f'Translation failed for "{text}": {e}')
                results.append({
                    '_status': 'error',
                    '_error': str(e),
                    'target_word': text,
                    'explanation_word': '',
                    'synonyme': '',
                    'conjugaison_genre': '',
                    'exemple_target': '',
                    'exemple_explanation': '',
                    'exemple2_target': '',
                    'exemple2_explanation': '',
                    'extend': '',
                    'hint': '',
                })
        return results
