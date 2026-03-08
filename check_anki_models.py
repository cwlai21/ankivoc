"""
检查 Anki 中的模型
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
print("Anki 中的所有模型:")
print("=" * 80)

models = invoke_anki('modelNames')
model_list = models.get('result', [])

for model in sorted(model_list):
    print(f"  - {model}")
    
print()
print(f"总共 {len(model_list)} 个模型")

# Check if Chinese model exists
chinese_models = [m for m in model_list if '中文' in m or 'zh' in m.lower()]
if chinese_models:
    print()
    print("找到的中文相关模型:")
    for m in chinese_models:
        print(f"  - {m}")
