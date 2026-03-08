"""
Test to verify Card 2 templates have typing functionality.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from languages.models import CardTemplate

def test_card2_templates():
    """Verify Card 2 templates contain required features"""
    
    templates = CardTemplate.objects.all()
    
    if not templates.exists():
        print("❌ No templates found")
        return False
    
    all_passed = True
    
    for template in templates:
        language_name = template.language.name
        native_name = template.language.name
        
        print(f"\n🔍 Testing {language_name} template...")
        
        # Check if Card 2 templates exist
        if not template.front_template_card2:
            print(f"  ❌ No Card 2 front template")
            all_passed = False
            continue
        
        if not template.back_template_card2:
            print(f"  ❌ No Card 2 back template")
            all_passed = False
            continue
        
        front = template.front_template_card2
        
        # Test 1: Check for typing functionality
        if '{{type:' in front:
            print(f"  ✅ Has typing functionality: {{{{type:{native_name}}}}}")
        else:
            print(f"  ❌ Missing typing functionality")
            all_passed = False
        
        # Test 2: Check for conditional Audio display
        if '{{#Audio}}' in front and '{{^Audio}}' in front:
            print(f"  ✅ Has conditional Audio display")
        else:
            print(f"  ❌ Missing conditional Audio display")
            all_passed = False
        
        # Test 3: Check for No Spell field integration
        if '{{#No Spell}}' in front or '{{^No Spell}}' in front:
            print(f"  ✅ Has No Spell field integration")
        else:
            print(f"  ❌ Missing No Spell field integration")
            all_passed = False
        
        # Test 4: Check for Hint field
        if '{{#Hint}}' in front:
            print(f"  ✅ Has Hint field display")
        else:
            print(f"  ⚠️  No Hint field (optional)")
        
        # Test 5: Check for title bars
        if 'Listening & Spelling' in front and 'Reading & Spelling' in front:
            print(f"  ✅ Has appropriate title bars")
        else:
            print(f"  ❌ Missing title bars")
            all_passed = False
        
        # Test 6: Check fields definition has 'No Spell'
        if 'No Spell' in template.fields_definition:
            print(f"  ✅ 'No Spell' field in field definitions")
        else:
            print(f"  ❌ 'No Spell' field missing from field definitions")
            all_passed = False
        
        # Count total fields
        field_count = len(template.fields_definition)
        print(f"  ℹ️  Total fields: {field_count}")
    
    return all_passed

if __name__ == '__main__':
    print("=" * 70)
    print("🧪 Testing Card 2 (Listening/Spelling) Templates")
    print("=" * 70)
    
    result = test_card2_templates()
    
    print("\n" + "=" * 70)
    if result:
        print("✅ All tests passed! Card 2 templates are properly configured.")
        print("\n📝 Next steps:")
        print("1. Run: python show_card2_templates.py")
        print("2. Copy templates to Anki models manually")
        print("3. Test cards in Anki by reviewing Card 2")
    else:
        print("❌ Some tests failed. Review the errors above.")
    print("=" * 70)
