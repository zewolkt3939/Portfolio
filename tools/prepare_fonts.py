"""Optional asset refresh: fetch self-hosted Noto fonts with full VI/EN coverage.

The normal site build is offline and uses the checked-in WOFF2 files.
Google Fonts text subsetting keeps all Vietnamese letters, combining marks,
Latin-1, punctuation and the portfolio's arrows in each variable font file.
"""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/fonts'
AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
points = set(range(0x20, 0x100)) | set(range(0x300, 0x370)) | set(range(0x1EA0, 0x1EFA)) | set(range(0x2000, 0x2070))
points |= {0x102, 0x103, 0x110, 0x111, 0x128, 0x129, 0x168, 0x169, 0x1A0, 0x1A1, 0x1AF, 0x1B0, 0x20AB, 0x20AC, 0x2190, 0x2191, 0x2192, 0x2193, 0x2197, 0x2212}
manifest = []
for family in ('Noto Sans', 'Noto Serif'):
    params = urlencode({'family': family + ':wght@100..900', 'display': 'swap', 'text': ''.join(map(chr, sorted(points)))})
    css_url = 'https://fonts.googleapis.com/css2?' + params
    request = Request(css_url, headers={'User-Agent': AGENT})
    css = urlopen(request, timeout=30).read().decode('utf-8')
    urls = re.findall(r'src:\s*url\(([^)]+)\)\s*format\([\'"]woff2[\'"]\)', css)
    if len(urls) != 1:
        raise ValueError(f'Expected one WOFF2 subset for {family}')
    data = urlopen(urls[0], timeout=30).read()
    if data[:4] != b'wOF2': raise ValueError('Invalid WOFF2 response')
    name = family.replace(' ', '') + '.woff2'
    (OUT / name).write_bytes(data)
    manifest.append({'file': name, 'source': urls[0], 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'unicode_requested': sorted(points)})
    print(f'{name}: {len(data):,} bytes')
(OUT / 'sources.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
