#!/usr/bin/env python
"""
更新 Anki 中现有模型的模板
"""
import os
import sys
import django
import requests

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from languages.models import CardTemplate

ANKI_URL = 'http://localhost:8765'

def anki_request(action, **params):
    """Send request to AnkiConnect."""
    payload = {
        'action': action,
        'version': 6,
        'params': params
    }
    response = requests.post(ANKI_URL, json=payload)
    result = response.json()
    if result.get('error'):
        raise Exception(f"AnkiConnect error: {result['error']}")
    return result.get('result')

def update_model_templates(model_name, card_template):
    """
    更新 Anki 模型的模板和样式
    """
    try:
        # 检查模型是否存在
        models = anki_request('modelNames')
        if model_name not in models:
            print(f"✗ 模型 '{model_name}' 不存在")
            return False
        
        print(f"正在更新模型: {model_name}")
        
        # 获取当前模型信息
        model_info = anki_request('modelNamesAndIds')
        model_id = model_info.get(model_name)
        
        if not model_id:
            print(f"✗ 无法获取模型 ID")
            return False
        
        # 使用 updateModelTemplates API
        try:
            templates = {
                'Reading': {
                    'Front': card_template.front_template,
                    'Back': card_template.back_template
                },
                'Listening': {
                    'Front': card_template.front_template_card2,
                    'Back': card_template.back_template_card2
                }
            }
            
            anki_request('updateModelTemplates',
                model={
                    'name': model_name,
                    'templates': templates
                }
            )
            print(f"  ✓ 已更新卡片模板")
        except Exception as e:
            print(f"  ⚠ 无法使用 updateModelTemplates: {e}")
            print(f"  尝试使用其他方法...")
            
            # 尝试使用 modelTemplates 获取当前模板结构
            try:
                current_templates = anki_request('modelTemplates', modelName=model_name)
                print(f"  当前模板: {current_templates}")
            except Exception as e2:
                print(f"  无法获取当前模板: {e2}")
        
        # 更新 CSS 样式
        try:
            anki_request('updateModelStyling',
                model={
                    'name': model_name,
                    'css': card_template.css_style
                }
            )
            print(f"  ✓ 已更新 CSS 样式")
        except Exception as e:
            print(f"  ✗ 更新 CSS 失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ 更新失败: {e}")
        return False

def main():
    print("=" * 70)
    print("更新 Anki 模型模板")
    print("=" * 70)
    
    # 获取所有语言的模板
    templates = CardTemplate.objects.select_related('language').all()
    
    print(f"\n找到 {templates.count()} 个模板\n")
    
    for card_template in templates:
        lang_name = card_template.language.name
        lang_code = card_template.language.code
        
        # 模型名称格式: 中文-(R/L), Français-(R/L), etc.
        model_name = f"{card_template.language.native_name}-(R/L)"
        
        print(f"\n处理: {lang_name} ({lang_code})")
        print(f"  模型名称: {model_name}")
        
        success = update_model_templates(model_name, card_template)
        
        if success:
            print(f"  ✓ 成功")
        else:
            print(f"  ✗ 失败")
    
    print("\n" + "=" * 70)
    print("完成!")
    print("\n注意: 如果无法自动更新模板，你可能需要:")
    print("1. 删除 Anki 中的旧模型 (Tools → Manage Note Types)")
    print("2. 重新创建一张卡片以自动创建新模型")
    print("=" * 70)

if __name__ == '__main__':
    main()
