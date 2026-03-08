"""
专门修复法语模板
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/cwlai/LangChain_AI/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from languages.models import Language, CardTemplate
from cards.services.anki_connect import AnkiConnectClient

print("=" * 80)
print("修复法语 Card 2 模板")
print("=" * 80)
print()

# Get French template
fr = CardTemplate.objects.get(language__code='fr')

print(f"语言: {fr.language.name}")
print(f"模型: {fr.anki_model_name}")
print()

anki = AnkiConnectClient()

try:
    # Check current templates
    templates = anki._invoke('modelTemplates', modelName=fr.anki_model_name)
    template_data = templates.get('result', {})
    
    print(f"当前模板: {list(template_data.keys())}")
    
    if 'Card 2' in template_data:
        print("✓ Card 2 已存在，更新中...")
        
        # Update templates
        anki._invoke('updateModelTemplates', model={
            'name': fr.anki_model_name,
            'templates': {
                'Card 2': {
                    'Front': fr.front_template_card2,
                    'Back': fr.back_template_card2
                }
            }
        })
        print("✓ Card 2 已更新")
    else:
        print("⚠️ Card 2 不存在，需要重新创建整个模型...")
        
        # Recreate the model
        # First, we need to check if there are any cards using this model
        print("警告：重新创建模型会删除所有现有卡片！")
        print("建议：在 Anki 中手动添加 Card 2")
        
except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
