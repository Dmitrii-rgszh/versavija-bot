import os, json
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    print('BOT_TOKEN not found in .env')
    raise SystemExit(1)

url = f'https://api.telegram.org/bot{TOKEN}/getUpdates?timeout=1&limit=1'
req = Request(url)
try:
    with urlopen(req, timeout=5) as r:
        data = json.load(r)
        print(json.dumps(data, indent=2, ensure_ascii=False))
except HTTPError as e:
    print('HTTPError:', e.code, e.read().decode(errors='ignore'))
except URLError as e:
    print('URLError:', e)
except Exception as e:
    print('Error:', e)
