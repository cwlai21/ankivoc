# Card 2 (Listening/Spelling) Template Update - Complete Guide

## 🎯 Overview

This update adds interactive typing functionality to Card 2 (Listening/Spelling cards) across all language models. Card 2 now features:

- **Typing practice**: Type the answer instead of just revealing it
- **Conditional display**: Different behavior when audio exists vs. when it doesn't
- **No Spell field**: Toggle typing on/off for specific cards
- **Dark theme**: Consistent styling with Card 1

## ✅ What Was Changed

### 1. Database Schema (languages/models.py)
Added two new fields to `CardTemplate` model:
- `front_template_card2`: Card 2 front template (Listening/Spelling)
- `back_template_card2`: Card 2 back template

### 2. Field Definitions (cards/services/pipeline.py)
Added `No Spell` field to control typing functionality:
- When empty: Typing enabled (default)
- When contains any text: Typing disabled for that specific card

### 3. Card 2 Template Generation (cards/services/pipeline.py)
Created rich Card 2 templates with:
- Conditional logic: `{{#Audio}}` vs `{{^Audio}}`
- Typing input: `{{type:TARGET_LANGUAGE}}`
- No Spell control: `{{^No Spell}}...{{/No Spell}}`
- Title bars: "Listening & Spelling" or "Reading & Spelling"
- Hint field support
- Dark theme styling

### 4. AnkiConnect Integration (cards/services/anki_connect.py)
Updated `create_model_if_missing` to use stored Card 2 templates:
- Checks for `front_template_card2` and `back_template_card2`
- Falls back to simple format if templates not available
- Maintains backward compatibility

## 📋 Files Modified

1. `/backend/languages/models.py` - Added Card 2 template fields
2. `/backend/cards/services/pipeline.py` - Added No Spell field & Card 2 templates
3. `/backend/cards/services/anki_connect.py` - Use stored Card 2 templates
4. Migration: `languages/0005_cardtemplate_back_template_card2_and_more.py`

## 📋 Helper Scripts Created

1. **update_card2_templates.py** - Updates existing templates in database
2. **show_card2_templates.py** - Displays templates for copying to Anki
3. **test_card2_templates.py** - Tests template configuration

## 🔧 Card 2 Template Structure

### When Audio Exists (Listening Mode):
```
📱 Title: "Listening & Spelling"
🔊 Audio player
💡 Hint (if present)
⌨️  Typing input box (if No Spell empty)
```

### When Audio Missing (Reading Mode):
```
📱 Title: "Reading & Spelling"
📝 Explanation text
💡 Hint (if present)
⌨️  Typing input box (if No Spell empty)
```

## 📝 How to Apply to Existing Anki Models

### Method 1: Manual Update (Preserves existing cards)

1. **Run display script**:
   ```bash
   cd /Users/cwlai/LangChain_AI/backend
   python show_card2_templates.py
   ```

2. **Update each model in Anki**:
   - Open Anki → Tools → Manage Note Types
   - Select model (中文-(R/L), Français-(R/L), etc.)
   - Click "Cards..."
   - Select "Card 2" from left panel
   - Copy front template from script output → Paste in "Front Template"
   - Copy back template from script output → Paste in "Back Template"
   - Click "Save"

3. **Add No Spell field**:
   - In Manage Note Types, select model
   - Click "Fields..."
   - Click "Add"
   - Name: `No Spell`
   - Click "Save"

4. **Repeat for all language models**

### Method 2: Delete & Recreate (Fresh start)

1. **In Anki**:
   - Back up your collection first!
   - Tools → Manage Note Types
   - Delete existing models: 中文-(R/L), Français-(R/L), etc.

2. **Generate new cards**:
   - Use your Django app to create new cards
   - System will automatically create models with new Card 2 templates
   - Includes No Spell field automatically

## 🧪 Testing

Run the test script to verify templates:
```bash
cd /Users/cwlai/LangChain_AI/backend
python test_card2_templates.py
```

Test results should show:
- ✅ Typing functionality present
- ✅ Conditional Audio display
- ✅ No Spell field integration
- ✅ Hint field display
- ✅ Appropriate title bars
- ✅ No Spell in field definitions

## 🎮 How to Use Card 2

### For Normal Cards (with typing):
1. Review card in Anki
2. Card 2 shows either audio (listening) or explanation (reading)
3. Type the answer in the input box
4. Press Enter or click "Show Answer"
5. Anki shows what you typed vs. the correct answer

### To Disable Typing for Specific Cards:
1. Edit the card in Anki
2. Add any text (e.g., "yes" or "1") to the "No Spell" field
3. Save
4. Card 2 will now show the word directly without typing input

## 🔄 Future Card Generation

All newly generated cards will automatically:
- Include No Spell field (empty by default)
- Use rich Card 2 templates with typing
- Have conditional audio/non-audio display
- Match dark theme styling

## 📊 Current Status

**Database**: ✅ Updated (Chinese & French templates have Card 2)
**Code**: ✅ Updated (pipeline & anki_connect use Card 2 templates)
**Field Definitions**: ✅ Updated (No Spell field added)
**Migration**: ✅ Applied (0005_cardtemplate_back_template_card2_and_more)
**Tests**: ✅ Passing (all Card 2 features verified)

**Anki Models**: ⚠️ Requires manual update (see Method 1 above)

## 🎨 Template Features Summary

| Feature | Card 1 (Reading) | Card 2 (Listening/Spelling) |
|---------|------------------|----------------------------|
| Shows target word | ✅ Front | ❌ Hidden (must type) |
| Audio playback | ✅ Yes | ✅ Yes (if available) |
| Typing practice | ❌ No | ✅ Yes |
| Shows explanation | ✅ Back | ✅ Front (if no audio) |
| Examples | ✅ Back | ❌ Only on back |
| Extend section | ✅ Back | ❌ Only on back |
| Hint | ❌ No | ✅ Yes (front) |
| No Spell control | N/A | ✅ Yes |

## 💡 Tips

- Leave "No Spell" field **empty** for most cards to enable typing practice
- Use "No Spell" field for:
  - Very long phrases that are hard to type
  - Phrases with special characters
  - Cards you want to review without typing

- The system automatically detects if audio exists:
  - With audio → "Listening & Spelling" mode
  - Without audio → "Reading & Spelling" mode

## 🐛 Troubleshooting

**Templates not showing in Anki?**
- Run `python show_card2_templates.py` to see templates
- Check that you're editing the correct model name
- Verify you selected "Card 2" (not Card 1)

**Typing not working in Anki?**
- Check "No Spell" field is empty
- Verify `{{type:LANGUAGE}}` is in front template
- Check `{{^No Spell}}` wraps the typing section

**New cards don't have Card 2 templates?**
- Delete and recreate the model in Anki
- System will automatically use new templates
- Or manually update existing models (Method 1)

## 📚 References

- Django migration: `languages/migrations/0005_cardtemplate_back_template_card2_and_more.py`
- Helper scripts: `backend/update_card2_templates.py`, `show_card2_templates.py`, `test_card2_templates.py`
- Modified files: `languages/models.py`, `cards/services/pipeline.py`, `cards/services/anki_connect.py`
