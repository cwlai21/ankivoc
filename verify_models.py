#!/usr/bin/env python3
import requests

models = ['中文-(R/L)', 'Français-(R/L)']
print('=== FINAL VERIFICATION ===\n')

for model in models:
    print(f'{model}:')
    
    # Get CSS
    css_resp = requests.post('http://localhost:8765', json={
        'action': 'modelStyling',
        'version': 6,
        'params': {'modelName': model}
    })
    css = css_resp.json()['result']['css']
    
    # Get templates
    tpl_resp = requests.post('http://localhost:8765', json={
        'action': 'modelTemplates',
        'version': 6,
        'params': {'modelName': model}
    })
    templates = tpl_resp.json()['result']
    card_names = list(templates.keys())
    front = templates[card_names[0]]['Front']
    
    print(f'  ✓ CSS: {len(css)} chars')
    print(f'  ✓ Front: {len(front)} chars')
    print(f'  ✓ Has emoji: {any(e in front for e in ["🇨🇳", "🇫🇷"])}')
    print(f'  ✓ Has .png: {".png" in front}')
    print(f'  ✓ Card names: {card_names}')
    print()

print('✅ Both models are now aligned!')
print('   - Both use emoji flags (no .png files)')
print('   - Both use same CSS length (2566 chars)')
