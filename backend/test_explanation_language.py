#!/usr/bin/env python
"""
Test script for explanation language auto-selection feature.

Tests the logic that automatically selects explanation language based on
user's default_explanation_language preference, with conflict resolution.
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from languages.models import Language
from cards.serializers import VocabularyBatchCreateSerializer


def test_explanation_language_selection():
    """Test explanation language selection logic."""
    
    print("=" * 70)
    print("Testing Explanation Language Auto-Selection")
    print("=" * 70)
    
    # Get test user
    try:
        user = User.objects.get(username='testuser')
    except User.DoesNotExist:
        print("❌ testuser not found. Please create testuser first.")
        return
    
    # Get languages
    fr = Language.objects.get(code='fr')
    zh = Language.objects.get(code='zh')
    en = Language.objects.get(code='en')
    
    print(f"\n📋 Test User: {user.username}")
    print(f"   Default Target: {user.default_target_language}")
    print(f"   Default Explanation: {user.default_explanation_language}")
    
    # Test scenarios
    scenarios = [
        {
            'name': 'Scenario 1: Target=French, No explanation provided',
            'user_pref': zh,
            'target': fr,
            'explanation': None,
            'expected': zh,
            'reason': "Should use user's preference (Chinese)"
        },
        {
            'name': 'Scenario 2: Target=Chinese, No explanation provided',
            'user_pref': zh,
            'target': zh,
            'explanation': None,
            'expected': en,
            'reason': "Target matches preference, should auto-select English"
        },
        {
            'name': 'Scenario 3: Target=French, Explanation=English (override)',
            'user_pref': zh,
            'target': fr,
            'explanation': en,
            'expected': en,
            'reason': "Should respect user's manual override"
        },
        {
            'name': 'Scenario 4: No user preference, Target=French',
            'user_pref': None,
            'target': fr,
            'explanation': None,
            'expected': en,
            'reason': "No preference, should default to English"
        },
    ]
    
    passed = 0
    failed = 0
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'─' * 70}")
        print(f"Test {i}: {scenario['name']}")
        print(f"{'─' * 70}")
        
        # Setup user preference
        user.default_explanation_language = scenario['user_pref']
        user.save()
        
        # Prepare data
        data = {
            'target_language': scenario['target'].code,
            'vocabulary': ['test word']
        }
        
        if scenario['explanation']:
            data['explanation_language'] = scenario['explanation'].code
        
        # Validate serializer
        serializer = VocabularyBatchCreateSerializer(data=data)
        
        if not serializer.is_valid():
            print(f"❌ Serializer validation failed: {serializer.errors}")
            failed += 1
            continue
        
        validated_data = serializer.validated_data
        
        # Simulate view logic
        explanation_language = validated_data.get('explanation_language')
        
        if not explanation_language:
            explanation_language = user.default_explanation_language
        
        if not explanation_language:
            explanation_language = en
        
        if validated_data['target_language'] == explanation_language:
            # Find alternative
            for fallback_code in ['en', 'zh', 'fr']:
                if validated_data['target_language'].code != fallback_code:
                    try:
                        explanation_language = Language.objects.get(code=fallback_code, is_active=True)
                        break
                    except Language.DoesNotExist:
                        continue
        
        # Check result
        print(f"Input:")
        print(f"  - User preference: {scenario['user_pref'].code if scenario['user_pref'] else 'None'}")
        print(f"  - Target language: {scenario['target'].code}")
        print(f"  - Explanation provided: {scenario['explanation'].code if scenario['explanation'] else 'None'}")
        print(f"\nResult:")
        print(f"  - Selected explanation: {explanation_language.code}")
        print(f"  - Expected: {scenario['expected'].code}")
        
        if explanation_language == scenario['expected']:
            print(f"\n✅ PASSED: {scenario['reason']}")
            passed += 1
        else:
            print(f"\n❌ FAILED: Expected {scenario['expected'].code}, got {explanation_language.code}")
            print(f"   Reason: {scenario['reason']}")
            failed += 1
    
    # Summary
    print(f"\n{'=' * 70}")
    print(f"Test Summary")
    print(f"{'=' * 70}")
    print(f"Total tests: {len(scenarios)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"{'=' * 70}\n")
    
    return failed == 0


if __name__ == '__main__':
    success = test_explanation_language_selection()
    sys.exit(0 if success else 1)
