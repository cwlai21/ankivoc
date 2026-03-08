"""
检查 Card 2 预览问题的脚本
Check for 'example' and 'sample' text in actual card data
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

# Get all notes from Chinese deck
print("=" * 80)
print("检查 Anki 中的卡片数据...")
print("=" * 80)

# Find notes in Chinese deck
result = invoke_anki('findNotes', query='deck:"中文-(R/L)"')
note_ids = result.get('result', [])

print(f"找到 {len(note_ids)} 张卡片")
print()

if note_ids:
    # Get details of first few notes
    notes_info = invoke_anki('notesInfo', notes=note_ids[:5])
    notes = notes_info.get('result', [])
    
    for i, note in enumerate(notes, 1):
        print(f"【卡片 {i}】Note ID: {note['noteId']}")
        print(f"  模型: {note['modelName']}")
        
        fields = note['fields']
        
        # Check key fields
        zh_value = fields.get('中文', {}).get('value', '')
        expl_value = fields.get('Explanation', {}).get('value', '')
        
        print(f"  中文字段: {zh_value[:50]}")
        print(f"  Explanation字段: {expl_value[:50]}")
        
        # Check for 'example' or 'sample' in any field
        problem_found = False
        for field_name, field_data in fields.items():
            field_value = field_data.get('value', '')
            if 'example' in field_value.lower() and 'exemple' not in field_value.lower():
                print(f"  ⚠️ 字段 '{field_name}' 包含 'example': {field_value[:100]}")
                problem_found = True
            if 'sample' in field_value.lower():
                print(f"  ⚠️ 字段 '{field_name}' 包含 'sample': {field_value[:100]}")
                problem_found = True
        
        if not problem_found:
            print(f"  ✓ 没有发现 'example' 或 'sample' 文本")
        
        print()

# Check template details
print("=" * 80)
print("检查模板中的 {{type:}} 字段...")
print("=" * 80)

model_names = invoke_anki('modelNames')
print(f"可用模型: {model_names.get('result', [])}")
print()

# Get Chinese model
zh_model = invoke_anki('modelFieldNames', modelName='中文-(R/L)')
field_names = zh_model.get('result', [])
print(f"中文模型的字段: {field_names}")
print()

# Get templates
templates = invoke_anki('modelTemplates', modelName='中文-(R/L)')
template_data = templates.get('result', {})

if 'Card 2' in template_data:
    card2 = template_data['Card 2']
    front = card2.get('Front', '')
    back = card2.get('Back', '')
    
    # Check for {{type:}} fields
    import re
    type_fields = re.findall(r'\{\{type:([^}]+)\}\}', front)
    print(f"Card 2 Front 中的 {{{{type:}}}} 字段: {type_fields}")
    
    # Check if 'example' or 'sample' appear as literal text
    if 'example' in front.lower() and 'exemple' not in front.lower():
        print("⚠️ Front 模板包含 'example' 字面文本")
        # Find context
        for match in re.finditer(r'.{0,50}example.{0,50}', front, re.IGNORECASE):
            if 'exemple' not in match.group().lower():
                print(f"  上下文: {match.group()}")
    
    if 'sample' in front.lower():
        print("⚠️ Front 模板包含 'sample' 字面文本")
        for match in re.finditer(r'.{0,50}sample.{0,50}', front, re.IGNORECASE):
            print(f"  上下文: {match.group()}")
    
    if 'example' in back.lower() and 'exemple' not in back.lower():
        print("⚠️ Back 模板包含 'example' 字面文本")
        for match in re.finditer(r'.{0,50}example.{0,50}', back, re.IGNORECASE):
            if 'exemple' not in match.group().lower():
                print(f"  上下文: {match.group()}")
    
    if 'sample' in back.lower():
        print("⚠️ Back 模板包含 'sample' 字面文本")
        for match in re.finditer(r'.{0,50}sample.{0,50}', back, re.IGNORECASE):
            print(f"  上下文: {match.group()}")

print()
print("=" * 80)
print("检查完成")
print("=" * 80)
