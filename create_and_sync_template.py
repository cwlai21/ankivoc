"""
创建中文模型并同步模板
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/cwlai/LangChain_AI/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from languages.models import CardTemplate
from cards.services.anki_connect import AnkiConnectClient

print("=" * 80)
print("创建/更新中文模型")
print("=" * 80)
print()

# Get Chinese template
zh = CardTemplate.objects.get(language__code='zh')

print(f"语言: {zh.language.name}")
print(f"模型: {zh.anki_model_name}")
print(f"牌组: {zh.default_deck_name}")
print()

try:
    anki = AnkiConnectClient()
    
    # Check if model exists
    existing_models = anki._invoke('modelNames')
    
    if zh.anki_model_name in existing_models:
        print(f"✓ 模型 '{zh.anki_model_name}' 已存在")
    else:
        print(f"⚠️ 模型 '{zh.anki_model_name}' 不存在，正在创建...")
        
        # Create the model using create_model_if_missing
        anki.create_model_if_missing(
            model_name=zh.anki_model_name,
            in_order_fields=zh.fields_definition,
            card_template=zh
        )
        print(f"✓ 创建了模型 '{zh.anki_model_name}'")
    
    print()
    print("=" * 80)
    print("同步模板到 Anki...")
    print("=" * 80)
    
    # Update CSS
    anki._invoke('updateModelStyling', model={
        'name': zh.anki_model_name,
        'css': zh.css_style
    })
    print(f"✓ 更新了 CSS 样式")
    
    # Update Card 2 templates
    anki._invoke('updateModelTemplates', model={
        'name': zh.anki_model_name,
        'templates': {
            'Card 2': {
                'Front': zh.front_template_card2,
                'Back': zh.back_template_card2
            }
        }
    })
    print(f"✓ 更新了 Card 2 模板")
    
    print()
    print("=" * 80)
    print("完成！")
    print("=" * 80)
    print()
    print("Card 2 Front 现在的结构:")
    print("- Listening 模式: 显示音频 + Hint")
    print("- Reading 模式: 显示 Explanation + Hint")
    print("- 不显示中文答案（答案在 Back 中显示）")
    
except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
