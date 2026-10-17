"""Deploy the server diagram integration with a recoverable SQLite backup."""
import argparse
import json
import shutil
import sqlite3
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("runtime", type=Path)
args = parser.parse_args()
db = sqlite3.connect(args.runtime / "data/webui.db")
backup = args.runtime / "data" / f"webui-before-diagram-v6-{int(time.time())}.db"
with sqlite3.connect(backup) as target:
    db.backup(target)
# sqlite readfile is CLI-only; supply the same behavior to this connection.
db.create_function("readfile", 1, lambda p: (root / p).read_bytes())
db.executescript((root / "scripts/openwebui-fireworks-renderer-tool.sql").read_text())
guard = (root / "scripts/openwebui-visual-diagram-filter.py").read_text()
with db:
    db.execute("UPDATE function SET content=?, meta=?, updated_at=? WHERE id='openwebui_visual_diagram_guard'",
        (guard, json.dumps({"description": "伺服器原生 Renderer 與結構化輸出同步", "manifest": {"version": "6.0.0"}}), int(time.time())))
    # The database Skill previously instructed the model to execute shell
    # commands through a disconnected browser. Keep the technical reference,
    # replace only the Open WebUI-specific execution contract.
    content = (root / "resources/openwebui-managed-skills/fireworks-tech-graph/SKILL.md").read_text()
    db.execute("UPDATE skill SET content=?,updated_at=? WHERE id='fireworks-tech-graph'", (content, int(time.time())))
shutil.copy2(root / "scripts/openwebui-fireworks-renderer-tool.py", args.runtime / "openwebui-fireworks-renderer-tool.py")
print(json.dumps({"backup": str(backup), "tool_registered": db.execute("SELECT count(*) FROM tool WHERE id='openwebui_fireworks_renderer'").fetchone()[0], "guard_version": "6.0.0"}))
