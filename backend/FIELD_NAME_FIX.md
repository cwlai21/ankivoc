# Card 2 Field Name Fix

## 问题诊断

### 根本原因
Card 2（Listening/Spelling）模板引用的字段名与实际字段定义不匹配：
- **字段定义** 使用 `Language.native_name`（如中文使用 `"中文"`）
- **Card 2模板** 使用 `Language.name`（如中文使用 `"Chinese (Mandarin)"`）

### 错误链
1. 系统尝试创建Anki模型 `中文-(R/L)`
2. AnkiConnect验证Card 2模板，发现 `{{type:Chinese (Mandarin)}}` 字段
3. 但模型字段列表中只有 `中文`，没有 `Chinese (Mandarin)`
4. AnkiConnect拒绝：`Field '⁨Chinese (Mandarin)⁩' not found`
5. 创建失败后，系统fallback到法语模型 `Français-(R/L)`
6. 使用法语模型创建中文卡片时，所有字段名不匹配（`中文` vs `Français`）
7. 最终错误：`cannot create note because it is empty`

### 关键日志证据
```
2026-03-08 16:04:23,744 [WARNING] createModel attempt failed: 
  Card template ⁨2⁩ in note type '⁨中文-(R/L)⁩' has a problem.
  Field '⁨Chinese (Mandarin)⁩' not found.

2026-03-08 16:04:23,834 [WARNING] Model "中文-(R/L)" not present in Anki; 
  falling back to "Français-(R/L)"

2026-03-08 16:04:23,915 [ERROR] Card #174 failed: 
  AnkiConnect error: cannot create note because it is empty
```

## 解决方案

### 已实施的修复
1. **重新生成所有CardTemplate**
   - 使用 `regenerate_all_templates.py` 
   - 所有模板现在统一使用 `native_name`
   - 7种语言全部更新并验证

2. **字段名称映射**
   | 语言 | 老字段名 | 新字段名（正确） |
   |------|---------|-----------------|
   | 中文 | Chinese (Mandarin) | 中文 |
   | 法语 | Français | Français |
   | 西班牙语 | Spanish | Español |
   | 德语 | German | Deutsch |
   | 日语 | Japanese | 日本語 |
   | 韩语 | Korean | 한국어 |
   | 英语 | English | English |

3. **验证检查**
   ```
   Processing Chinese (Mandarin) (zh)...
     ✓ Updated template
     Model: 中文-(R/L)
     First field: 中文
     Card 2 type fields: ['中文', '中文']
     ✓ Type field matches first field name
   ```

### 文件变更
- `backend/regenerate_all_templates.py` - 模板重建脚本（新增）
- `backend/cleanup_anki_models.py` - Anki模型清理脚本（新增）
- Database: 所有 `CardTemplate` 记录已更新

## 测试步骤

### 1. 验证模板
```bash
cd /Users/cwlai/LangChain_AI/backend
source ../.venv/bin/activate
python manage.py shell -c "
from languages.models import CardTemplate
import re
ct = CardTemplate.objects.get(language__code='zh')
print('Fields:', ct.fields_definition[:3])
print('Type fields:', re.findall(r'\{\{type:([^}]+)\}\}', ct.front_template_card2))
print('Match:', ct.fields_definition[0] in ct.front_template_card2)
"
```

**预期输出：**
```
Fields: ['中文', 'Explanation', 'Synonyme']
Type fields: ['中文', '中文']
Match: True
```

### 2. 创建测试卡片
通过API创建一个中文卡片（例如 "手術室"）

**预期结果：**
- ✅ 成功创建Anki模型 `中文-(R/L)`
- ✅ 成功添加卡片到Anki
- ✅ 卡片包含Card 1（阅读）和Card 2（听写）
- ✅ Card 2显示打字输入框

### 3. 检查Anki
打开Anki桌面应用：
1. 查看 `中文::Vocabulary` 牌组
2. 验证卡片存在
3. 点击"学习"，测试Card 2的打字功能

## 技术细节

### AnkiConnect模型创建
```python
{
  'modelName': '中文-(R/L)',
  'inOrderFields': [
    '中文',          # native_name
    'Explanation',
    'Synonyme',
    'Conjugaison/Gender',
    'Audio',
    ...
  ],
  'cardTemplates': [
    {'Name': 'Card 1', ...},
    {'Name': 'Card 2', 'Front': '...{{type:中文}}...'}  # 匹配！
  ]
}
```

### Card 2模板结构
```html
{{#Audio}}
  <div>Listening & Spelling</div>
  {{^No Spell}}
    {{type:中文}}  <!-- 正确：使用native_name -->
  {{/No Spell}}
{{/Audio}}

{{^Audio}}
  <div>Reading & Spelling</div>
  {{type:中文}}    <!-- 正确：使用native_name -->
{{/Audio}}
```

## 相关Commit
- `2ab6740` - Add Card 2 (Listening/Spelling) template with typing functionality
- `75a7ec8` - Fix: Ensure all template fields are defined when creating Anki models
- `2529ce7` - Fix: Regenerate CardTemplates with correct field names for Card 2

## 后续维护

### 添加新语言时
确保 `Language` 模型的 `native_name` 字段已填写，不要留空。如果为空，系统会fallback到 `name`，可能导致同样的字段不匹配问题。

### 修改模板时
在 `pipeline.py` 的 `_build_dual_card_template_entry()` 方法中修改模板。修改后需要运行：
```bash
python regenerate_all_templates.py
```

### 验证脚本
```bash
# 检查所有语言的字段一致性
python manage.py shell -c "
from languages.models import CardTemplate
import re
for ct in CardTemplate.objects.all():
    fields = re.findall(r'\{\{type:([^}]+)\}\}', ct.front_template_card2 or '')
    first = ct.fields_definition[0] if ct.fields_definition else None
    status = '✓' if fields and fields[0] == first else '✗'
    print(f'{status} {ct.language.code}: {first} vs {fields[0] if fields else None}')
"
```
