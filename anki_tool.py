import tkinter as tk
from tkinter import messagebox

# Configuration: Your EXACT 13-field order
FIELDS = [
    "Français", "English", "Synonyme", "Conjugaison/Féminin ou Masculin", 
    "Audio", "Exemple-FR", "Exemple-EN", "Exemple1-Audio", 
    "Exemple2-FR", "Exemple2-EN", "Exemple2-Audio", "Extend", "Hint"
]

def generate_csv_format():
    input_text = text_input.get("1.0", tk.END).strip()
    if not input_text:
        messagebox.showwarning("Error", "Please paste words first.")
        return

    prompt = f"MY FIELD ORDER IS: {', '.join(FIELDS)}\n\n"
    prompt += "Please create cards for these words following Solution A (Plain Text for AwesomeTTS Batch Generation):\n"
    prompt += "- Fields 5 (Audio), 8 (Exemple1-Audio), and 11 (Exemple2-Audio) must contain the PLAIN FRENCH TEXT (no brackets, no [sound:]).\n"
    prompt += "- Examples must be C1 level, sophisticated, and interesting.\n"
    prompt += "- Use a semicolon (;) as the separator.\n\n"
    prompt += "Words to process:\n" + input_text + "\n\n"
    prompt += "You can paste this prompt directly to Gemini or ChatGPT. The output should be a CSV (semicolon separated) matching the field order above."

    root.clipboard_clear()
    root.clipboard_append(prompt)
    messagebox.showinfo("Success", "Prompt copied! Paste it to Gemini or ChatGPT.")

def save_csv():
    csv_content = csv_input.get("1.0", tk.END).strip()
    if not csv_content:
        messagebox.showwarning("Error", "Please paste CSV content from Gemini/ChatGPT.")
        return
    try:
        with open("anki_output.csv", "w", encoding="utf-8") as f:
            f.write(csv_content)
        messagebox.showinfo("Success", "CSV saved as anki_output.csv in this folder.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save CSV: {e}")

root = tk.Tk()
root.title("Anki C1 French - AwesomeTTS Ready")
root.geometry("500x600")

tk.Label(root, text="Paste French words/phrases:", font=("Arial", 10, "bold")).pack(pady=5)
text_input = tk.Text(root, height=10, width=55)
text_input.pack(pady=5, padx=10)

tk.Button(root, text="Copy Prompt for Gemini/ChatGPT", command=generate_csv_format, bg="#769FCD", fg="white", font=("Arial", 10, "bold")).pack(pady=10)

tk.Label(root, text="Paste CSV result from Gemini/ChatGPT:", font=("Arial", 10, "bold")).pack(pady=5)
csv_input = tk.Text(root, height=10, width=55)
csv_input.pack(pady=5, padx=10)

tk.Button(root, text="Save CSV to Folder", command=save_csv, bg="#A7C7E7", fg="black", font=("Arial", 10, "bold")).pack(pady=10)

root.mainloop()