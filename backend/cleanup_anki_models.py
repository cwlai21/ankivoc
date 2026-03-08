#!/usr/bin/env python
"""
Delete old Chinese model from Anki to prevent field conflicts.
"""
import requests
import json

ANKI_URL = 'http://localhost:8765'

def anki_request(action, **params):
    """Send request to AnkiConnect."""
    payload = {
        'action': action,
        'version': 6,
        'params': params
    }
    response = requests.post(ANKI_URL, json=payload)
    result = response.json()
    if result.get('error'):
        raise Exception(f"AnkiConnect error: {result['error']}")
    return result.get('result')

def delete_model(model_name):
    """Delete a model from Anki."""
    try:
        # Check if model exists
        models = anki_request('modelNames')
        if model_name not in models:
            print(f"✓ Model '{model_name}' does not exist (already clean)")
            return
        
        # Get cards using this model
        card_ids = anki_request('findCards', query=f'"note:{model_name}"')
        
        if card_ids:
            print(f"⚠ Found {len(card_ids)} cards using model '{model_name}'")
            print(f"  These cards will be deleted if you proceed.")
            response = input(f"  Delete model '{model_name}' and all its cards? (yes/no): ")
            if response.lower() != 'yes':
                print("  Skipped.")
                return
        
        # Delete the model (this also deletes all cards using it)
        try:
            anki_request('modelNamesAndIds')  # Verify connection first
            # AnkiConnect doesn't have a direct deleteModel API
            # We need to use the GUI or deleteNotes for all cards
            if card_ids:
                print(f"  Deleting {len(card_ids)} cards...")
                anki_request('deleteNotes', notes=card_ids)
                print(f"  ✓ Deleted cards")
            
            print(f"⚠ Note: Model '{model_name}' structure remains in Anki")
            print(f"   Please manually delete the note type in Anki:")
            print(f"   Tools → Manage Note Types → Select '{model_name}' → Delete")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    except Exception as e:
        print(f"✗ Failed to check model '{model_name}': {e}")

if __name__ == '__main__':
    print("Cleaning old Anki models...")
    print("="*60)
    
    # Delete Chinese model (will be recreated with correct fields)
    delete_model('中文-(R/L)')
    
    print("\n" + "="*60)
    print("Cleanup complete!")
    print("\nImportant: After this, the model will be recreated automatically")
    print("with the correct field structure when you create a new card.")
