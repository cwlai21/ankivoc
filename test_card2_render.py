"""
测试 Card 2 实际渲染的 HTML
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

# Find the Chinese card
result = invoke_anki('findNotes', query='note:"中文-(R/L)"')
note_ids = result.get('result', [])

if note_ids:
    note_id = note_ids[0]
    print(f"测试卡片 Note ID: {note_id}")
    print("=" * 80)
    
    # Get cards for this note
    cards_result = invoke_anki('findCards', query=f'nid:{note_id}')
    card_ids = cards_result.get('result', [])
    
    print(f"此笔记有 {len(card_ids)} 张卡片")
    print()
    
    if len(card_ids) >= 2:
        # Card 2 is the second card (index 1)
        card2_id = card_ids[1]
        
        print(f"Card 2 ID: {card2_id}")
        print()
        
        # Render card 2
        print("尝试渲染 Card 2...")
        print("注意：AnkiConnect 可能不支持完整的卡片渲染")
        print()
        
        # Get card info
        cards_info = invoke_anki('cardsInfo', cards=[card2_id])
        card_data = cards_info.get('result', [])
        
        if card_data:
            card = card_data[0]
            print("Card 2 信息:")
            print(f"  Question: {card.get('question', 'N/A')[:200]}")
            print(f"  Answer: {card.get('answer', 'N/A')[:200]}")
            
            # Check for 'example' or 'sample' in rendered HTML
            question_html = card.get('question', '')
            answer_html = card.get('answer', '')
            
            if 'example' in question_html.lower() and 'exemple' not in question_html.lower():
                print("\n⚠️ 渲染的 Question HTML 包含 'example'")
            if 'sample' in question_html.lower():
                print("\n⚠️ 渲染的 Question HTML 包含 'sample'")
            if 'example' in answer_html.lower() and 'exemple' not in answer_html.lower():
                print("\n⚠️ 渲染的 Answer HTML 包含 'example'")
            if 'sample' in answer_html.lower():
                print("\n⚠️ 渲染的 Answer HTML 包含 'sample'")
    else:
        print("此笔记少于 2 张卡片")
else:
    print("未找到中文卡片")

print()
print("=" * 80)
print("结论:")
print("=" * 80)
print("""
如果在卡片浏览器预览中看到 'example' 和 'sample'，
这是 Anki 的 {{type:}} 字段的默认预览行为。

{{type:}} 字段在不同情况下的表现：
1. 学习时：显示输入框，您可以输入答案
2. 复习后：显示 "您的答案 ↓ 正确答案"
3. 预览时：Anki 可能显示示例占位符

这不是模板错误，而是 Anki 的功能设计。

要验证卡片是否正常工作：
1. 在 Anki 中实际学习这张卡片（不是预览）
2. Card 2 应该显示：
   - Listening 模式：播放音频，输入中文
   - Reading 模式：显示英文，输入中文
3. 提交答案后，才会显示比较结果
""")
