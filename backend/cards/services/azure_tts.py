import os
import uuid
import logging
import json
import hashlib
import asyncio
from pathlib import Path
from django.conf import settings
 
logger = logging.getLogger(__name__)
 
 
class AzureTTSError(Exception):
    """Raised when Azure TTS fails."""
    pass
 
 
class AzureTTSService:
    """
    Generates speech audio files using Azure Cognitive Services TTS.
 
    Requires:
        - AZURE_SPEECH_KEY in .env
        - AZURE_SPEECH_REGION in .env
        - azure-cognitiveservices-speech package installed
    """
 
    def __init__(self):
        # Support multiple environment variable names for backward compatibility.
        # Prefer explicit AZURE_SPEECH_* vars but fall back to AZURE_API_KEY / AZURE_REGION.
        self.speech_key = os.getenv('AZURE_SPEECH_KEY') or os.getenv('AZURE_API_KEY')
        self.speech_region = os.getenv('AZURE_SPEECH_REGION') or os.getenv('AZURE_REGION')

        if not self.speech_key or not self.speech_region:
            raise AzureTTSError(
                'Azure Speech credentials not configured. '
                'Set AZURE_SPEECH_KEY (or AZURE_API_KEY) and AZURE_SPEECH_REGION (or AZURE_REGION) in .env'
            )
        logger.debug('AzureTTSService initialized using speech_key from environment; region=%s', self.speech_region)
        # TTS prosody rate (e.g. '1.3' for 1.3x speed). Can be set via
        # Django settings.AZURE_TTS_RATE or env AZURE_TTS_RATE / AZURE_RATE.
        self.rate = getattr(settings, 'AZURE_TTS_RATE', None) or os.getenv('AZURE_TTS_RATE') or os.getenv('AZURE_RATE') or '1.3'
 
    def _get_output_dir(self, subfolder):
        """Create and return the output directory path."""
        output_dir = Path(settings.MEDIA_ROOT) / 'tts' / subfolder
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
 
    def synthesize(self, text, voice, locale, output_prefix='audio', subfolder='words'):
        """
        Synthesize speech from text and save as an audio file.
 
        Args:
            text: Text to synthesize
            voice: Azure TTS voice name (e.g., 'fr-FR-DeniseNeural')
            locale: Language locale (e.g., 'fr-FR')
            output_prefix: Prefix for the output filename
            subfolder: Subfolder under media/tts/ ('words' or 'examples')
 
        Returns:
            Relative path to the audio file (relative to MEDIA_ROOT)
 
        Raises:
            AzureTTSError: If synthesis fails
        """
        if not text or not text.strip():
            logger.warning('Empty text passed to TTS, skipping.')
            return None

        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        filename = f'{output_prefix}_{unique_id}.mp3'
        output_dir = self._get_output_dir(subfolder)
        output_path = output_dir / filename

        logger.info(f'Synthesizing TTS: "{text[:50]}..." → {filename}')

        # Try native SDK first; if not installed or if SDK path fails, fall back to REST API
        try:
            try:
                import azure.cognitiveservices.speech as speechsdk
            except Exception as imp_exc:
                # Could be ImportError or partial install issue
                logger.debug('azure-cognitiveservices-speech import failed: %s; will use REST fallback', imp_exc)
                return self._synthesize_rest(text, voice, locale, output_path, filename, subfolder)

            # Use SDK, but guard against runtime failures and fall back to REST on unexpected exceptions
            try:
                # Configure Azure Speech
                speech_config = speechsdk.SpeechConfig(
                    subscription=self.speech_key,
                    region=self.speech_region,
                )
                speech_config.speech_synthesis_voice_name = voice
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
                )

                # Configure output to file
                audio_config = speechsdk.audio.AudioOutputConfig(
                    filename=str(output_path)
                )

                # Create synthesizer and generate audio
                synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=speech_config,
                    audio_config=audio_config,
                )

                # Use SSML prosody to control speaking rate so SDK and REST match.
                ssml = f"""
                <speak version='1.0' xml:lang='{locale}'>
                    <voice xml:lang='{locale}' name='{voice}'>
                        <prosody rate=\"{self.rate}\">{text}</prosody>
                    </voice>
                </speak>
                """

                result = synthesizer.speak_ssml_async(ssml).get()

                # Check result
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    relative_path = f'tts/{subfolder}/{filename}'
                    logger.info(f'TTS successful (SDK): {relative_path}')
                    return relative_path

                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    error_msg = f'TTS canceled: {cancellation.reason}'

                    if cancellation.reason == speechsdk.CancellationReason.Error:
                        error_msg += f' | Error: {cancellation.error_details}'

                    # If SDK reports a cancellation error, surface it (SDK likely available but failed)
                    raise AzureTTSError(error_msg)

                else:
                    # Unexpected SDK result — fall back to REST
                    logger.warning('Unexpected TTS SDK result (%s); falling back to REST', getattr(result, 'reason', repr(result)))
                    return self._synthesize_rest(text, voice, locale, output_path, filename, subfolder)

            except AzureTTSError:
                # SDK returned an AzureTTSError we should propagate
                raise
            except Exception as sdk_exc:
                # Any SDK runtime failure — log and fall back to REST
                logger.warning('TTS SDK path failed at runtime: %s; falling back to REST', sdk_exc)
                return self._synthesize_rest(text, voice, locale, output_path, filename, subfolder)

        except AzureTTSError:
            raise
        except Exception as e:
            # As a final safety net, try REST before giving up
            logger.exception('Unexpected error in TTS SDK flow: %s — attempting REST fallback', e)
            return self._synthesize_rest(text, voice, locale, output_path, filename, subfolder)

    def _synthesize_rest(self, text, voice, locale, output_path, filename, subfolder):
        """Perform REST-based TTS and write output file. Raises AzureTTSError on failure."""
        logger.debug('Using REST fallback for TTS')

        ssml = f"""
        <speak version='1.0' xml:lang='{locale}'>
            <voice xml:lang='{locale}' name='{voice}'>
                <prosody rate=\"{self.rate}\">{text}</prosody>
            </voice>
        </speak>
        """

        url = f'https://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/v1'
        headers = {
            'Ocp-Apim-Subscription-Key': self.speech_key,
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'audio-16khz-128kbitrate-mono-mp3'
        }

        session = __import__('requests').Session()
        session.trust_env = False

        # retry for transient errors with exponential backoff + jitter
        max_retries = getattr(settings, 'AZURE_TTS_MAX_RETRIES', 4)
        base_backoff = getattr(settings, 'AZURE_TTS_BACKOFF_BASE', 1.0)
        retryable_statuses = {429, 500, 502, 503, 504}

        for attempt in range(1, max_retries + 1):
            try:
                resp = session.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=(5, 60))
            except Exception as e:
                resp = None
                logger.warning('TTS REST request exception on attempt %s/%s: %s', attempt, max_retries, e)

            status = resp.status_code if resp is not None else None
            # success
            if resp is not None and resp.status_code == 200:
                try:
                    with open(output_path, 'wb') as fh:
                        fh.write(resp.content)
                    relative_path = f'tts/{subfolder}/{filename}'
                    logger.info('TTS successful (REST): %s', relative_path)
                    return relative_path
                except Exception as e:
                    logger.exception('Failed writing TTS file to disk: %s', e)
                    # treat as retryable until final attempt

            # determine if should retry
            if status in retryable_statuses or resp is None:
                if attempt == max_retries:
                    msg = resp.text if resp is not None else 'no response'
                    raise AzureTTSError(f'TTS REST Error after {attempt} attempts: {status} - {msg}')
                # exponential backoff with jitter
                backoff = base_backoff * (2 ** (attempt - 1))
                import random
                jitter = random.uniform(0, 0.5 * backoff)
                wait = backoff + jitter
                logger.warning('TTS REST retry %s/%s after %.1fs (status=%s)', attempt, max_retries, wait, status)
                import time
                time.sleep(wait)
                continue

            # non-retryable failure
            if resp is not None:
                raise AzureTTSError(f'TTS REST failed: {resp.status_code} {resp.text}')
            else:
                raise AzureTTSError('TTS REST failed with unknown error')
 
    def synthesize_word(self, text, voice, locale, card_id):
        """
        Convenience method for synthesizing a vocabulary word.
 
        Args:
            text: The word to speak
            voice: Azure TTS voice name
            locale: Language locale
            card_id: Card ID (used in filename)
 
        Returns:
            Relative path to audio file
        """
        return self.synthesize(
            text=text,
            voice=voice,
            locale=locale,
            output_prefix=f'word_{card_id}',
            subfolder='words',
        )
 
    def synthesize_example(self, text, voice, locale, card_id, example_number=1):
        """
        Convenience method for synthesizing an example sentence.
 
        Args:
            text: The example sentence
            voice: Azure TTS voice name
            locale: Language locale
            card_id: Card ID (used in filename)
            example_number: 1 or 2
 
        Returns:
            Relative path to audio file
        """
        return self.synthesize(
            text=text,
            voice=voice,
            locale=locale,
            output_prefix=f'ex{example_number}_{card_id}',
            subfolder='examples',
        )
    def synthesize_batch(self, items, voice, locale, concurrency=6):
        """
        Batch-synthesize multiple texts concurrently using Azure REST TTS.

        Args:
            items: dict mapping arbitrary key -> text to synthesize
            voice: Azure TTS voice name
            locale: language locale
            concurrency: max concurrent requests

        Returns:
            dict mapping original key -> relative filename (or None if failed)

        Notes:
            - Uses a local JSON cache at MEDIA_ROOT/tts/audio_cache.json to avoid
              re-synthesizing identical text+voice combos.
            - Writes files into MEDIA_ROOT/tts/examples or /words depending on
              caller intent; filenames use SHA1 hashes for deduplication.
        """
        # local imports to avoid hard dependency at module import time
        try:
            import aiohttp
        except Exception:
            aiohttp = None

        if not items:
            return {}

        cache_path = Path(settings.MEDIA_ROOT) / 'tts' / 'audio_cache.json'
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if cache_path.exists():
                audio_cache = json.loads(cache_path.read_text(encoding='utf-8'))
            else:
                audio_cache = {}
        except Exception:
            audio_cache = {}

        # Normalize and build jobs for missing keys
        jobs = {}  # hash -> (norm_text, filename, subfolder, original_keys)
        timestamp = uuid.uuid4().hex[:8]
        for key, text in items.items():
            if not text or not str(text).strip():
                continue
            norm = ' '.join(str(text).split())
            h = hashlib.sha1((norm + '|' + voice).encode('utf-8')).hexdigest()
            if h in audio_cache:
                # cache stores mapping hash -> filename
                # also attach original key mapping later
                continue
            subfolder = 'words' if len(norm) <= 6 else 'examples'
            filename = f'az_{h}_{timestamp}.mp3'
            jobs[h] = (norm, filename, subfolder)

        # If nothing to do, return mapping from cache
        if not jobs:
            result = {}
            for key, text in items.items():
                norm = ' '.join(str(text).split())
                h = hashlib.sha1((norm + '|' + voice).encode('utf-8')).hexdigest()
                result[key] = audio_cache.get(h)
            return result

        async def _fetch_and_store(norm_text, filename, subfolder, sem):
            ssml = f"""
            <speak version='1.0' xml:lang='{locale}'>
                <voice xml:lang='{locale}' name='{voice}'>
                    <prosody rate=\"{self.rate}\">{norm_text}</prosody>
                </voice>
            </speak>
            """
            url = f'https://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/v1'
            headers = {
                'Ocp-Apim-Subscription-Key': self.speech_key,
                'Content-Type': 'application/ssml+xml',
                'X-Microsoft-OutputFormat': 'audio-16khz-128kbitrate-mono-mp3'
            }
            out_dir = Path(settings.MEDIA_ROOT) / 'tts' / subfolder
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / filename

            async with sem:
                try:
                    if aiohttp is None:
                        logger.warning('aiohttp not available; cannot run batch TTS')
                        return None
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=60) as resp:
                            if resp.status == 200:
                                content = await resp.read()
                                out_path.write_bytes(content)
                                return filename
                            else:
                                text_resp = await resp.text()
                                logger.warning('Batch TTS failed status=%s for %s: %s', resp.status, filename, text_resp)
                                return None
                except Exception as e:
                    logger.warning('Batch TTS exception for %s: %s', filename, e)
                    return None

        async def _run_all():
            sem = asyncio.Semaphore(concurrency)
            tasks = []
            for h, (norm, filename, subfolder) in jobs.items():
                tasks.append(asyncio.create_task(_fetch_and_store(norm, filename, subfolder, sem)))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            i = 0
            for h, (norm, filename, subfolder) in jobs.items():
                res = results[i]
                if isinstance(res, Exception) or res is None:
                    # failed
                    pass
                else:
                    audio_cache[h] = res
                i += 1

        # run async tasks
        try:
            asyncio.run(_run_all())
        except Exception as e:
            logger.warning('synthesize_batch encountered exception: %s', e)

        # persist cache
        try:
            cache_path.write_text(json.dumps(audio_cache, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            logger.debug('Failed to write audio cache file')

        # build final mapping for caller
        result = {}
        for key, text in items.items():
            norm = ' '.join(str(text).split())
            h = hashlib.sha1((norm + '|' + voice).encode('utf-8')).hexdigest()
            result[key] = audio_cache.get(h)
        return result
