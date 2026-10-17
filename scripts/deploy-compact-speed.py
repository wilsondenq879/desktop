"""Deploy just the compact speed footer and clean tagged footers in one chat."""
import argparse
import copy
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
args = parser.parse_args()
db = sqlite3.connect(args.runtime / "data/webui.db")
backup = args.runtime / "data" / f"webui-before-compact-speed-{int(time.time())}.db"
with sqlite3.connect(backup) as target:
    db.backup(target)
owner = db.execute("SELECT user_id FROM tool WHERE id=?", ("openwebui_fireworks_renderer",)).fetchone()[0]
values = dotenv_values(args.runtime / ".env")
secret = values.get("WEBUI_SECRET_KEY") or (args.runtime / ".webui_secret_key").read_text()
session = requests.Session()
session.headers["Authorization"] = "Bearer " + jwt.encode(
    {"id": owner, "iat": int(time.time()), "exp": int(time.time()) + 900, "jti": str(uuid.uuid4())},
    secret, algorithm="HS256",
)


def api(path, payload=None):
    url = "http://127.0.0.1:3000" + path
    response = session.get(url, timeout=30) if payload is None else session.post(url, json=payload, timeout=90)
    response.raise_for_status()
    return response.json()


fid = "openwebui_response_speed"
existing = api(f"/api/v1/functions/id/{fid}")
source = Path(__file__).with_name("openwebui-response-speed-filter.py")
saved = api(f"/api/v1/functions/id/{fid}/update", {
    "id": fid, "name": existing["name"], "content": source.read_text(),
    "meta": existing.get("meta") or {}, "commit_message": "只顯示 tokens/s；移除可見註解標記與冗長說明",
})
assert saved["is_active"] and saved["is_global"]
shutil.copy2(source, args.runtime / source.name)

tagged = re.compile(r"\n*<!-- openwebui-response-speed -->([\s\S]*?)<!-- /openwebui-response-speed -->")


def compact(text):
    def replace(match):
        metric = re.search(r"([\d.]+) tokens/s", match[1])
        value = metric[1] if metric else "N/A"
        prefix = "≈ " if "端到端" in match[1] and metric else ""
        return "\n\n" + prefix + value + " tokens/s"
    return tagged.sub(replace, text)


changed = {}
if args.chat:
    chat = api("/api/v1/chats/" + args.chat)["chat"]
    for mid, message in chat.get("history", {}).get("messages", {}).items():
        if message.get("role") != "assistant" or message.get("done") is False:
            continue
        updated = copy.deepcopy(message)
        if isinstance(updated.get("content"), str):
            updated["content"] = compact(updated["content"])
        for item in updated.get("output") or []:
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                        part["text"] = compact(part["text"])
        if updated != message:
            changed[mid] = updated
    if changed:
        api("/api/v1/chats/" + args.chat, {"chat": {"history": {"messages": changed}}})
        loaded = api("/api/v1/chats/" + args.chat)["chat"]["history"]["messages"]
        for mid, expected in changed.items():
            assert loaded[mid]["content"] == expected["content"]
            assert loaded[mid].get("output") == expected.get("output")
            assert loaded[mid].get("usage") == expected.get("usage")
print(json.dumps({"ok": True, "backup": str(backup), "version": saved["version_id"], "cleaned_messages": len(changed)}, ensure_ascii=False))
