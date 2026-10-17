"""Deploy early diagram prose and a global, provider-measured speed footer."""
import argparse
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
backup = args.runtime / "data" / f"webui-before-response-feedback-{int(time.time())}.db"
with sqlite3.connect(backup) as target:
    db.backup(target)
owner = db.execute("SELECT user_id FROM tool WHERE id=?", ("openwebui_fireworks_renderer",)).fetchone()[0]
values = dotenv_values(args.runtime / ".env")
secret = values.get("WEBUI_SECRET_KEY") or (args.runtime / ".webui_secret_key").read_text()
session = requests.Session()
session.headers["Authorization"] = "Bearer "+jwt.encode({"id":owner,"iat":int(time.time()),"exp":int(time.time())+900,"jti":str(uuid.uuid4())},secret,algorithm="HS256")

def api(path, payload=None):
    response = session.get(args.base+path, timeout=30) if payload is None else session.post(args.base+path,json=payload,timeout=90)
    if not response.ok:
        raise RuntimeError(f"{path}: HTTP {response.status_code} {response.text[:300]}")
    return response.json()

versions = {}
tool_id = "openwebui_fireworks_renderer"
tool = api(f"/api/v1/tools/id/{tool_id}")
tool_source = ROOT / "scripts/openwebui-fireworks-renderer-tool.py"
shutil.copy2(tool_source,args.runtime/tool_source.name)
shutil.copy2(ROOT/"resources/openwebui-managed-skills/fireworks-tech-graph/scripts/generate-from-template.py",args.runtime/"skills/fireworks-tech-graph/scripts/generate-from-template.py")
saved = api(f"/api/v1/tools/id/{tool_id}/update",{"id":tool_id,"name":tool["name"],"content":tool_source.read_text(),"meta":tool.get("meta") or {},"commit_message":"修正跨層分支路由與短折線，保留零交叉及最短線段品質檢查"})
versions[tool_id] = saved["version_id"]
known = {item["id"] for item in api("/api/v1/functions/list")}
for id, name, file in (("openwebui_visual_diagram_guard","Fireworks 技術圖表守門員","openwebui-visual-diagram-filter.py"), ("openwebui_response_speed","回答生成速度","openwebui-response-speed-filter.py")):
    existing = api(f"/api/v1/functions/id/{id}") if id in known else {}
    content = (ROOT / "scripts" / file).read_text()
    shutil.copy2(ROOT / "scripts" / file, args.runtime / file)
    payload = {"id":id,"name":existing.get("name") or name,"content":content,"meta":existing.get("meta") or {},"commit_message":"先輸出架構說明再繪圖；每則回答顯示實際 tokens/s"}
    saved = api(f"/api/v1/functions/id/{id}/update" if existing else "/api/v1/functions/create", payload)
    if not saved["is_active"]:
        saved = api(f"/api/v1/functions/id/{id}/toggle", {})
    if not saved["is_global"]:
        saved = api(f"/api/v1/functions/id/{id}/toggle/global", {})
    assert saved["is_active"] and saved["is_global"]
    versions[id] = saved["version_id"]
source = ROOT / "resources/openwebui-managed-skills/fireworks-tech-graph/SKILL.md"
shutil.copy2(source, args.runtime / "skills/fireworks-tech-graph/SKILL.md")
current = api("/api/v1/skills/id/fireworks-tech-graph")
saved = api("/api/v1/skills/id/fireworks-tech-graph/update", {"id":current["id"],"name":current["name"],"content":source.read_text(),"expected_version_id":current["version_id"],"commit_message":"先給有用的架構說明再呼叫繪圖，不再把正常文字一起暫存"})
versions["fireworks-tech-graph"] = saved["version_id"]
print(json.dumps({"ok":True,"backup":str(backup),"versions":versions,"early_prose":True,"speed_footer_global":True},ensure_ascii=False))
