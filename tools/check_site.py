"""Check generated routes, fragment targets, assets, language and lab provenance."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import hashlib
import json
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.ids, self.images, self.primary = [], [], [], []
        self.h1 = 0
        self.in_primary = False
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if tag == 'h1': self.h1 += 1
        if tag == 'nav' and a.get('id') == 'primary-nav': self.in_primary = True
        if tag == 'a' and 'href' in a:
            self.links.append(a['href'])
            if self.in_primary: self.primary.append(a['href'])
        if tag in ('script', 'img') and 'src' in a: self.links.append(a['src'])
        if tag == 'link' and 'href' in a: self.links.append(a['href'])
        if tag == 'img': self.images.append(a)
    def handle_endtag(self, tag):
        if tag == 'nav': self.in_primary = False

def main():
    config=json.loads((ROOT/'content/pages.json').read_text(encoding='utf-8'))
    translations=json.loads((ROOT/'content/vi.json').read_text(encoding='utf-8'))
    static_config=[p for p in config if not p.get('dynamic')]
    routes=[p['route'] for p in static_config] + ['vi/'+p['route'] for p in static_config]
    dynamic_routes={
        (ROOT/route).resolve()
        for item in config if item.get('dynamic')
        for route in (item['route'], 'vi/'+item['route'])
    }
    pages={route:Page((ROOT/route).read_text(encoding='utf-8')) for route in routes}
    failures=[]
    checked=0
    for route,page in pages.items():
        if page.h1 != 1: failures.append(f'{route}: expected one h1, got {page.h1}')
        if len(page.ids) != len(set(page.ids)): failures.append(f'{route}: duplicate IDs')
        if len(page.primary) != 6 or any('#' in href for href in page.primary): failures.append(f'{route}: primary navigation must contain five page routes and one language counterpart')
        for img in page.images:
            if not img.get('alt'): failures.append(f'{route}: image missing alt')
        for href in page.links:
            part=urlsplit(href)
            if part.scheme or part.netloc: continue
            target=(ROOT/route).parent/unquote(part.path) if part.path else ROOT/route
            target=target.resolve()
            checked+=1
            if target in dynamic_routes:
                continue
            if not target.is_relative_to(ROOT) or not target.is_file():
                failures.append(f'{route}: missing target {href}')
            elif part.fragment and target.suffix=='.html':
                target_page=Page(target.read_text(encoding='utf-8'))
                if unquote(part.fragment) not in target_page.ids: failures.append(f'{route}: missing fragment {href}')
        text=(ROOT/route).read_text(encoding='utf-8')
        if '\ufffd' in text: failures.append(f'{route}: replacement character')
        if not unicodedata.is_normalized('NFC', text): failures.append(f'{route}: non-normalized Unicode')
        if route.startswith('vi/') and re.search(r'\btôi\b', text, re.I): failures.append(f'{route}: use the requested personal voice')
        expected_lang='vi' if route.startswith('vi/') else 'en'
        if f'<html lang="{expected_lang}">' not in text: failures.append(f'{route}: wrong document language')
        if 'hreflang="en"' not in text or 'hreflang="vi"' not in text: failures.append(f'{route}: missing language alternates')
    for asset in json.loads((ROOT/'assets/fonts/sources.json').read_text(encoding='utf-8')):
        font=(ROOT/'assets/fonts'/asset['file']).read_bytes()
        if font[:4] != b'wOF2' or hashlib.sha256(font).hexdigest() != asset['sha256']:
            failures.append(f"Invalid or changed font asset: {asset['file']}")
    supplied=ROOT/'Coursera YZZXJ9446ZZN.pdf'
    public=ROOT/'assets/certificates/google-cybersecurity-YZZXJ9446ZZN.pdf'
    if hashlib.sha256(supplied.read_bytes()).digest() != hashlib.sha256(public.read_bytes()).digest():
        failures.append('Published certificate differs from the supplied PDF')
    results=json.loads((ROOT/'research/labs/results.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256((ROOT/'research/labs/run_labs.py').read_bytes()).hexdigest()
    if results['source_sha256'] != digest: failures.append('Lab source changed since execution')
    # Long English prose outside the already bilingual research articles must
    # have an explicit Vietnamese translation. Proper names and tool labels are
    # intentionally allowed to remain unchanged.
    class TextCollector(HTMLParser):
        def __init__(self):
            super().__init__(); self.values=[]; self.skipped=0
        def handle_starttag(self, tag, attrs):
            if tag in ('code', 'pre'): self.skipped += 1
        def handle_endtag(self, tag):
            if tag in ('code', 'pre'): self.skipped -= 1
        def handle_data(self, data):
            value=data.strip()
            if not self.skipped and value: self.values.append(value)
    for item in static_config:
        if item['route'].startswith('research/'): continue
        collector=TextCollector()
        # A page may provide a complete Vietnamese source instead of text-node mapping.
        translation_source = item.get('source_vi')
        if translation_source and translation_source == item['source']:
            failures.append(f"{item['source']}: explicit Vietnamese source must be distinct")
        collector.feed((ROOT/'content'/(translation_source or item['source'])).read_text(encoding='utf-8'))
        for value in collector.values:
            if len(value) >= 75 and re.search(r'\b(the|and|with|from|for|this|that|into|when|where)\b', value, re.I) and value not in translations:
                failures.append(f"{item['source']}: untranslated long text: {value[:60]}...")
    if failures: raise SystemExit('\n'.join(failures))
    print(f'PASS: {len(pages)} bilingual pages; {checked} local link/asset targets; headings, IDs, navigation, language alternates, image alt and lab source hash.')

if __name__=='__main__': main()
