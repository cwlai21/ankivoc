"""
列出所有牌组和卡片
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

# Get all deck names
print("=" * 80)
print("所有牌组:")
print("=" * 80)
decks = invoke_anki('deckNames')
deck_list = decks.get('result', [])
for deck in sorted(deck_list):
    print(f"  - {deck}")
    
    # Count notes in each deck
    result = invoke_anki('findNotes', query=f'deck:"{deck}"')
    note_count = len(result.get('result', []))
    if note_count > 0:
        print(f"    ({note_count} 张卡片)")

print()
print("=" * 80)
print(f"总共 {len(deck_list)} 个牌组")
print("=" * 80)

# Find notes with Chinese model
print()
print("=" * 80)
print("查找使用 '中文-(R/L)' 模型的卡片:")
print("=" * 80)
result = invoke_anki('findNotes', query='note:"中文-(R/L)"')
note_ids = result.get('result', [])
print(f"找到 {len(note_ids)} 张卡片")

if note_ids:
    # Get first note details
    notes_info = invoke_anki('notesInfo', notes=note_ids[:1])
    notes = notes_info.get('result', [])
    
    if notes:
        note = notes[0]
        print(f"\n【示例卡片】Note ID: {note['noteId']}")
        fields = note['fields']
        for field_name, field_data in fields.items():
            value = field_data.get('value', '')[:100]
            if value:
                print(f"  {field_name}: {value}")
