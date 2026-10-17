"""Versioned, backed-up deployment of the numeric chart tool and policy."""
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
db = sqlite3.connect(args.runtime / "data/webui.db")
backup = args.runtime / "data" / f"webui-before-data-charts-{int(time.time())}.db"
with sqlite3.connect(backup) as target:
    db.backup(target)
owner = db.execute("SELECT user_id FROM tool WHERE id=?", ("openwebui_fireworks_renderer",)).fetchone()[0]
values = dotenv_values(args.runtime / ".env")
secret = values.get("WEBUI_SECRET_KEY") or (args.runtime / ".webui_secret_key").read_text()
session = requests.Session()
session.headers["Authorization"] = "Bearer "+jwt.encode({"id":owner,"iat":int(time.time()),"exp":int(time.time())+900,"jti":str(uuid.uuid4())},secret,algorithm="HS256")

def api(path, payload=None):
    result = session.get(args.base+path, timeout=30) if payload is None else session.post(args.base+path,json=payload,timeout=90)
    if not result.ok:
        raise RuntimeError(f"{path}: HTTP {result.status_code} {result.text[:300]}")
    return result.json()

versions = {}
# A later terminology filter used to normalize legacy content only, leaving
# structured output different after a reload. Keep its existing dictionary
# and protected regions; apply exactly the same normalizer to message text.
term_id = "taiwan_terminology_output_guard"
term = api(f"/api/v1/functions/id/{term_id}")
term_content = term["content"]
if "message.get(\"output\")" not in term_content:
    assert term_content.count("            break\n") == 1, "Terminology filter changed; inspect before patching"
    term_content = term_content.replace("            break\n", '''            for output in message.get("output") or []:
                if output.get("type") == "message":
                    for part in output.get("content") or []:
                        if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                            part["text"] = self._normalize_content(part["text"])
            break
''').replace("version: 1.0.0", "version: 1.1.0")
    saved = api(f"/api/v1/functions/id/{term_id}/update", {"id":term_id,"name":term["name"],"content":term_content,"meta":term.get("meta") or {},"commit_message":"同步術語校正的 content 與 structured output，避免圖表重整前後不一致"})
    versions[term_id] = saved.get("version_id")
for kind, id, file in (("tools","openwebui_fireworks_renderer","openwebui-fireworks-renderer-tool.py"), ("functions","openwebui_visual_diagram_guard","openwebui-visual-diagram-filter.py")):
    content = (ROOT / "scripts" / file).read_text()
    shutil.copy2(ROOT / "scripts" / file, args.runtime / file)
    current = api(f"/api/v1/{kind}/id/{id}")
    saved = api(f"/api/v1/{kind}/id/{id}/update", {"id":id,"name":current["name"],"content":content,"meta":current.get("meta") or {},"commit_message":"加入深色數值比較、趨勢與資料來源驗證；保留文字分析並隱藏繪圖代碼"})
    versions[id] = saved.get("version_id")
skill_id = "numeric-comparison-charts"
source = ROOT / "resources/openwebui-managed-skills" / skill_id / "SKILL.md"
destination = args.runtime / "skills" / skill_id
destination.mkdir(parents=True, exist_ok=True)
shutil.copy2(source, destination / "SKILL.md")
existing = session.get(args.base+f"/api/v1/skills/id/{skill_id}",timeout=30)
form = {"id":skill_id,"name":"數值比較與趨勢圖","description":"長條圖、橫向圖、分組比較、折線圖；保留分析，標示單位、來源與實測／估算性質。","content":source.read_text(),"is_active":True,"commit_message":"加入伺服器數值圖表工作流程"}
if existing.status_code == 404:
    saved = api("/api/v1/skills/create",form)
else:
    existing.raise_for_status()
    form["expected_version_id"] = existing.json()["version_id"]
    saved = api(f"/api/v1/skills/id/{skill_id}/update",form)
versions[skill_id] = saved["version_id"]
static = Path(importlib.util.find_spec("open_webui").origin).parent / "static/openwebui-generated/chart-examples"
shutil.copytree(ROOT / "deliverables/data-chart-examples", static, dirs_exist_ok=True, ignore=shutil.ignore_patterns("generated"))
tool = api("/api/v1/tools/id/openwebui_fireworks_renderer")
names = {s["name"] for s in tool["specs"]}
assert names == {"render_technical_architecture", "render_data_chart"}, names
assert "version: 4.1.0" in tool["content"]
guard = api("/api/v1/functions/id/openwebui_visual_diagram_guard")
assert guard.get("is_active") and guard.get("is_global"), "Chart policy must be active globally"
print(json.dumps({"ok":True,"backup":str(backup),"versions":versions,"tools":sorted(names),"policy_global":True,"sample":"/static/openwebui-generated/chart-examples/inference-comparison.png"},ensure_ascii=False))
