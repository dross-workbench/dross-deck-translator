"""Build a Decky ZIP with upstream's checksum-pinned Linux runtime included."""
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
package = json.loads((root/'package.json').read_text())
asset = package['remote_binary'][0]
cache = root/'.local'/asset['name']
cache.parent.mkdir(exist_ok=True)
if not cache.exists():
    urllib.request.urlretrieve(asset['url'], cache)
digest = hashlib.file_digest(cache.open('rb'), 'sha256').hexdigest()
if digest != asset['sha256hash']:
    raise SystemExit('Upstream dependency checksum mismatch')
if not (root/'dist/index.js').exists():
    raise SystemExit('Run pnpm build first')
out = root/'out'
out.mkdir(exist_ok=True)
target = out/'Dross.Deck.Translator.zip'
with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for file in ['main.py', 'plugin.json', 'LICENSE', 'THIRD_PARTY_LICENSES']:
        z.write(root/file, 'dross-deck-translator/'+file)
    # The verified dependency archive is already bundled below. Leaving
    # remote_binary here makes Decky's installer download it a second time.
    installed_package = {k: v for k, v in package.items() if k != 'remote_binary'}
    z.writestr('dross-deck-translator/package.json', json.dumps(installed_package, indent=2))
    for folder in ['dist', 'py_modules/providers']:
        for p in (root/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                z.write(p, 'dross-deck-translator/'+p.relative_to(root).as_posix())
    z.write(cache, 'dross-deck-translator/bin/'+asset['name'])
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    assert all(n.startswith('dross-deck-translator/') for n in z.namelist())
print(f'Created {target.name}: {target.stat().st_size} bytes; SHA256 {hashlib.file_digest(target.open("rb"), "sha256").hexdigest()}')
