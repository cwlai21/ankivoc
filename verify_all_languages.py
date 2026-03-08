"""
验证所有语言的 Card 2 模板
"""
import json
import urllib.request

def invoke_anki(action, **params):
    """Call AnkiConnect API."""
    payload = {
        'action': action,
        'version': 6,
        'params': params
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request('http://localhost:8765', data=data, headers={'Content-Type': 'application/json'})
    response = urllib.request.urlopen(req)
    return json.loads(response.read().decode('utf-8'))

# Language models to check
language_models = [
    ('中文-(R/L)', 'Chinese'),
    ('Français-(R/L)', 'French'),
    ('English-(R/L)', 'English'),
    ('Deutsch-(R/L)', 'German'),
    ('日本語-(R/L)', 'Japanese'),
    ('한국어-(R/L)', 'Korean'),
    ('Español-(R/L)', 'Spanish')
]

print("=" * 80)
print("验证所有语言的 Card 2 Front 模板")
print("=" * 80)
print()

all_pass = True

for model_name, lang_name in language_models:
    print(f"【{lang_name}】({model_name})")
    
    try:
        templates = invoke_anki('modelTemplates', modelName=model_name)
        template_data = templates.get('result', {})
        
        if 'Card 2' not in template_data:
            print("  ❌ Card 2 模板不存在")
            all_pass = False
            continue
        
        front = template_data['Card 2'].get('Front', '')
        
        # Check 1: No {{type:}} field
        has_type = '{{type:' in front
        
        # Check 2: No {{^No Spell}} block
        has_no_spell = '{{^No Spell}}' in front
        
        # Check 3: Has Audio section
        has_audio = '{{#Audio}}' in front and '{{Audio}}' in front
        
        # Check 4: Has Reading section
        has_reading = '{{^Audio}}' in front and '{{Explanation}}' in front
        
        if has_type:
            print("  ❌ 仍包含 {{type:}} 输入框")
            all_pass = False
        else:
            print("  ✅ 已移除 {{type:}} 输入框")
        
        if has_no_spell:
            print("  ❌ 仍包含 {{^No Spell}} 区块")
            all_pass = False
        else:
            print("  ✅ 已移除 {{^No Spell}} 区块")
        
        if has_audio:
            print("  ✅ 包含 Listening 模式")
        else:
            print("  ⚠️  缺少 Listening 模式")
        
        if has_reading:
            print("  ✅ 包含 Reading 模式")
        else:
            print("  ⚠️  缺少 Reading 模式")
        
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        all_pass = False
    
    print()

print("=" * 80)
if all_pass:
    print("✅ 所有语言的 Card 2 模板验证通过！")
else:
    print("❌ 部分语言的模板验证失败")
print("=" * 80)
print()
print("所有语言现在的 Card 2 行为:")
print("- Front: 只显示音频/解释和 Hint")
print("- Back: 显示完整答案和例句")
print("- 没有输入框，没有拼写练习")
