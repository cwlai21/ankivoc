#!/usr/bin/env python3
"""
驗證例句和擴展內容的背景色是否都已成功移除
"""

import requests
import json

def get_model_styling(model_name):
    """獲取模型的 CSS 樣式"""
    try:
        response = requests.post(
            'http://localhost:8765',
            json={
                "action": "modelStyling",
                "version": 6,
                "params": {
                    "modelName": model_name
                }
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('result', {}).get('css', '')
        return None
    except requests.RequestException:
        return None

def check_background_removed(css_content, css_class):
    """檢查指定 CSS 類別的背景色是否已移除"""
    if css_class in css_content:
        start = css_content.find(css_class)
        brace_start = css_content.find('{', start)
        brace_count = 1
        current_pos = brace_start + 1
        
        while brace_count > 0 and current_pos < len(css_content):
            if css_content[current_pos] == '{':
                brace_count += 1
            elif css_content[current_pos] == '}':
                brace_count -= 1
            current_pos += 1
        
        class_content = css_content[brace_start:current_pos]
        
        # 檢查背景色設定
        if 'background-color: transparent' in class_content:
            return True, "transparent"
        elif 'background-color:' in class_content:
            # 提取背景色值
            bg_start = class_content.find('background-color:')
            line_end = class_content.find(';', bg_start)
            if line_end == -1:
                line_end = class_content.find('}', bg_start)
            bg_value = class_content[bg_start:line_end].split(':')[1].strip()
            return False, bg_value
        else:
            return True, "not specified (transparent by default)"
    
    return False, "Class not found"

def main():
    print("=" * 80)
    print("驗證例句(.eB)和擴展內容(.extend)背景色移除狀況")
    print("=" * 80)
    
    # 要檢查的模型
    models = {
        'Chinese (Mandarin)': '中文-(R/L)',
        'French': 'Français-(R/L)',
        'English': 'English-(R/L)',
        'German': 'Deutsch-(R/L)',
        'Japanese': '日本語-(R/L)',
        'Korean': '한국어-(R/L)',
        'Spanish': 'Español-(R/L)'
    }
    
    css_classes = {
        '.eB': '例句',
        '.extend': '擴展內容'
    }
    
    all_success = True
    
    for language, model_name in models.items():
        print(f"\n【{language}】")
        print(f"  模型: {model_name}")
        
        css_content = get_model_styling(model_name)
        
        if css_content is None:
            print(f"  ❌ 無法獲取模型樣式")
            all_success = False
            continue
        
        if not css_content:
            print(f"  ❌ 模型樣式為空")
            all_success = False
            continue
        
        # 檢查每個 CSS 類別
        model_success = True
        for css_class, class_name in css_classes.items():
            background_removed, bg_value = check_background_removed(css_content, css_class)
            
            if background_removed:
                print(f"  ✓ {class_name}({css_class}): 背景色已移除 ({bg_value})")
            else:
                print(f"  ❌ {class_name}({css_class}): 仍有背景色 ({bg_value})")
                model_success = False
        
        if not model_success:
            all_success = False
    
    print("\n" + "=" * 80)
    if all_success:
        print("🎉 所有語言的例句和擴展內容背景色都已成功移除！")
        print("   • 例句(.eB): 不再有藍色背景框框")
        print("   • 擴展內容(.extend): 不再有紫色/粉色背景框框")
        print("   所有內容現在都顯示為透明背景，看起來更簡潔!")
    else:
        print("❌ 部分語言的背景色移除失敗，請重新檢查同步狀態。")
    print("=" * 80)

if __name__ == "__main__":
    main()