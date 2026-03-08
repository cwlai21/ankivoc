#!/usr/bin/env python3
"""
驗證例句背景色是否已成功移除
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

def check_background_removed(css_content):
    """檢查 .eB 類別的背景色是否已移除"""
    if '.eB' in css_content:
        start = css_content.find('.eB')
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
    print("驗證例句背景色移除狀況")
    print("=" * 80)
    
    # 檢查一個模型作為范例
    model_name = '中文-(R/L)'
    css_content = get_model_styling(model_name)
    
    if css_content:
        background_removed, bg_value = check_background_removed(css_content)
        
        print(f"模型: {model_name}")
        if background_removed:
            print(f"✓ 例句背景色已成功移除")
            print(f"  背景色設定: {bg_value}")
        else:
            print(f"❌ 例句仍有背景色")
            print(f"  當前背景色: {bg_value}")
        
        print("\n檢查所有語言模型...")
        models = {
            'Chinese (Mandarin)': '中文-(R/L)',
            'French': 'Français-(R/L)',
            'English': 'English-(R/L)',
            'German': 'Deutsch-(R/L)',
            'Japanese': '日本語-(R/L)',
            'Korean': '한국어-(R/L)',
            'Spanish': 'Español-(R/L)'
        }
        
        all_success = True
        for language, model in models.items():
            css = get_model_styling(model)
            if css:
                removed, value = check_background_removed(css)
                if removed:
                    print(f"✓ {language}: 背景色已移除 ({value})")
                else:
                    print(f"❌ {language}: 仍有背景色 ({value})")
                    all_success = False
            else:
                print(f"❌ {language}: 無法獲取樣式")
                all_success = False
        
        print("\n" + "=" * 80)
        if all_success:
            print("🎉 所有語言的例句背景色都已成功移除！")
            print("   例句現在將顯示為透明背景，不再有藍色框框。")
        else:
            print("❌ 部分語言的背景色移除失敗，請重新檢查同步狀態。")
        print("=" * 80)
        
    else:
        print(f"❌ 無法獲取模型 {model_name} 的樣式，請確認 Anki 正在運行。")

if __name__ == "__main__":
    main()