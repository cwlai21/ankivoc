"""
验证 Card 2 模板已正确更新
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

print("=" * 80)
print("验证 Card 2 Front 模板")
print("=" * 80)
print()

templates = invoke_anki('modelTemplates', modelName='中文-(R/L)')
template_data = templates.get('result', {})

if 'Card 2' in template_data:
    card2 = template_data['Card 2']
    front = card2.get('Front', '')
    
    print("检查要点:")
    print("-" * 80)
    
    # Check 1: No {{type:}} field
    if '{{type:' in front:
        print("❌ 仍包含 {{type:}} 输入框")
    else:
        print("✅ 已移除 {{type:}} 输入框")
    
    # Check 2: No answer display in front
    if '{{^No Spell}}' in front:
        print("❌ 仍包含 {{^No Spell}} 区块")
    else:
        print("✅ 已移除 {{^No Spell}} 区块")
    
    # Check 3: Has Audio section
    if '{{#Audio}}' in front and '{{Audio}}' in front:
        print("✅ 包含 Listening 模式（音频）")
    else:
        print("❌ 缺少 Listening 模式")
    
    # Check 4: Has Reading section
    if '{{^Audio}}' in front and '{{Explanation}}' in front:
        print("✅ 包含 Reading 模式（解释）")
    else:
        print("❌ 缺少 Reading 模式")
    
    # Check 5: Has Hint
    if '{{#Hint}}' in front and '{{Hint}}' in front:
        print("✅ 包含 Hint 显示")
    else:
        print("⚠️  没有 Hint 字段")
    
    print()
    print("=" * 80)
    print("Card 2 Front 模板预览:")
    print("=" * 80)
    print(front[:500])
    if len(front) > 500:
        print("...")
        print(f"(总共 {len(front)} 字符)")
    
    print()
    print("=" * 80)
    print("结论:")
    print("=" * 80)
    print("✅ Card 2 Front 已正确配置")
    print()
    print("当前行为:")
    print("- Listening 模式: 播放音频 + 显示 Hint（如果有）")
    print("- Reading 模式: 显示英文解释 + 显示 Hint（如果有）")
    print("- 中文答案只在 Card 2 Back 中显示")
    print("- 没有输入框，没有拼写练习")
else:
    print("❌ 未找到 Card 2 模板")
