"""
同步所有语言的 Card 2 模板到 Anki
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
print("同步所有语言的模板到 Anki")
print("=" * 80)
print()

# Get all card templates
templates = CardTemplate.objects.all()
anki = AnkiConnectClient()

# Check existing models in Anki
existing_models = anki._invoke('modelNames')
print(f"Anki 中现有 {len(existing_models)} 个模型")
print()

success_count = 0
created_count = 0
error_count = 0

for template in templates:
    lang_name = template.language.name
    model_name = template.anki_model_name
    
    print(f"【{lang_name}】")
    print(f"  模型: {model_name}")
    
    try:
        # Check if model exists, create if not
        if model_name not in existing_models:
            print(f"  ⚠️  模型不存在，正在创建...")
            anki.create_model_if_missing(
                model_name=model_name,
                in_order_fields=template.fields_definition,
                card_template=template
            )
            created_count += 1
            print(f"  ✓ 创建了模型")
        
        # Update CSS
        anki._invoke('updateModelStyling', model={
            'name': model_name,
            'css': template.css_style
        })
        
        # Update Card 2 templates
        anki._invoke('updateModelTemplates', model={
            'name': model_name,
            'templates': {
                'Card 2': {
                    'Front': template.front_template_card2,
                    'Back': template.back_template_card2
                }
            }
        })
        
        print(f"  ✓ 更新了 Card 2 模板")
        success_count += 1
        
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        error_count += 1
    
    print()

print("=" * 80)
print("同步完成！")
print("=" * 80)
print(f"成功: {success_count} 个语言")
print(f"创建: {created_count} 个新模型")
print(f"失败: {error_count} 个语言")
print()
print("所有语言的 Card 2 Front 现在:")
print("- Listening 模式: 显示音频 + Hint")
print("- Reading 模式: 显示 Explanation + Hint")
print("- 不显示答案（答案在 Back 中显示）")
print("- 已移除 {{^No Spell}} 区块")
