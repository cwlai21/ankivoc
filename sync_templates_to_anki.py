"""
手动同步模板到 Anki
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
print("同步所有模板到 Anki")
print("=" * 80)
print()

# Get Chinese template as example
zh = CardTemplate.objects.get(language__code='zh')

print(f"语言: {zh.language.name}")
print(f"模型: {zh.anki_model_name}")
print()

# Check the template content
print("检查 Card 2 Front 模板:")
print("-" * 80)
if '{{type:' in zh.front_template_card2:
    print("⚠️ 数据库中仍有 {{type:}} 字段 - 这不应该发生！")
else:
    print("✓ 数据库中已移除 {{type:}} 字段")

if '<script>' in zh.front_template_card2 and 'ankiTypingValidation' in zh.front_template_card2:
    print("⚠️ 数据库中仍有验证脚本")
else:
    print("✓ 数据库中已移除验证脚本")

print()
print("=" * 80)
print("同步到 Anki...")
print("=" * 80)

try:
    anki = AnkiConnectClient()
    
    # Use the low-level _invoke method to update templates
    # Update CSS
    anki._invoke('updateModelStyling', model={
        'name': zh.anki_model_name,
        'css': zh.css_style
    })
    print(f"✓ 更新了 CSS 样式")
    
    # Update Card 2 Front template
    anki._invoke('updateModelTemplates', model={
        'name': zh.anki_model_name,
        'templates': {
            'Card 2': {
                'Front': zh.front_template_card2,
                'Back': zh.back_template_card2
            }
        }
    })
    print(f"✓ 更新了 Card 2 模板到 Anki")
    
    print()
    print("=" * 80)
    print("同步完成！")
    print("=" * 80)
    print()
    print("请检查 Anki 中的模板编辑器:")
    print("1. 工具 → 管理笔记类型")
    print("2. 选择'中文-(R/L)'")
    print("3. 点击'卡片...'")
    print("4. 选择 Card 2")
    print("5. 验证:")
    print("   - Front 模板应该有 {{中文}} 而不是 {{type:中文}}")
    print("   - 没有 <script> 标签")
    
except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
