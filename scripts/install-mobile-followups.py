"""Install scoped follow-up layout/tooltip fixes; preserve existing customizations."""
import argparse
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("package", type=Path, help="Installed open_webui Python package")
args = parser.parse_args()
root = args.package.resolve()
index = root / "frontend/index.html"
version = root / "frontend/_app/version.json"
assert index.is_file() and version.is_file()
source = Path(__file__).resolve().parents[1] / "resources/openwebui-mobile-followups.css"
script = source.with_suffix('.js')
digest = hashlib.sha256(source.read_bytes()+script.read_bytes()).hexdigest()[:12]
name = source.name
tag = f'<link rel="stylesheet" href="/static/{name}?v={digest}" crossorigin="use-credentials" />'
previous = index.read_text()
if re.search(r'<link\b[^>]*href="/static/openwebui-mobile-followups\.css[^>]*>', previous):
    updated = re.sub(r'<link\b[^>]*href="/static/openwebui-mobile-followups\.css[^>]*>', tag, previous)
else:
    assert '</head>' in previous
    updated = previous.replace('</head>', '\t'+tag+'\n\t</head>', 1)
script_tag = f'<script src="/static/{script.name}?v={digest}" defer crossorigin="use-credentials"></script>'
if re.search(r'<script\b[^>]*src="/static/openwebui-mobile-followups\.js[^>]*></script>', updated):
    updated = re.sub(r'<script\b[^>]*src="/static/openwebui-mobile-followups\.js[^>]*></script>', script_tag, updated)
else:
    updated = updated.replace('</head>', '\t'+script_tag+'\n\t</head>', 1)
stamp = str(time.time_ns())
backups = []
for path in (index, version, *[root / directory / asset.name for directory in ('static','frontend/static') for asset in (source,script)]):
    if path.is_file():
        backup = path.with_name(path.name+".before-mobile-followups-"+stamp)
        shutil.copy2(path, backup)
        backups.append(str(backup))
for directory in (root / "static", root / "frontend/static"):
    assert directory.is_dir()
    for asset in (source,script):
        shutil.copy2(asset, directory / asset.name)
index.write_text(updated)
data = json.loads(version.read_text())
data["version"] = re.sub(r'-followups-[a-f0-9]+$', '', data["version"])+"-followups-"+digest
version.write_text(json.dumps(data))
assert index.read_text().count('/static/'+name) == 1
assert index.read_text().count('/static/'+script.name) == 1
print(json.dumps({"ok": True, "css_hash": digest, "backups": backups}, ensure_ascii=False))
