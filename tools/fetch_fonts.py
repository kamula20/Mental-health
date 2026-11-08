"""Fetch the specified open fonts for self-hosting; not required at runtime."""
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / 'static' / 'fonts'
FONT_DIR.mkdir(parents=True, exist_ok=True)
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'}
url = 'https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&family=Source+Serif+4:wght@400;600;700&display=swap'
css = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30).read().decode()
blocks = re.findall(r'/\* latin \*/\s*(@font-face\s*\{.*?\})', css, re.S)
if not blocks:
    blocks = re.findall(r'@font-face\s*\{.*?\}', css, re.S)
output = []
downloaded = {}
for block in blocks:
    remote = re.search(r'url\(([^)]+)\)', block).group(1)
    if remote not in downloaded:
        name = 'font-' + str(len(downloaded)) + pathlib.PurePosixPath(remote).suffix
        (FONT_DIR / name).write_bytes(urllib.request.urlopen(remote, timeout=30).read())
        downloaded[remote] = name
    output.append(block.replace(remote, '/static/fonts/' + downloaded[remote]))
(FONT_DIR / 'fonts.css').write_text('\n'.join(output), encoding='utf-8')
# Source Sans 3 and Source Serif 4 are distributed under the SIL Open Font License.
for family, location in [('source-sans', 'adobe-fonts/source-sans/release/LICENSE.md'), ('source-serif', 'adobe-fonts/source-serif/release/LICENSE.md')]:
    (FONT_DIR / (family + '-LICENSE.md')).write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/' + location, timeout=30).read())
print(f'Self-hosted {len(downloaded)} font files and both font licences.')
