#!/usr/bin/env python3
"""
檢查 Anki 中實際的 CSS 內容以診斷問題
"""

import requests
import json

def get_model_styling(model_name):
    """獲取模型的完整 CSS 樣式"""
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

def main():
    # 檢查一個模型的 CSS
    model_name = '中文-(R/L)'
    css_content = get_model_styling(model_name)
    
    if css_content:
        print(f"模型 {model_name} 的完整 CSS 內容：")
        print("=" * 80)
        print(css_content)
        print("=" * 80)
        
        # 查找相關的 CSS 類別
        classes = ['.eB', '.eg', '.Verbform', '.extend']
        
        for css_class in classes:
            if css_class in css_content:
                print(f"\n找到 {css_class} 類別")
                
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
                print(f"內容: {class_content}")
            else:
                print(f"\n未找到 {css_class} 類別")
    else:
        print(f"無法獲取模型 {model_name} 的 CSS 樣式")

if __name__ == "__main__":
    main()