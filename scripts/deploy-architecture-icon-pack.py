"""Install the icon library and update Open WebUI through its versioned APIs."""
import argparse
import importlib.util
import json
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
import jwt
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("runtime", type=Path)
parser.add_argument("--base", default="http://127.0.0.1:3000")
args = parser.parse_args()
pack = ROOT / "deliverables/architecture-icon-pack-v1"
manifest = ROOT / "resources/architecture-icon-pack/manifest.json"
assert len(json.loads(manifest.read_text())["icons"]) == 64
assert (pack / "preview.html").is_file()
db = sqlite3.connect(args.runtime / "data/webui.db")
backup = args.runtime / "data" / f"webui-before-icon-pack-{int(time.time())}.db"
with sqlite3.connect(backup) as target:
    db.backup(target)
owner = db.execute("SELECT user_id FROM tool WHERE id=?", ("openwebui_fireworks_renderer",)).fetchone()[0]
values = dotenv_values(args.runtime / ".env")
secret = values.get("WEBUI_SECRET_KEY") or (args.runtime / ".webui_secret_key").read_text()
session = requests.Session()
session.headers["Authorization"] = "Bearer " + jwt.encode({"id":owner, "iat":int(time.time()), "exp":int(time.time())+900, "jti":str(uuid.uuid4())},secret,algorithm="HS256")


def api(path, payload=None):
    response = session.get(args.base+path, timeout=30) if payload is None else session.post(args.base+path, json=payload, timeout=90)
    if not response.ok:
        raise RuntimeError(f"{path}: {response.status_code} {response.text[:500]}")
    return response.json()


# Install files before publishing source which depends on them.
skill_root = args.runtime / "skills/fireworks-tech-graph"
icon_root = skill_root / "assets/icons/technical"
icon_root.mkdir(parents=True, exist_ok=True)
shutil.copy2(manifest, icon_root / "manifest.json")
reference = ROOT / "resources/openwebui-managed-skills/fireworks-tech-graph/references/architecture-icon-catalog.md"
(skill_root / "references").mkdir(parents=True, exist_ok=True)
shutil.copy2(reference, skill_root / "references/architecture-icon-catalog.md")
shutil.copy2(ROOT / "resources/openwebui-managed-skills/fireworks-tech-graph/scripts/generate-from-template.py", skill_root / "scripts/generate-from-template.py")
shutil.copy2(ROOT / "resources/openwebui-managed-skills/fireworks-tech-graph/SKILL.md", skill_root / "SKILL.md")
shutil.copy2(ROOT / "scripts/openwebui-fireworks-renderer-tool.py", args.runtime / "openwebui-fireworks-renderer-tool.py")
shutil.copy2(ROOT / "scripts/openwebui-visual-diagram-filter.py", args.runtime / "openwebui-visual-diagram-filter.py")
static = Path(importlib.util.find_spec("open_webui").origin).parent / "static/architecture-icons"
for target in (args.runtime / "data/architecture-icons", static):
    shutil.copytree(pack, target / "v1", dirs_exist_ok=True)
    shutil.copy2(ROOT / "deliverables/Local-Architecture-Icons-v1.zip", target / "Local-Architecture-Icons-v1.zip")
    shutil.copytree(ROOT / "deliverables/architecture-diagram-examples", target / "v1/examples", dirs_exist_ok=True, ignore=shutil.ignore_patterns("generated"))

versions = {}
for kind, id, file in (("tools", "openwebui_fireworks_renderer", "openwebui-fireworks-renderer-tool.py"), ("functions", "openwebui_visual_diagram_guard", "openwebui-visual-diagram-filter.py")):
    current = api(f"/api/v1/{kind}/id/{id}")
    saved = api(f"/api/v1/{kind}/id/{id}/update", {"id":id,"name":current["name"],"content":(ROOT / "scripts" / file).read_text(),"meta":current.get("meta") or {},"commit_message":"加入 64 個可重用 SVG 圖示、設備面板及互動預覽"})
    versions[id] = saved.get("version_id")

id = "fireworks-tech-graph"
current = api(f"/api/v1/skills/id/{id}")
saved = api(f"/api/v1/skills/id/{id}/update", {
    "id":id,"name":current["name"],"content":(skill_root / "SKILL.md").read_text(),
    "operations":[{"op":"put","path":"references/architecture-icon-catalog.md","content":reference.read_text()}],
    "expected_version_id":current["version_id"],"commit_message":"加入通用設備圖示選擇、連接埠與物理／邏輯連線準則"
})
versions[id] = saved["version_id"]
tool = api("/api/v1/tools/id/openwebui_fireworks_renderer")
assert "version: 4.1.0" in tool["content"] and {s["name"] for s in tool["specs"]} == {"render_technical_architecture", "render_data_chart"}
assert "architecture-icon-catalog.md" in str(saved["data"])
models = api("/api/models")
print(json.dumps({"backup":str(backup),"icons":64,"versions":versions,"preview":"/static/architecture-icons/v1/preview.html","models":[m["id"] for m in models.get("data",[])][:15]},ensure_ascii=False))
