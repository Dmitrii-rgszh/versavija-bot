from db import get_setting
import json

cats = json.loads(get_setting('portfolio_categories', '[]'))
print('Portfolio categories:')
for cat in cats:
    print(f'  - {cat["text"]} ({cat["slug"]})')