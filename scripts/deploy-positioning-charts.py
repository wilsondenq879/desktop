"""Deploy quadrant support and repair only an existing diagram block, without model regeneration."""
import argparse
import asyncio
import copy
import importlib.util
import json
import re
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

import jwt
import requests
from dotenv import dotenv_values

parser = argparse.ArgumentParser()
parser.add_argument("runtime", type=Path)
parser.add_argument("--chat")
parser.add_argument("--source-backup", type=Path, help="Re-export a repaired chart using its original source, preserving current prose")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
db = sqlite3.connect(args.runtime / "data/webui.db")
backup = args.runtime / "data" / f"webui-before-positioning-charts-{int(time.time())}.db"
with sqlite3.connect(backup) as target:
    db.backup(target)
owner = db.execute("SELECT user_id FROM tool WHERE id=?", ("openwebui_fireworks_renderer",)).fetchone()[0]
values = dotenv_values(args.runtime / ".env")
secret = values.get("WEBUI_SECRET_KEY") or (args.runtime / ".webui_secret_key").read_text()
session = requests.Session()
session.headers["Authorization"] = "Bearer " + jwt.encode(
    {"id": owner, "iat": int(time.time()), "exp": int(time.time()) + 900, "jti": str(uuid.uuid4())}, secret, algorithm="HS256")


def api(path, payload=None):
    url = "http://127.0.0.1:3000" + path
    response = session.get(url, timeout=30) if payload is None else session.post(url, json=payload, timeout=90)
    response.raise_for_status()
    return response.json()


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


versions = {}
for kind, id, file in (("tools", "openwebui_fireworks_renderer", "openwebui-fireworks-renderer-tool.py"),
    ("functions", "openwebui_visual_diagram_guard", "openwebui-visual-diagram-filter.py")):
    existing = api(f"/api/v1/{kind}/id/{id}")
    source = root / "scripts" / file
    saved = api(f"/api/v1/{kind}/id/{id}/update", {
        "id": id, "name": existing["name"], "content": source.read_text(), "meta": existing.get("meta") or {},
        "commit_message": "支援四象限定性定位成品圖，修正泛用圖表意圖及 Mermaid 復原；不冒充市佔數據",
    })
    shutil.copy2(source, args.runtime / file)
    versions[id] = saved["version_id"]

artifact = None
if args.chat:
    loaded = api("/api/v1/chats/" + args.chat)["chat"]
    mid = loaded["history"]["currentId"]
    message = loaded["history"]["messages"][mid]
    assert message["role"] == "assistant" and message.get("done") is not False
    original = message["content"]
    block = re.search(r"```mermaid\s*\n(\s*quadrantChart\b[\s\S]*?)```", original)
    source_block = block
    if not source_block and args.source_backup:
        with sqlite3.connect(f"file:{args.source_backup}?mode=ro", uri=True) as prior:
            record = json.loads(prior.execute("SELECT chat FROM chat WHERE id=?", (args.chat,)).fetchone()[0])
        source_block = re.search(r"```mermaid\s*\n(\s*quadrantChart\b[\s\S]*?)```", record["history"]["messages"][mid]["content"])
    if source_block:
        guard = load("positioning_guard", "openwebui-visual-diagram-filter.py").Filter()
        renderer = load("positioning_renderer", "openwebui-fireworks-renderer-tool.py").Tools()
        data = guard._quadrant_data(source_block[1])
        assert data, "Existing block cannot be recovered safely"
        artifact = asyncio.run(renderer.render_data_chart(**data))
        assert artifact.startswith("!["), artifact
        png_url = re.search(r"\]\((/static/[^)]+\.png)\)", artifact)[1]
        response = session.get("http://127.0.0.1:3000" + png_url, timeout=30)
        assert response.ok and response.content.startswith(b"\x89PNG")
        warning = "> 圖表修正：以下沿用原模型的定性分析，尚未完成來源查證；定位座標不是市佔率、實測或客觀品牌排名。\n\n"
        if block:
            content = warning + original[:block.start()] + artifact + original[block.end():]
        else:
            old = re.search(r"\]\(/static/openwebui-generated/fireworks/(chart-[\w-]+)\.png\)", original)
            assert old, "No existing chart to refresh"
            new = re.search(r"/(chart-[\w-]+)\.png", artifact)[1]
            content = original.replace(old[1], new)
        # Correct only the textual quadrant reference that contradicted its
        # own original coordinates; do not move points or invent market data.
        content = content.replace("位處右上角的「技術領先區」", "位處右上角的高單價／高功能區（定性示意）")
        content = content.replace("他們在右下角的「智慧生態區」", "依原模型座標，他們位於左下角（定性示意）")
        updated = copy.deepcopy(message)
        updated["content"] = content
        parts = [p for item in updated.get("output", []) if item.get("type") == "message"
            for p in item.get("content", []) if p.get("type") == "output_text"]
        if parts:
            for part in parts:
                part["text"] = ""
            parts[-1]["text"] = content
        else:
            updated.setdefault("output", []).append({"id":"msg_"+uuid.uuid4().hex,"type":"message","role":"assistant","status":"completed","content":[{"type":"output_text","text":content}]})
        api("/api/v1/chats/" + args.chat, {"chat":{"history":{"messages":{mid:updated}}}})
        actual = api("/api/v1/chats/" + args.chat)["chat"]["history"]["messages"][mid]
        assert actual["content"] == content and actual["output"] == updated["output"]
        assert actual.get("usage") == message.get("usage")
print(json.dumps({"ok":True,"backup":str(backup),"versions":versions,"repaired_png":png_url if artifact else None}, ensure_ascii=False))
