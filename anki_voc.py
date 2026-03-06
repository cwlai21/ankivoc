import os
import re
from dotenv import dotenv_values
from openai import OpenAI
from groq import Groq
from datetime import datetime
import requests
import json
import urllib.request
import base64
import time
import random
import hashlib
import asyncio
import aiohttp
from pathlib import Path
import argparse


ENV_FILE = str(Path(__file__).parent.joinpath('backend', '.env'))


def llm_generate_anki_note(model: str, system_instructions: str, word_list: str):
    config = dotenv_values(ENV_FILE)
    today = datetime.today().strftime("%Y%m%d")
    filename = f"anki_voc_{today}.csv"
    full_prompt = f"{system_instructions}\n\nWORD_LIST TO PROCESS:\n{word_list}"

    if model == "gemini":
        api_key = config.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("No GOOGLE_API_KEY found in .env for Gemini. Set GOOGLE_API_KEY in .env")

        # Use a known-stable Gemini model id directly to avoid extra list calls
        mid = "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1/models/{mid}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": full_prompt}]}]}
        session = requests.Session()
        # Don't inherit system proxy settings (can cause hanging if proxy unreachable)
        session.trust_env = False
        try:
            # timeout=(connect_timeout, read_timeout)
            resp = session.post(url, headers=headers, json=data, timeout=(10, 60))
        except requests.exceptions.ConnectTimeout:
            raise RuntimeError("Gemini generateContent connection timed out. Check network/firewall or proxy settings.")
        except requests.exceptions.ReadTimeout:
            raise RuntimeError("Gemini generateContent read timed out. The service may be slow; try increasing read timeout.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Gemini generateContent request failed (network error): {e}")

        if resp.status_code == 200:
            j = resp.json()
            try:
                result = j["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                raise RuntimeError(f"Unexpected Gemini response structure: {j}")
        else:
            raise RuntimeError(
                f"Gemini generateContent failed: {resp.status_code} {resp.text}. "
                "Verify API key, model access and Quota in Google Cloud Console."
            )
    elif model == "groq":
        api_key = config.get("GROQ_API_KEY")
        if not api_key: raise ValueError("No GROQ_API_KEY found.")
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": full_prompt}],
            model="llama-3.3-70b-versatile",
        )
        result = response.choices[0].message.content
    elif model == "openai":
        api_key = config.get("OPENAI_API_KEY")
        if not api_key: raise ValueError("No OPENAI_API_KEY found.")
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": full_prompt}],
            model="gpt-4o",
        )
        result = response.choices[0].message.content
    else:
        raise ValueError(f"Unknown model: {model}")

    # --- Attempt JSON parsing first (preferred, per updated system_prompt.md) ---
    final_output = None
    try:
        # Clean possible markdown fences or surrounding text before JSON parse
        clean_result = re.sub(r'```(?:json|text)?\n?', '', result or '')
        clean_result = clean_result.replace('```', '').strip()
        # Attempt to extract JSON array substring if the model wrapped it in text
        json_start = clean_result.find('[')
        json_end = clean_result.rfind(']')
        parsed = None
        if json_start != -1 and json_end != -1 and json_end > json_start:
            candidate = clean_result[json_start:json_end+1]
            try:
                parsed = json.loads(candidate)
            except Exception:
                parsed = None
        if parsed is None:
            # Fallback: try parsing the whole cleaned result
            try:
                parsed = json.loads(clean_result)
            except Exception:
                parsed = None
        if isinstance(parsed, list):
            keys = [
                "Français", "English", "Synonyme", "Conjugaison/Féminin ou Masculin",
                "Audio", "Exemple-FR", "Exemple-EN", "Exemple1-Audio",
                "Exemple2-FR", "Exemple2-EN", "Exemple2-Audio", "Extend", "Hint"
            ]
            # Normalization rules requested by user:
            # - field 0 (Français) == field 4 (Audio)
            # - field 5 (Exemple-FR) == field 7 (Exemple1-Audio)
            # - field 8 (Exemple2-FR) == field 10 (Exemple2-Audio)
            rows = []
            for item in parsed:
                if isinstance(item, dict):
                    # enforce equality constraints by copying text fields into the corresponding audio fields
                    fr = str(item.get("Français", "") or "").strip()
                    ex1 = str(item.get("Exemple-FR", "") or "").strip()
                    ex2 = str(item.get("Exemple2-FR", "") or "").strip()
                    # copy textual content into the audio fields so downstream TTS uses the same text
                    item["Audio"] = fr
                    item["Exemple1-Audio"] = ex1
                    item["Exemple2-Audio"] = ex2

                row_fields = []
                for k in keys:
                    v = item.get(k, "") if isinstance(item, dict) else ""
                    if not isinstance(v, str):
                        v = str(v)
                    # safety: remove newlines and replace any stray semicolons
                    v = v.replace('\n', ' ').replace('\r', ' ').replace(';', ',').strip()
                    row_fields.append(v)
                rows.append(';'.join(row_fields))
            final_output = '\n'.join(rows)
    except Exception:
        final_output = None

    # --- FALLBACK: original cleaning logic for non-JSON outputs ---
    if final_output is None:
        clean_csv = re.sub(r'```(?:csv|text)?\n?', '', result)
        clean_csv = clean_csv.replace('```', '').strip()
        processed_lines = []
        for line in clean_csv.split('\n'):
            line = line.strip()
            if not line:  # Skip empty lines
                continue
            if line.count(';') > 12:
                parts = line.split(';')
                main_fields = parts[:12]
                extra_fields = parts[12:]
                line = ";".join(main_fields) + ";" + ", ".join(extra_fields).replace(';', ':')
            processed_lines.append(line)
        final_output = "\n".join(processed_lines)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_output)
        print(f"✅ CSV content written to {filename}")
    try:
        add_notes_to_anki(filename)
    except Exception as e:
        print(f"❌ Error when adding notes to Anki: {e}")
    print(f"✅ CSV saved as {filename}")

def generate_azure_audio(text, filename):
    """Generates audio via Azure API and stores it in Anki."""
    if not text or len(text.strip()) == 0:
        return ""

    # Read config from .env each time to ensure latest values
    config = dotenv_values(".env")
    AZURE_KEY = config.get("AZURE_API_KEY", "YOUR_AZURE_API_KEY")
    AZURE_REGION = config.get("AZURE_REGION", "eastus")
    AZURE_VOICE = config.get("AZURE_VOICE_NAME", "fr-FR-DeniseNeural")
    url = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3"
    }
    ssml = f"""
    <speak version='1.0' xml:lang='fr-FR'>
        <voice xml:lang='fr-FR' name='{AZURE_VOICE}'>
            <prosody rate="1.3">
                {text}
            </prosody>
        </voice>
    </speak>
    """

    # Retry logic for transient errors (429, 5xx)
    max_retries = 4
    base_backoff = 1.0
    retryable_statuses = {429, 500, 502, 503, 504}

    session = requests.Session()
    session.trust_env = False
    for attempt in range(1, max_retries + 1):
        try:
            response = session.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=(5, 30))
        except requests.exceptions.ConnectTimeout:
            print(f"⚠️ Azure TTS connect timeout (attempt {attempt}/{max_retries}) for {filename}")
            response = None
        except requests.exceptions.ReadTimeout:
            print(f"⚠️ Azure TTS read timeout (attempt {attempt}/{max_retries}) for {filename}")
            response = None
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Azure TTS request exception (attempt {attempt}/{max_retries}) for {filename}: {e}")
            response = None

        if response is not None and response.status_code == 200:
            audio_data = base64.b64encode(response.content).decode('utf-8')
            anki_request("storeMediaFile", filename=filename, data=audio_data)
            return f"[sound:{filename}]"

        # If we received a response and it's retryable, wait and retry
        status = response.status_code if response is not None else None
        if status in retryable_statuses or response is None:
            if attempt == max_retries:
                if response is not None:
                    print(f"❌ Azure TTS Error after {attempt} attempts: {status} - {response.text} (filename: {filename})")
                else:
                    print(f"❌ Azure TTS failed after {attempt} attempts for {filename}")
                print("🔎 Check your .env: AZURE_API_KEY, AZURE_REGION, AZURE_VOICE_NAME")
                return ""
            # exponential backoff with jitter
            backoff = base_backoff * (2 ** (attempt - 1))
            jitter = random.uniform(0, 0.5 * backoff)
            wait = backoff + jitter
            print(f"⏳ Azure TTS retry {attempt}/{max_retries} for {filename} after {wait:.1f}s (status={status})")
            time.sleep(wait)
            continue

        # Non-retryable status
        if response is not None:
            print(f"❌ Azure TTS Error: {response.status_code} - {response.text} (filename: {filename})")
        else:
            print(f"❌ Azure TTS unknown error for {filename}")
        print("🔎 Check your .env: AZURE_API_KEY, AZURE_REGION, AZURE_VOICE_NAME")
        return ""
    return ""

def anki_request(action: str, **params):
    """Helper to send a request to AnkiConnect and return the result."""
    payload = {"action": action, "version": 6, "params": params}
    try:
        req = urllib.request.Request(
            'http://localhost:8765',
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get('result')
    except Exception as e:
        print(f"❌ AnkiConnect request failed ({action}): {e}")
        return None


def add_notes_to_anki(csv_filename, target_deck="Français::Vocabulary", model_name="Français-(R/L)"):
    """Synchronous wrapper that runs the asyncio implementation."""
    try:
        asyncio.run(async_add_notes_to_anki(csv_filename, target_deck, model_name))
    except Exception as e:
        print(f"❌ Error in async add_notes_to_anki: {e}")


async def _fetch_and_store_tts(session: aiohttp.ClientSession, text: str, filename: str, az_key: str, az_region: str, az_voice: str, semaphore: asyncio.Semaphore):
    if not text or not text.strip():
        return None
    ssml = f"""
    <speak version='1.0' xml:lang='fr-FR'>
        <voice xml:lang='fr-FR' name='{az_voice}'>
            <prosody rate="1.3">{text}</prosody>
        </voice>
    </speak>
    """
    url = f"https://{az_region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": az_key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3"
    }
    # Limit concurrency via semaphore
    async with semaphore:
        try:
            async with session.post(url, data=ssml.encode('utf-8'), headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    audio_b64 = base64.b64encode(content).decode('utf-8')
                    # storeMediaFile is synchronous; run in thread
                    await asyncio.to_thread(anki_request, "storeMediaFile", filename=filename, data=audio_b64)
                    return filename
                else:
                    text_resp = await resp.text()
                    print(f"❌ Azure TTS failed status={resp.status} for {filename}: {text_resp}")
                    return None
        except Exception as e:
            print(f"⚠️ Azure async TTS exception for {filename}: {e}")
            return None


async def async_add_notes_to_anki(csv_filename, target_deck="Vocabulaire", model_name="Français-(R/L)"):
    anki_request("createDeck", deck=target_deck)
    # Load CSV
    try:
        with open(csv_filename, 'r', encoding='utf-8') as f:
            lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    except Exception as e:
        print(f"❌ Could not read CSV file {csv_filename}: {e}")
        return

    # prepare Azure settings
    cfg = dotenv_values(ENV_FILE)
    AZURE_KEY = cfg.get('AZURE_API_KEY')
    AZURE_REGION = cfg.get('AZURE_REGION', 'eastus')
    AZURE_VOICE = cfg.get('AZURE_VOICE_NAME', 'fr-FR-DeniseNeural')
    if not AZURE_KEY:
        print("❌ No AZURE_API_KEY in .env; cannot generate audio.")

    # Disk cache for audio key -> filename
    cache_path = Path("audio_cache.json")
    try:
        if cache_path.exists():
            audio_cache = json.loads(cache_path.read_text(encoding='utf-8'))
        else:
            audio_cache = {}
    except Exception:
        audio_cache = {}

    # gather unique TTS jobs
    timestamp = datetime.now().strftime("%f")
    tts_jobs = {}  # key -> (text, filename)
    rows = []
    for line in lines:
        fields = line.split(';')
        if len(fields) < 13:
            continue
        rows.append(fields)
        for idx, suffix in ((4, '1'), (7, '2'), (10, '3')):
            text = fields[idx].strip() if idx < len(fields) else ''
            if not text:
                continue
            norm = ' '.join(text.split())
            voice = AZURE_VOICE
            key = hashlib.sha1((norm + '|' + voice).encode('utf-8')).hexdigest()
            if key in audio_cache:
                continue
            if key not in tts_jobs:
                filename = f"az_{key}_{timestamp}_{suffix}.mp3"
                tts_jobs[key] = (norm, filename)

    # perform async TTS for all jobs
    semaphore = asyncio.Semaphore(6)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for key, (text, filename) in tts_jobs.items():
            tasks.append(asyncio.create_task(_fetch_and_store_tts(session, text, filename, AZURE_KEY, AZURE_REGION, AZURE_VOICE, semaphore)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            # update cache with successful filenames
            for key, (_, filename) in tts_jobs.items():
                # if file was created successfully, ensure mapping exists
                if filename and filename not in audio_cache.values():
                    # verify by checking Anki media exists? We'll assume success if stored via AnkiConnect returned None or OK
                    audio_cache[key] = filename
            try:
                cache_path.write_text(json.dumps(audio_cache, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception:
                pass

    # build notes
    notes = []
    for fields in rows:
        word = fields[0]
        # Check if note already exists in deck
        existing_ids = anki_request("findNotes", query=f'deck:"{target_deck}" "Français:{word}"')
        if existing_ids:
            print(f"⏭️ Skipping '{fields[0]}' - already exists in deck.")
            continue

        # This helper now just returns the filename, not the full tag
        def get_audio_filename(text):
            norm = ' '.join(text.split())
            key = hashlib.sha1((norm + '|' + AZURE_VOICE).encode('utf-8')).hexdigest()
            return audio_cache.get(key)

        audio_payload = []
        
        # Word Audio
        word_audio_text = fields[4] if len(fields) > 4 else ''
        word_audio_filename = get_audio_filename(word_audio_text)
        if word_audio_filename:
            audio_payload.append({
                "filename": word_audio_filename,
                "fields": ["Audio"]
            })

        # Example 1 Audio
        ex1_audio_text = fields[7] if len(fields) > 7 else ''
        ex1_audio_filename = get_audio_filename(ex1_audio_text)
        if ex1_audio_filename:
            audio_payload.append({
                "filename": ex1_audio_filename,
                "fields": ["Exemple1-Audio"]
            })

        # Example 2 Audio
        ex2_audio_text = fields[10] if len(fields) > 10 else ''
        ex2_audio_filename = get_audio_filename(ex2_audio_text)
        if ex2_audio_filename:
            audio_payload.append({
                "filename": ex2_audio_filename,
                "fields": ["Exemple2-Audio"]
            })

        note_data = {
            "deckName": target_deck,
            "modelName": model_name,
            "fields": {
                "Français": fields[0],
                "English": fields[1] if len(fields) > 1 else '',
                "Synonyme": fields[2] if len(fields) > 2 else '',
                "Conjugaison/Féminin ou Masculin": fields[3] if len(fields) > 3 else '',
                "Audio": "",  # Keep field empty, AnkiConnect will fill it
                "Exemple-FR": fields[5] if len(fields) > 5 else '',
                "Exemple-EN": fields[6] if len(fields) > 6 else '',
                "Exemple1-Audio": "", # Keep field empty
                "Exemple2-FR": fields[8] if len(fields) > 8 else '',
                "Exemple2-EN": fields[9] if len(fields) > 9 else '',
                "Exemple2-Audio": "", # Keep field empty
                "Extend": fields[11] if len(fields) > 11 else '',
                "Hint": fields[12] if len(fields) > 12 else ''
            },
        }

        # Add the audio payload ONLY if there are audio files to add
        if audio_payload:
            # We don't need to send base64 data again if files are already in Anki's media collection
            note_data["audio"] = audio_payload

        notes.append(note_data)

    if notes:
        anki_request("addNotes", notes=notes)
        print("✅ All notes with Azure audio added successfully!")


def load_system_instructions():
    """Load the system prompt used for the standalone anki_voc pipeline.

    For this CLI tool we want a stable, French-specific JSON schema
    (keys like "Français", "Exemple-FR", etc.), which is defined in the
    repo-root system_prompt.md. The Django backend uses its own
    backend/config/system_prompt.md with more generic, language-parameterised
    keys; that template is not suitable for this CSV generator.

    Resolution order:
      1) Prefer the root system_prompt.md (CLI-specific schema).
      2) If missing, fall back to backend/config/system_prompt.md.
    """
    # 1) Prefer repo-root system_prompt.md
    root_prompt = Path(__file__).parent.joinpath('system_prompt.md')
    if root_prompt.exists():
        with open(root_prompt, "r", encoding="utf-8") as f:
            return f.read()

    # 2) Fallback: backend/config/system_prompt.md (may use slightly different keys)
    backend_prompt = Path(__file__).parent.joinpath('backend', 'config', 'system_prompt.md')
    if backend_prompt.exists():
        with open(backend_prompt, "r", encoding="utf-8") as f:
            return f.read()

    # If neither file exists, raise so caller can handle/exit explicitly
    raise FileNotFoundError("system_prompt.md not found. Please create it at repo root or under backend/config/.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Anki vocabulary CSV and optionally add notes via AnkiConnect.")
    parser.add_argument('--words', '-w', help='Inline words (multi-line string) to process')
    parser.add_argument('--csv', '-c', help='Write only CSV to given filename (no Anki add)')
    parser.add_argument('--model', '-m', default='gemini', choices=['gemini', 'groq', 'openai'], help='LLM provider')
    parser.add_argument('--no-anki', action='store_true', help='Do not call AnkiConnect to add notes')
    args = parser.parse_args()

    # Clean up old CSV files before generating new ones
    import glob
    old_csvs = glob.glob("anki_voc_*.csv")
    for old_csv in old_csvs:
        try:
            os.remove(old_csv)
            print(f"🗑️ Removed old CSV: {old_csv}")
        except Exception:
            pass

    try:
        system_instructions = load_system_instructions()
    except Exception as e:
        print(f"❌ Could not load system prompt: {e}")
        raise

    input_words = args.words or "tacite"
    model_choice = args.model
    print(f"🤖 Using model: {model_choice}")

    # Generate CSV (and optionally add to Anki)
    # If user requested only CSV filename, write CSV and exit
    today = datetime.today().strftime("%Y%m%d")
    out_csv = args.csv or f"anki_voc_{today}.csv"

    # Call LLM to generate CSV and add notes unless --no-anki or --csv is specified
    llm_generate_anki_note(model_choice, system_instructions, input_words)
    if args.no_anki:
        print("ℹ️ Skipping AnkiConnect as requested (--no-anki).")