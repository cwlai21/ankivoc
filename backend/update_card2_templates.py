"""
Script to update existing CardTemplate records with Card 2 (Listening/Spelling) templates
and add 'No Spell' field to field definitions.
"""
import os
import sys
import django

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from languages.models import Language, CardTemplate
from cards.services.anki_connect import AnkiConnectClient

def update_templates():
    """Update all existing CardTemplate records with Card 2 templates"""
    
    # Get all templates
    templates = CardTemplate.objects.all()
    
    if not templates.exists():
        print("No templates found in database.")
        return
    
    anki_client = AnkiConnectClient()
    
    for template in templates:
        language = template.language
        lang_code = language.code
        native_name = language.name
        
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
        lang_flag = lang_flag_map.get(lang_code, '🌐')
        
        # Add 'No Spell' field if not already present
        fields = template.fields_definition
        if 'No Spell' not in fields:
            fields.append('No Spell')
            print(f"Added 'No Spell' field to {native_name} template")
        
        # Get language-specific script (simplified version)
        if lang_code == 'zh':
            script = f"""
var register = document.getElementById("register");
var text = register.innerText || register.textContent;
if (text.includes("(") && text.includes(")")) {{
    var parts = text.match(/^(.+?)\\s*\\((.+?)\\)$/);
    if (parts) {{
        register.innerHTML = parts[1] + " <span style='color:#818cf8; font-size:16px;'>(" + parts[2] + ")</span>";
    }}
}}
"""
        elif lang_code == 'ja':
            script = f"""
var register = document.getElementById("register");
var text = register.innerText || register.textContent;
if (text.includes("[") && text.includes("]")) {{
    var parts = text.match(/^(.+?)\\s*\\[(.+?)\\]$/);
    if (parts) {{
        register.innerHTML = parts[1] + " <span style='color:#818cf8; font-size:16px;'>[" + parts[2] + "]</span>";
    }}
}}
"""
        else:
            script = ""
        
        # Create Card 2 front template (Listening/Spelling with typing)
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

{{{{^No Spell}}}}
<div class="Text_Card radius">
<div class="Text-answer">{{{{type:{native_name}}}}}</div>
</div>
{{{{/No Spell}}}}
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

{{{{^No Spell}}}}
<div class="Text_Card radius">
<div class="Text-answer">{{{{type:{native_name}}}}}</div>
</div>
{{{{/No Spell}}}}
{{{{/Audio}}}}

<script>
{script}
</script>"""
        
        # Create Card 2 back template
        back_template_card2 = f"""{{{{FrontSide}}}}
<div class="noreplaybutton"> [sound:silence1.mp3] </div>"""
        
        # Update template
        template.fields_definition = fields
        template.front_template_card2 = front_template_card2
        template.back_template_card2 = back_template_card2
        template.save()
        
        print(f"\n✅ Updated {native_name} template:")
        print(f"   - Added Card 2 front template ({len(front_template_card2)} chars)")
        print(f"   - Added Card 2 back template ({len(back_template_card2)} chars)")
        print(f"   - Total fields: {len(fields)}")
        print(f"   - Model name in Anki: {template.anki_model_name}")

if __name__ == '__main__':
    print("Starting Card 2 template update...")
    print("=" * 60)
    update_templates()
    print("\n" + "=" * 60)
    print("✅ Database templates updated successfully!")
    print("\n⚠️  IMPORTANT: To apply Card 2 templates to Anki models:")
    print("\n📝 Manual steps required in Anki:")
    print("1. Open Anki and go to: Tools > Manage Note Types")
    print("2. For each model (中文-(R/L), Français-(R/L), etc.):")
    print("   a) Select the model and click 'Cards...'")
    print("   b) Select 'Card 2' from the card list")
    print("   c) Copy the Card 2 front template from below")
    print("   d) Paste into the 'Front Template' area")
    print("   e) Copy the Card 2 back template")
    print("   f) Paste into the 'Back Template' area")
    print("   g) Click 'Save'")
    print("3. Add 'No Spell' field to each model:")
    print("   a) In 'Manage Note Types', select model")
    print("   b) Click 'Fields...'")
    print("   c) Click 'Add' and name it 'No Spell'")
    print("   d) Click 'Save'")
    print("\n💡 Or delete existing models and let the system recreate them:")
    print("   - The next time you generate cards, the system will")
    print("     automatically create models with the new Card 2 templates")
    print("\n🔍 Templates are stored in the database and ready to use!")
