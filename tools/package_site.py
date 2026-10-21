"""Create an allowlisted public directory; keep source reports out of deployment."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'dist'
pages=[p for p in json.loads((ROOT/'content/pages.json').read_text(encoding='utf-8')) if not p.get('dynamic')]
files=[p['route'] for p in pages]+['vi/'+p['route'] for p in pages]+['styles.css','script.js','site.webmanifest','robots.txt','assets/favicon.svg','assets/resume/NguyenTruongBao_CV_VinSOC.pdf','research/labs/run_labs.py','research/labs/results.json','research/labs/transcript.txt']
files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'assets/research').glob('*.svg')]
files += [p.relative_to(ROOT).as_posix() for pattern in ('*.woff2', '*-OFL.txt') for p in (ROOT/'assets/fonts').glob(pattern)]
files += ['assets/certificates/google-cybersecurity-YZZXJ9446ZZN.pdf', 'assets/certificates/google-cybersecurity.webp']
files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'assets/p070').iterdir() if p.is_file() and p.suffix.lower() in {'.webp', '.svg', '.mp4', '.vtt', '.json', '.md'}]
allowed=set(files)
# Remove only stale files inside the verified build output directory.
assert OUT.resolve().parent == ROOT
if OUT.is_symlink(): raise SystemExit('Refusing to package into a symlink')
for target in OUT.rglob('*') if OUT.exists() else []:
    if target.is_file() and target.relative_to(OUT).as_posix() not in allowed:
        if not target.resolve().is_relative_to(OUT.resolve()): raise SystemExit('Unsafe output path')
        target.unlink()
for name in files:
    target=OUT/name
    if not target.resolve().is_relative_to(OUT.resolve()): raise SystemExit('Unsafe output path')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT/name,target)
print(f'Packaged {len(files)} public files into dist/.')
