import os
import re
from dotenv import dotenv_values
from openai import OpenAI
from groq import Groq
from datetime import datetime
import requests
import json
import urllib.request


def llm_generate_anki_note(model: str, system_instructions: str, word_list: str):
    config = dotenv_values(".env")
    today = datetime.today().strftime("%Y%m%d")
    filename = f"anki_voc_{today}.csv"
   
    # Combine instructions with word list
    full_prompt = f"{system_instructions}\n\nWORD_LIST TO PROCESS:\n{word_list}"

    if model == "gemini":
        api_key = config.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("No GOOGLE_API_KEY found in .env for Gemini.")

        # List models to find valid candidates
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

    # --- CLEANING LOGIC ---
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


def add_notes_to_anki(csv_filename: str, deck_name: str = "Vocabulaire", model_name: str = "Français-(R/L)"):
    """Read semicolon-separated CSV and add notes to Anki via AnkiConnect.

    - Assumes each valid line has 13 semicolon-separated fields.
    - Default deck is `Vocabulaire` and default note type/model is `Vocabulaire`.
    """
    notes = []
    try:
        with open(csv_filename, 'r', encoding='utf-8') as f:
            lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    except Exception as e:
        print(f"❌ Could not read CSV file {csv_filename}: {e}")
        return

    for line in lines:
        fields = line.split(';')
        if len(fields) < 13:
            continue

        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": {
                "Français": fields[0],
                "English": fields[1],
                "Synonyme": fields[2],
                "Conjugaison/Féminin ou Masculin": fields[3],
                "Audio": fields[4],
                "Exemple-FR": fields[5],
                "Exemple-EN": fields[6],
                "Exemple1-Audio": fields[7],
                "Exemple2-FR": fields[8],
                "Exemple2-EN": fields[9],
                "Exemple2-Audio": fields[10],
                "Extend": fields[11],
                "Hint": fields[12]
            },
            "tags": ["C1_AutoGenerated"]
        }
        notes.append(note)

    if not notes:
        print("⚠️ No valid notes found in CSV to add to Anki.")
        return

    payload = {
        "action": "addNotes",
        "version": 6,
        "params": {
            "notes": notes
        }
    }

    req = urllib.request.Request('http://localhost:8765', data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = resp.read()
        result = json.loads(resp_data)
        if result.get('error'):
            print(f"❌ AnkiConnect Error: {result['error']}")
        else:
            # result['result'] is usually a list of note IDs or info
            added = result.get('result')
            print(f"✅ Successfully requested adding {len(notes)} notes to Anki (AnkiConnect response: {added})")
    except Exception as e:
        print(f"❌ Could not connect to Anki: {e}. Is Anki with AnkiConnect running?")

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
réprénsible
"""
            model_choice = "gemini"
            llm_generate_anki_note(model_choice, system_instructions, my_words)
    except Exception as e:
        print(f"❌ Error: {e}")