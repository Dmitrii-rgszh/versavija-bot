#!/usr/bin/env python3
from db import get_setting
import json

categories = ['family', 'love_story', 'wedding', 'personal', 'children', 'lingerie']

print("Portfolio status:")
for cat in categories:
    photos = json.loads(get_setting(f'portfolio_{cat}', '[]'))
    print(f'{cat}: {len(photos)} photos')
    if photos:
        print(f'  First photo ID: {photos[0][:20]}...')