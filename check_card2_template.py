"""
获取 Card 2 的完整模板
"""
import json
import urllib.request
import re

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

#Get templates
print("=" * 80)
print("Card 2 模板内容:")
print("=" * 80)
templates = invoke_anki('modelTemplates', modelName='中文-(R/L)')
template_data = templates.get('result', {})

if 'Card 2' in template_data:
    card2 = template_data['Card 2']
    front = card2.get('Front', '')
    back = card2.get('Back', '')
    
    print("\n【Front Template】")
    print("=" * 80)
    print(front)
    
    print("\n\n【Back Template】")
    print("=" * 80)
    print(back)
    
    # Search for 'example' or 'sample' (excluding 'exemple')
    print("\n\n【检查结果】")
    print("=" * 80)
    
    # Front template
    if re.search(r'example', front, re.IGNORECASE):
        matches = re.finditer(r'.{0,100}example.{0,100}', front, re.IGNORECASE)
        for match in matches:
            context = match.group()
            if 'exemple' not in context.lower():
                print(f"⚠️ Front 包含 'example': {context}")
    else:
        print("✓ Front 不包含 'example' 文本")
    
    if re.search(r'sample', front, re.IGNORECASE):
        matches = re.finditer(r'.{0,100}sample.{0,100}', front, re.IGNORECASE)
        for match in matches:
            print(f"⚠️ Front 包含 'sample': {match.group()}")
    else:
        print("✓ Front 不包含 'sample' 文本")
    
    # Back template
    if re.search(r'example', back, re.IGNORECASE):
        matches = re.finditer(r'.{0,100}example.{0,100}', back, re.IGNORECASE)
        for match in matches:
            context = match.group()
            if 'exemple' not in context.lower():
                print(f"⚠️ Back 包含 'example': {context}")
    else:
        print("✓ Back 不包含 'example' 文本")
    
    if re.search(r'sample', back, re.IGNORECASE):
        matches = re.finditer(r'.{0,100}sample.{0,100}', back, re.IGNORECASE)
        for match in matches:
            print(f"⚠️ Back 包含 'sample': {match.group()}")
    else:
        print("✓ Back 不包含 'sample' 文本")
    
    print()
    print("=" * 80)
    print("结论:")
    print("=" * 80)
    print("模板本身不包含 'example' 或 'sample' 文本。")
    print("问题可能是 Anki 的预览功能显示的占位符。")
    print()
    print("建议:")
    print("1. 在 Anki 中打开实际卡片（不是模板编辑器）")
    print("2. 学习这张卡片，看看 Card 2 是否显示 'example'/'sample'")
    print("3. 如果只在模板编辑器预览中出现，这是 Anki 的默认行为")
else:
    print("未找到 Card 2 模板")
