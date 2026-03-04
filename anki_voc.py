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


def llm_generate_anki_note(model: str, system_instructions: str, word_list: str):
    config = dotenv_values(".env")
    today = datetime.today().strftime("%Y%m%d")
    filename = f"anki_voc_{today}.csv"
    full_prompt = f"{system_instructions}\n\nWORD_LIST TO PROCESS:\n{word_list}"

    if model == "gemini":
        api_key = config.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("No GOOGLE_API_KEY found in .env for Gemini.")
        list_url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
        list_resp = requests.get(list_url)
        if list_resp.status_code != 200:
            raise RuntimeError(f"Failed to list Gemini models: {list_resp.status_code} {list_resp.text}")
        models = list_resp.json().get("models", [])
        candidates = [m.get("name").split("/")[-1] for m in models if "gemini" in m.get("name", "").lower()]
        if not candidates:
            raise RuntimeError("No Gemini models found.")
        for mid in candidates:
            url = f"https://generativelanguage.googleapis.com/v1/models/{mid}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            data = {"contents": [{"parts": [{"text": full_prompt}]}]}
            resp = requests.post(url, headers=headers, json=data)
            if resp.status_code == 200:
                result = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                break
            else:
                last_err = (mid, resp.status_code, resp.text)
        if 'result' not in locals():
            raise RuntimeError(f"Gemini failed. Last error: {last_err}")
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

    # --- CLEANING LOGIC ---
    clean_csv = re.sub(r'```(?:csv|text)?\n?', '', result)
    clean_csv = clean_csv.replace('```', '').strip()
    processed_lines = []
    for line in clean_csv.split('\n'):
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
    if not text or len(text.strip()) == 0: return ""
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
    try:
        response = requests.post(url, headers=headers, data=ssml.encode('utf-8'))
    except Exception as e:
        print(f"❌ Azure TTS request failed for {filename}: {e}")
        return ""
    if response.status_code == 200:
        audio_data = base64.b64encode(response.content).decode('utf-8')
        anki_request("storeMediaFile", filename=filename, data=audio_data)
        # print(f"🔊 Azure TTS audio generated for {filename}")
        return f"[sound:{filename}]"
    else:
        print(f"❌ Azure TTS Error: {response.status_code} - {response.text} (filename: {filename})")
        print(f"🔎 Check your .env: AZURE_API_KEY, AZURE_REGION, AZURE_VOICE_NAME")
        return ""
    # 1. Strip Markdown code blocks
    clean_csv = re.sub(r'```(?:csv|text)?\n?', '', result)
    clean_csv = clean_csv.replace('```', '').strip()

    # 2. FINAL SAFETY NET: If the LLM produces a line with more than 12 semicolons,
    # it means it used a semicolon inside a sentence. We convert internal semicolons
    # to colons while preserving the 12 column delimiters.
    processed_lines = []
    for line in clean_csv.split('\n'):
        if line.count(';') > 12:
            # Split by semicolon, keep the first 12, join the rest with a colon
            parts = line.split(';')
            main_fields = parts[:12]
            extra_fields = parts[12:]
            # Re-join the overflow into the final field (Hint)
            line = ";".join(main_fields) + ";" + ", ".join(extra_fields).replace(';', ':')
        processed_lines.append(line)
    
    final_output = "\n".join(processed_lines)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_output)
        print(f"✅ CSV content written to {filename}")

    # After writing CSV, attempt to add notes to Anki via AnkiConnect
    try:
        add_notes_to_anki(filename)
    except NameError:
        # Function not defined yet in some contexts; ignore
        pass
    except Exception as e:
        print(f"❌ Error when adding notes to Anki: {e}")

    print(f"✅ CSV saved as {filename}")
    # return filename




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


def add_notes_to_anki(csv_filename, target_deck="Vocabulaire", model_name="Français-(R/L)"):
    anki_request("createDeck", deck=target_deck)
    notes = []
    try:
        with open(csv_filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ Could not read CSV file {csv_filename}: {e}")
        return

    for line in lines:
        fields = line.strip().split(';')
        if len(fields) < 13:
            continue
        word = fields[0]
        timestamp = datetime.now().strftime("%f")
        # print(f"🎙️ Azure generating: {word}")
        # print(f"  Audio text: {fields[4]}")
        audio1 = generate_azure_audio(fields[4], f"az_{word}_{timestamp}_1.mp3")
        # print(f"  Audio1 result: {audio1}")
        audio2 = generate_azure_audio(fields[7], f"az_{word}_{timestamp}_2.mp3")
        # print(f"  Audio2 result: {audio2}")
        audio3 = generate_azure_audio(fields[10], f"az_{word}_{timestamp}_3.mp3")
        # print(f"  Audio3 result: {audio3}")
        if not audio1:
            print(f"⚠️ No audio generated for Audio field in word: {word}")
        if not audio2:
            print(f"⚠️ No audio generated for Exemple1-Audio field in word: {word}")
        if not audio3:
            print(f"⚠️ No audio generated for Exemple2-Audio field in word: {word}")
        notes.append({
            "deckName": target_deck,
            "modelName": model_name,
            "fields": {
                "Français": fields[0],
                "English": fields[1],
                "Synonyme": fields[2],
                "Conjugaison/Féminin ou Masculin": fields[3],
                "Audio": audio1,
                "Exemple-FR": fields[5],
                "Exemple-EN": fields[6],
                "Exemple1-Audio": audio2,
                "Exemple2-FR": fields[8],
                "Exemple2-EN": fields[9],
                "Exemple2-Audio": audio3,
                "Extend": fields[11],
                "Hint": fields[12]
            },
            "tags": ["C1_AutoGenerated"]
        })

    if notes:
        anki_request("addNotes", notes=notes)
        print(f"✅ All notes with Azure audio added successfully!")


def load_system_instructions():
    prompt_file = "system_prompt.md"
    if os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()

    # If the file does not exist, raise so caller can handle/exit explicitly
    raise FileNotFoundError("system_prompt.md not found in working directory. Please create it with the system prompt.")


if __name__ == "__main__":
    # Use existing CSV file anki_voc_20260304.csv if available
    csv_file = "anki_voc_20260304.csv"
    
    try:
        if os.path.exists(csv_file):
            print(f"📄 Using existing CSV: {csv_file}")
            add_notes_to_anki(csv_file)
        else:
            print(f"❌ CSV file {csv_file} not found.")
            system_instructions = load_system_instructions()
            my_words = """
céder à
réprénsible
"""
            model_choice = "gemini"
            llm_generate_anki_note(model_choice, system_instructions, my_words)
    except Exception as e:
        print(f"❌ Error: {e}")