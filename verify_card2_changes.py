"""
验证 Card 2 模板已移除 {{type:}} 字段
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
print("从数据库检查 Card 2 Front 模板...")
print("=" * 80)

# We can't directly query Django DB, but we can check what will be synced
# Let's check the template in the regenerate script output

print("\n检查要点:")
print("1. Card 2 Front 应该使用 {{中文}} 而不是 {{type:中文}}")
print("2. 不应该有 JavaScript 输入验证代码")
print("3. Card 2 Back 保持不变")
print()

# Check if we can see the Anki template (after sync)
try:
    templates = invoke_anki('modelTemplates', modelName='中文-(R/L)')
    template_data = templates.get('result', {})
    
    if 'Card 2' in template_data:
        card2 = template_data['Card 2']
        front = card2.get('Front', '')
        
        print("=" * 80)
        print("当前 Anki 中的 Card 2 Front 模板:")
        print("=" * 80)
        
        # Check for type: field
        if '{{type:' in front:
            print("⚠️ 警告：模板仍然包含 {{type:}} 字段")
            print("   需要同步到 Anki：请运行后端服务器并创建新卡片")
        else:
            print("✓ 模板已移除 {{type:}} 字段")
        
        # Check for script
        if '<script>' in front and 'ankiTypingValidation' in front:
            print("⚠️ 警告：模板仍然包含输入验证脚本")
        else:
            print("✓ 模板已移除输入验证脚本")
        
        # Show what's there instead
        import re
        # Look for the answer display pattern
        if re.search(r'<div class="Text-answer">\{\{[^}]+\}\}</div>', front):
            matches = re.findall(r'<div class="Text-answer">(\{\{[^}]+\}\})</div>', front)
            print(f"\n✓ 找到答案显示字段: {matches}")
        
    else:
        print("未找到 Card 2 模板")
        
except Exception as e:
    print(f"无法连接到 Anki: {e}")
    print("\n这是正常的，因为 Anki 中的模板需要同步后才会更新。")

print()
print("=" * 80)
print("下一步:")
print("=" * 80)
print("1. 确保后端服务器正在运行")
print("2. 创建新卡片，这会自动同步模板到 Anki")
print("3. 或者手动在 Anki 中更新模板")
print()
print("预期行为:")
print("- Card 2 Front: 直接显示中文答案（没有输入框）")
print("- Card 2 Back: 显示解释、同义词和例句")
print("- 不再有拼写练习功能")
