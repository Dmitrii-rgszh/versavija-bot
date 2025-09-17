import os, json
from urllib.request import urlopen
from urllib.error import URLError
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    print('BOT_TOKEN not found in .env')
    raise SystemExit(1)

url = f'https://api.telegram.org/bot{TOKEN}/getWebhookInfo'
try:
    with urlopen(url, timeout=10) as r:
        data = json.load(r)
        print(json.dumps(data, indent=2, ensure_ascii=False))
except URLError as e:
    print('Network error:', e)
except Exception as e:
    print('Error:', e)
