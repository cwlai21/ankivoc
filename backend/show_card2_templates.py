"""
Display Card 2 templates for manual copying to Anki.
Run this after update_card2_templates.py to get the templates.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from languages.models import CardTemplate

def display_templates():
    """Display Card 2 templates for each language"""
    
    templates = CardTemplate.objects.all().order_by('language__name')
    
    if not templates.exists():
        print("No templates found.")
        return
    
    for template in templates:
        language_name = template.language.name
        model_name = template.anki_model_name
        
        print("\n" + "=" * 70)
        print(f"📚 {language_name} - Model: {model_name}")
        print("=" * 70)
        
        print("\n" + "-" * 70)
        print("CARD 2 FRONT TEMPLATE:")
        print("-" * 70)
        print(template.front_template_card2)
        
        print("\n" + "-" * 70)
        print("CARD 2 BACK TEMPLATE:")
        print("-" * 70)
        print(template.back_template_card2)
        
        print("\n")
        print("💡 How to use:")
        print(f"1. Open Anki: Tools > Manage Note Types")
        print(f"2. Select '{model_name}' and click 'Cards...'")
        print(f"3. Select 'Card 2' from the list")
        print(f"4. Copy the FRONT template above and paste into 'Front Template'")
        print(f"5. Copy the BACK template above and paste into 'Back Template'")
        print(f"6. Click 'Save'")
        print("")

if __name__ == '__main__':
    print("\n🎯 Card 2 (Listening/Spelling) Templates for Anki\n")
    display_templates()
    print("=" * 70)
    print("✅ Copy the templates above to your Anki models!")
    print("=" * 70)
    print("\n📝 Don't forget to add 'No Spell' field to each model:")
    print("   - Go to: Tools > Manage Note Types")
    print("   - Select model > Fields... > Add")
    print("   - Name: 'No Spell'")
    print("   - Save")
    print("\n💡 Leave 'No Spell' empty to enable typing practice")
    print("   Add any text to 'No Spell' to disable typing for specific cards\n")
