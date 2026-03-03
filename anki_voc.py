import os
import re
from dotenv import dotenv_values
from openai import OpenAI
from groq import Groq
from datetime import datetime
import requests

def llm_generate_csv(model: str, system_instructions: str, word_list: str):
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
    
    print(f"✅ CSV saved as {filename}")
    return filename

if __name__ == "__main__":
    system_instructions = """
Role: Expert French Linguist and Anki Specialist.
Task: Generate Anki cards in a semicolon-separated CSV format (;).

Field Order (Strictly 13 Columns):
1. Français | 2. English | 3. Synonyme | 4. Conjugaison/Féminin ou Masculin | 5. Audio | 6. Exemple-FR | 7. Exemple-EN | 8. Exemple1-Audio | 9. Exemple2-FR | 10. Exemple2-EN | 11. Exemple2-Audio | 12. Extend | 13. Hint

STRICT PUNCTUATION RULES:
- Use the SEMICOLON (;) ONLY as a column delimiter (exactly 12 per row).
- Inside a sentence or list of meanings, NEVER use a semicolon. Use a COMMA (,) or COLON (:) instead.
- Example correct: "He is secretive: he never reveals his plans"
- Example wrong: "He is secretive; he never reveals his plans"

Linguistic Requirements:
- Level: C1/C2. High-level vocabulary but common enough for learners and daily use.
- Audio Logic: Fields 5, 8, and 11 MUST contain the PLAIN FRENCH TEXT (no [sound:] tags).
- No header row.
"""

    my_words = """"
s'étioler
ostentatoire
acerbe
céder à
"""
    
    model_choice = "gemini" 
    
    try:
        llm_generate_csv(model_choice, system_instructions, my_words)
    except Exception as e:
        print(f"❌ Error: {e}")