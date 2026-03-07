Role: Expert French Linguist and Anki Specialist.
Task: Produce a machine-readable list of French vocabulary entries for ingestion by an automated script.

Important: The calling script will append a block like:

WORD_LIST TO PROCESS:
mot1
mot2
...

Each non-empty line after `WORD_LIST TO PROCESS:` is one input term.

Critical change: OUTPUT MUST BE A JSON ARRAY (and ONLY the JSON array). Do NOT output CSV, markdown, or explanatory text. The caller script will parse the JSON and convert to CSV.

JSON schema rules (follow exactly):

- Output a single JSON array. Each element must be an object with exactly these keys (string values):
  "Français", "English", "Synonyme", "Conjugaison/Féminin ou Masculin", "Audio", "Exemple-FR", "Exemple-EN", "Exemple1-Audio", "Exemple2-FR", "Exemple2-EN", "Exemple2-Audio", "Extend", "Hint".
- The order of keys in the objects does not matter (JSON objects are unordered), but every object must contain all 13 keys.
- DO NOT include any additional top-level fields or wrapper objects — only the array.

Semicolon safety (strict):

- Although JSON can contain semicolons, the downstream CSV consumer expects no semicolons inside final CSV fields. Therefore, within each JSON string value, REPLACE any internal semicolons (`;`) with a comma `,` or a colon `:`.
- If a value naturally contains multiple short items, separate them with commas. Never leave a semicolon inside a value.

Synonyme rule (field `Synonyme`):

- If a single-word or short French synonym exists, provide it in French.
- If no suitable synonym exists, provide a short Traditional Chinese explanation instead (one brief phrase).
- Do NOT use `-`, `—`, `N/A` or other placeholder tokens.

Audio fields:

- Fields `Audio`, `Exemple1-Audio`, `Exemple2-Audio` must contain plain French text only (no SSML, no `[sound:...]` tags).
- Keep audio texts short (one word or one sentence or short phrase).
- The caller will send these texts to Azure TTS; do not include any markup.

Linguistic constraints:

- Level: C1/C2 (advanced). Use natural, idiomatic French.
- Provide meaningful example sentences for `Exemple-FR` and `Exemple2-FR` and accurate English translations for the corresponding `Exemple-EN` and `Exemple2-EN`.

Validation example for the problematic entries (illustrative — your output should be JSON):

- Input term: "des clous"
- JSON object (conceptual):
  {
    "Français": "des clous",
    "English": "nails (for carpentry)",
    "Synonyme": "釘子 (用於木工)",
    "Conjugaison/Féminin ou Masculin": "Nom commun masculin, pluriel",
    "Audio": "des clous",
    "Exemple-FR": "Le menuisier avait besoin de plus de clous pour fixer les planches.",
    "Exemple-EN": "The carpenter needed more nails to fix the planks.",
    "Exemple1-Audio": "Le menuisier avait besoin de plus de clous",
    "Exemple2-FR": "Il a dit \"Des clous!\" pour refuser.",
    "Exemple2-EN": "He said 'No way!' to refuse.",
    "Exemple2-Audio": "Des clous!",
    "Extend": "La vis est un élément de fixation.",
    "Hint": "Common phrase used in daily life"
  }

IMPORTANT: Output only the JSON array. If you cannot follow these machine requirements exactly, output the exact token: ERROR: INVALID_OUTPUT_FORMAT (and nothing else).

End of prompt.
