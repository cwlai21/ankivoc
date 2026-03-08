#!/usr/bin/env python
"""
Regenerate all CardTemplates using current pipeline code.
This ensures fields_definition and templates are in sync.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from languages.models import Language, CardTemplate

def generate_template_for_language(target_lang, explanation_lang):
    """Generate CardTemplate for a specific language."""
    
    # Get native name for deck/model naming
    native_name = target_lang.native_name or target_lang.name
    
    # Build model name: <NativeLanguageName>-(R/L)
    model_name = f"{native_name}-(R/L)"
    
    # Build deck name: <NativeLanguageName>::Vocabulary
    deck_name = f"{native_name}::Vocabulary"
    
    # Define field list using native name for first field
    fields = [
        native_name,  # Target language word (e.g., "中文" for Chinese)
        'Explanation',
        'Synonyme',
        'Conjugaison/Gender',
        'Audio',
        f'exemple-{target_lang.code.upper()}',
        'exemple-Explanation',
        'exemple1-Audio',
        f'exemple2-{target_lang.code.upper()}',
        'exemple2-Explanation',
        'exemple2-Audio',
        'Extend',
        'Hint',
        'No Spell',
    ]
    
    # Get language flag emoji
    lang_flag_map = {
        'fr': '🇫🇷',
        'en': '🇬🇧',
        'zh': '🇨🇳',
        'es': '🇪🇸',
        'de': '🇩🇪',
        'ja': '🇯🇵',
        'ko': '🇰🇷',
    }
    lang_flag = lang_flag_map.get(target_lang.code, '🌍')
    
    # Card 1 front template - Display target word
    front_template_card1 = f"""<div class="TitleBar title-r">
<span style="font-size: 18px; padding-right: 5px;">{lang_flag}</span>
Reading
<span style="font-size: 18px; padding-left: 5px;">{lang_flag}</span>
</div>
<div class="Tag light-r">
{{{{#Tags}}}} &nbsp; {{{{Tags}}}} {{{{/Tags}}}}</div>

<div class="Text_Card radius">
<div id="register" class="Text_big">{{{{{native_name}}}}}</div>
{{{{#Conjugaison/Gender}}}}<div class="Verbform">{{{{Conjugaison/Gender}}}}</div>{{{{/Conjugaison/Gender}}}}
{{{{Audio}}}}
</div>

<script>
// Language-specific card initialization
window.ankiCardInit = function() {{
    const textBig = document.querySelector('.Text_big');
    if (textBig) {{
        textBig.style.fontSize = '36px';
    }}
}};

if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', window.ankiCardInit);
}} else {{
    window.ankiCardInit();
}}
</script>"""
    
    # Card 1 back template
    back_template_card1 = """{{FrontSide}}
<div class="noreplaybutton"> [sound:silence1.mp3] </div>
<div class="Text_Card radius"><hr id=answer>
<div class="Text-answer">
{{Explanation}}
</div>
{{Synonyme}}
</div>

{{#exemple-""" + target_lang.code.upper() + """}}
<ul class="light-r2">
					<li class="eB">{{exemple-""" + target_lang.code.upper() + """}}{{exemple1-Audio}}
{{/exemple-""" + target_lang.code.upper() + """}}
{{#exemple-""" + target_lang.code.upper() + """}}
					<li class="eg">{{exemple-Explanation}}
{{/exemple-""" + target_lang.code.upper() + """}}

{{#exemple2-""" + target_lang.code.upper() + """}}
					<li class="eB">{{exemple2-""" + target_lang.code.upper() + """}}{{exemple2-Audio}}
{{/exemple2-""" + target_lang.code.upper() + """}}{{#exemple2-Explanation}}
					<li class="eg">{{exemple2-Explanation}}
{{/exemple2-Explanation}}
</ul>

{{#Extend}}
<div class="extend">
{{Extend}}
</div>
{{/Extend}}"""
    
    # Card 2 front template (Listening/Spelling)
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
    
    # Card 2 back template - aligned with Card 1 format
    back_template_card2 = f"""{{{{FrontSide}}}}
<div class="noreplaybutton"> [sound:silence1.mp3] </div>
<div class="Text_Card radius"><hr id=answer>
<div class="Text-answer">
{{{{Explanation}}}}
</div>
{{{{Synonyme}}}}
</div>

{{{{#exemple-{target_lang.code.upper()}}}}}
<ul class="light-r2">
					<li class="eB">{{{{exemple-{target_lang.code.upper()}}}}}{{{{exemple1-Audio}}}}
{{{{/exemple-{target_lang.code.upper()}}}}}
{{{{#exemple-{target_lang.code.upper()}}}}}
					<li class="eg">{{{{exemple-Explanation}}}}
{{{{/exemple-{target_lang.code.upper()}}}}}

{{{{#exemple2-{target_lang.code.upper()}}}}}
					<li class="eB">{{{{exemple2-{target_lang.code.upper()}}}}}{{{{exemple2-Audio}}}}
{{{{/exemple2-{target_lang.code.upper()}}}}}{{{{#exemple2-Explanation}}}}
					<li class="eg">{{{{exemple2-Explanation}}}}
{{{{/exemple2-Explanation}}}}
</ul>

{{{{#Extend}}}}
<div class="extend">
{{{{Extend}}}}
</div>
{{{{/Extend}}}}"""
    
    # CSS (dark theme)
    css = """.card {
    font-family: 'Segoe UI', 'Microsoft YaHei', '微软正黑体', Arial, sans-serif;
    font-size: 20px;
    text-align: center;
    color: #e0e0e0;
    background-color: #1e1e1e;
    padding: 0;
    line-height: 1.6;
}

input[type="text"] {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #404040;
    padding: 8px 12px;
    font-size: 18px;
    border-radius: 4px;
    width: 80%;
    max-width: 400px;
}

input[type="text"]:focus {
    outline: none;
    border-color: #818cf8;
    box-shadow: 0 0 0 2px rgba(129,140,248,0.2);
}

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
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.title-l {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
}

.Tag {
    padding: 8px;
    font-size: 12px;
    margin-bottom: 15px;
}

.light-r {
    background-color: #2d2d2d;
    color: #a5b4fc;
    border-radius: 4px;
}

.Text_Card {
    background-color: #2d2d2d;
    padding: 20px;
    margin: 10px;
}

.radius {
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

.Text_big {
    font-size: 36px;
    font-weight: bold;
    color: #818cf8;
    margin: 20px 0;
}

.Text-answer {
    font-size: 28px;
    color: #e0e0e0;
    margin: 15px 0;
}

.Synonyme {
    font-size: 16px;
    color: #4ade80;
    margin: 10px 0;
    font-style: italic;
}

.Verbform {
    font-size: 20px;
    color: #fbbf24;
    margin: 8px 0;
    max-width: 800px;
    line-height: 1.5;
    word-wrap: break-word;
}

.light-r2 {
    background-color: #2d2d2d;
    border-radius: 8px;
    padding: 15px 30px;
    margin: 15px 10px;
    text-align: left;
    list-style: none;
}

.eB {
    font-size: 22px;
    color: #1976d2;
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
    color: #9ca3af;
    margin: 5px 0 15px 20px;
    font-style: italic;
    max-width: 800px;
    line-height: 1.4;
    word-wrap: break-word;
}

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

hr#answer {
    border: none;
    border-top: 3px solid #404040;
    margin: 20px 0;
}

.noreplaybutton {
    display: none;
}"""
    
    # Create or update CardTemplate
    template, created = CardTemplate.objects.update_or_create(
        language=target_lang,
        defaults={
            'anki_model_name': model_name,
            'default_deck_name': deck_name,
            'fields_definition': fields,
            'front_template': front_template_card1,
            'back_template': back_template_card1,
            'front_template_card2': front_template_card2,
            'back_template_card2': back_template_card2,
            'css_style': css,
        }
    )
    
    return template, created

def regenerate_all_templates():
    """Regenerate CardTemplates for all languages."""
    languages = Language.objects.all()
    explanation_lang = Language.objects.get(code='en')
    
    print(f"Found {languages.count()} languages")
    print(f"Using {explanation_lang.name} as explanation language\n")
    
    for lang in languages:
        print(f"Processing {lang.name} ({lang.code})...")
        
        try:
            template, created = generate_template_for_language(lang, explanation_lang)
            
            action = "Created new" if created else "Updated"
            print(f"  ✓ {action} template")
            print(f"    Model: {template.anki_model_name}")
            print(f"    Deck: {template.default_deck_name}")
            print(f"    Fields: {len(template.fields_definition)} fields")
            print(f"    First field: {template.fields_definition[0] if template.fields_definition else 'N/A'}")
            
            # Check Card 2 template for type: fields
            import re
            type_fields = re.findall(r'\{\{type:([^}]+)\}\}', template.front_template_card2 or '')
            if type_fields:
                print(f"    Card 2 type fields: {type_fields}")
                # Verify they match first field
                if type_fields[0] == template.fields_definition[0]:
                    print(f"    ✓ Type field matches first field name")
                else:
                    print(f"    ⚠ WARNING: Type field '{type_fields[0]}' does not match first field '{template.fields_definition[0]}'")
            print()
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("="*60)
    print("Regeneration complete!")
    print(f"Total templates: {CardTemplate.objects.count()}")

if __name__ == '__main__':
    regenerate_all_templates()
