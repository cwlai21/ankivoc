#!/usr/bin/env python3
"""
驗證 CSS 字體大小和行長度限制的改進是否正確應用到所有模板
"""

import requests
import sys

def check_anki_connection():
    """檢查 Anki 連接"""
    try:
        response = requests.post(
            'http://localhost:8765',
            json={
                "action": "version",
                "version": 6
            },
            timeout=5
        )
        return response.status_code == 200
    except requests.RequestException:
        return False

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

def check_css_improvements(css_content, model_name):
    """檢查 CSS 改進是否已應用"""
    improvements = {
        '.eB': {'font-size': '22px', 'max-width': '800px', 'word-wrap': 'break-word'},
        '.eg': {'font-size': '20px', 'max-width': '800px', 'word-wrap': 'break-word'},
        '.Verbform': {'font-size': '20px', 'max-width': '800px', 'word-wrap': 'break-word'},
        '.extend': {'font-size': '18px', 'max-width': '800px', 'word-wrap': 'break-word'}
    }
    
    results = {}
    
    for css_class, properties in improvements.items():
        results[css_class] = {}
        
        # 查找該 CSS class
        if css_class in css_content:
            # 提取該 class 的內容
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
            
            # 檢查每個屬性
            for prop, expected_value in properties.items():
                if f"{prop}:" in class_content:
                    # 提取實際值
                    prop_start = class_content.find(f"{prop}:")
                    line_end = class_content.find(';', prop_start)
                    if line_end == -1:
                        line_end = class_content.find('}', prop_start)
                    
                    actual_value = class_content[prop_start:line_end].split(':')[1].strip()
                    
                    results[css_class][prop] = {
                        'expected': expected_value,
                        'actual': actual_value,
                        'match': expected_value in actual_value
                    }
                else:
                    results[css_class][prop] = {
                        'expected': expected_value,
                        'actual': 'Not found',
                        'match': False
                    }
        else:
            for prop, expected_value in properties.items():
                results[css_class][prop] = {
                    'expected': expected_value,
                    'actual': 'Class not found',
                    'match': False
                }
    
    return results

def main():
    print("=" * 80)
    print("驗證 CSS 字體大小和行長度限制改進")
    print("=" * 80)
    
    # 檢查 Anki 連接
    if not check_anki_connection():
        print("❌ 無法連接到 Anki。請確保 Anki 正在運行並啟用了 AnkiConnect 外掛。")
        sys.exit(1)
    
    print("✓ Anki 連接正常")
    print()
    
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
    
    all_passed = True
    
    for language, model_name in models.items():
        print(f"【{language}】")
        print(f"  模型: {model_name}")
        
        css_content = get_model_styling(model_name)
        
        if css_content is None:
            print(f"  ❌ 無法獲取模型樣式")
            all_passed = False
            continue
        
        if not css_content:
            print(f"  ❌ 模型樣式為空")
            all_passed = False
            continue
        
        # 檢查 CSS 改進
        results = check_css_improvements(css_content, model_name)
        
        model_passed = True
        for css_class, properties in results.items():
            class_passed = all(prop['match'] for prop in properties.values())
            
            if class_passed:
                print(f"  ✓ {css_class}: 字體大小和行長度限制已正確應用")
            else:
                print(f"  ❌ {css_class}: 存在問題")
                model_passed = False
                
                for prop, details in properties.items():
                    if not details['match']:
                        print(f"    - {prop}: 期望 '{details['expected']}', 實際 '{details['actual']}'")
        
        if model_passed:
            print(f"  ✓ 所有 CSS 改進已正確應用")
        else:
            all_passed = False
        
        print()
    
    print("=" * 80)
    if all_passed:
        print("🎉 驗證成功！所有模型的 CSS 改進都已正確應用：")
        print("   • 字體大小已增大（.eB: 22px, .eg: 20px, .Verbform: 20px, .extend: 18px）")
        print("   • 行長度限制已添加（max-width: 800px）")
        print("   • 自動換行已啟用（word-wrap: break-word）")
    else:
        print("❌ 驗證失敗！部分模型的 CSS 改進未正確應用。")
        print("   請檢查上述錯誤並重新同步模板。")
    print("=" * 80)

if __name__ == "__main__":
    main()