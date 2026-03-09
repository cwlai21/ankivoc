# Explanation Language Selection Guide

## Overview

The system now automatically selects the **explanation language** based on your user profile preferences when creating vocabulary batches.

## How It Works

### 1. User Profile Settings

Each user has two language preferences in their profile:
- **Default Target Language**: The language you want to learn
- **Default Explanation Language**: The language used for translations and explanations

### 2. Automatic Selection Logic

When creating a new vocabulary batch:

#### Backend Logic (`cards/views.py`)

1. **User provides explanation language**: Use the provided language
2. **User doesn't provide explanation language**: Use user's `default_explanation_language`
3. **No default set**: Fall back to English (`en`)
4. **Conflict resolution**: If target language equals explanation language, automatically choose alternative:
   - Priority order: English → Traditional Chinese → French
   - Select first language that differs from target

#### Frontend Logic (`templates/cards/batch_create.html`)

- On page load: Auto-select user's preferred explanation language
- If target equals preference: Auto-select alternative language
- On target language change: Adjust explanation language if conflict occurs

### 3. Example Scenarios

#### Scenario A: User prefers Chinese explanations, learning French
```python
user.default_target_language = French (fr)
user.default_explanation_language = Chinese (zh)
```

**Batch Creation:**
- Target: French → Explanation: Chinese ✓ (user's preference)
- Target: Chinese → Explanation: English ✓ (auto-alternative)
- Target: English → Explanation: Chinese ✓ (user's preference)

#### Scenario B: User prefers English explanations, learning Chinese
```python
user.default_target_language = Chinese (zh)
user.default_explanation_language = English (en)
```

**Batch Creation:**
- Target: Chinese → Explanation: English ✓ (user's preference)
- Target: English → Explanation: Chinese ✓ (auto-alternative)
- Target: French → Explanation: English ✓ (user's preference)

#### Scenario C: No preferences set
```python
user.default_target_language = None
user.default_explanation_language = None
```

**Batch Creation:**
- Target: French → Explanation: English ✓ (system default)
- Target: English → Explanation: Chinese ✓ (auto-alternative)
- Target: Chinese → Explanation: English ✓ (system default)

## Setting User Preferences

### Via Django Admin

```python
from accounts.models import User
from languages.models import Language

user = User.objects.get(username='your_username')
user.default_target_language = Language.objects.get(code='fr')
user.default_explanation_language = Language.objects.get(code='zh')
user.save()
```

### Via API (Future Enhancement)

A profile update endpoint could allow users to set these preferences:

```
PATCH /api/v1/auth/profile/
{
  "default_target_language": "fr",
  "default_explanation_language": "zh"
}
```

## API Changes

### POST /api/v1/cards/batches/

#### Request (Before)
```json
{
  "target_language": "fr",
  "explanation_language": "en",  // Required
  "vocabulary": ["bonjour", "merci"]
}
```

#### Request (After)
```json
{
  "target_language": "fr",
  "explanation_language": "en",  // Optional - uses user preference if omitted
  "vocabulary": ["bonjour", "merci"]
}
```

#### Response (Error Case)
```json
{
  "error": "Cannot determine explanation language",
  "message": "Target language matches your preferred explanation language. Please specify a different explanation language."
}
```

## Frontend Behavior

### Language Selection Dropdowns

1. **Target Language**: User selects the language they want to learn
2. **Explanation Language**: 
   - Auto-populated with user's preference
   - Auto-adjusted if conflicts with target
   - User can manually override

### Validation

- Target and explanation languages must be different
- Submit button is disabled until valid selection is made
- Real-time validation as user changes selections

## Benefits

✅ **Convenience**: Users don't need to select explanation language every time  
✅ **Intelligence**: System automatically handles conflicts  
✅ **Flexibility**: Users can still manually override the default  
✅ **Consistency**: Same language preferences across all batches  

## Technical Implementation

### Files Modified

1. **`cards/serializers.py`**
   - Made `explanation_language` optional in `VocabularyBatchCreateSerializer`
   - Updated validation to allow `None` value

2. **`cards/views.py`**
   - Added logic to use `request.user.default_explanation_language`
   - Implemented conflict resolution with fallback alternatives

3. **`templates/cards/batch_create.html`**
   - Auto-select user's preferred explanation language on load
   - Adjust explanation language when target language changes
   - Handle conflicts automatically

### Database Schema

No changes required - uses existing fields:
- `users.default_target_language` (ForeignKey to Language)
- `users.default_explanation_language` (ForeignKey to Language)

## Testing

### Test Case 1: Use User Preference
```bash
# Setup
user.default_explanation_language = Chinese (zh)

# Request
POST /api/v1/cards/batches/
{
  "target_language": "fr",
  "vocabulary": ["bonjour"]
}

# Expected Result
Batch created with:
- target_language: French
- explanation_language: Chinese (from user preference)
```

### Test Case 2: Handle Conflict
```bash
# Setup
user.default_explanation_language = Chinese (zh)

# Request
POST /api/v1/cards/batches/
{
  "target_language": "zh",
  "vocabulary": ["你好"]
}

# Expected Result
Batch created with:
- target_language: Chinese
- explanation_language: English (auto-alternative)
```

### Test Case 3: Manual Override
```bash
# Setup
user.default_explanation_language = Chinese (zh)

# Request
POST /api/v1/cards/batches/
{
  "target_language": "fr",
  "explanation_language": "en",  // Manual override
  "vocabulary": ["bonjour"]
}

# Expected Result
Batch created with:
- target_language: French
- explanation_language: English (user's choice, not preference)
```

## Future Enhancements

1. **Profile UI**: Add settings page for users to manage language preferences
2. **Smart Defaults**: Learn from user's batch creation history
3. **Multiple Preferences**: Support different explanation languages for different target languages
4. **Language Pairs**: Pre-configured optimal language pairs (e.g., JP→ZH, FR→EN)

## Troubleshooting

### Issue: Explanation language not auto-selecting

**Check:**
1. User has `default_explanation_language` set in database
2. Template is receiving user context: `{{ user.default_explanation_language }}`
3. JavaScript console for errors

### Issue: Getting "Cannot determine explanation language" error

**Cause:** Target language matches user's preferred explanation language, and system couldn't find alternative

**Solution:** 
- Ensure at least English, Chinese, or French is active in the system
- Manually specify explanation language in API request
- Update user's `default_explanation_language` to a different language

## Summary

This feature improves user experience by:
- Reducing repetitive selections
- Intelligently handling edge cases
- Maintaining flexibility for manual overrides
- Providing sensible defaults for new users

The implementation respects user preferences while ensuring the system always produces valid batch configurations.
