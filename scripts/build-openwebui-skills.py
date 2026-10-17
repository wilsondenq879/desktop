#!/usr/bin/env python3
"""Build the Open WebUI Workspace Skills bundle shipped by Desktop.

The bundle is imported into Open WebUI's own Skills API at sign-in.  It is
not a Codex runtime directory: Codex/Agents/Claude folders are only the local
source used to create a portable Open WebUI import payload.
"""

from __future__ import annotations

import json
import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "resources" / "openwebui-skills.json"


def frontmatter_value(content: str, key: str) -> str:
    if not content.startswith("---\n"):
        return ""
    end = content.find("\n---", 4)
    if end < 0:
        return ""
    frontmatter = content[4:end]
    match = re.search(rf"^{re.escape(key)}:\s*(.*)$", frontmatter, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip().strip('"\'') if match else ""


def strip_lmlab_prefix(value: str) -> str:
    visible = re.sub(r"^lmlab(?:\s*[-_:·|]\s*|\s+)?", "", value.strip(), flags=re.IGNORECASE).strip()
    return visible or value.strip()


def normalize_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    return value.lower() or "desktop-skill"


def load_skill(path: Path, source: str) -> dict:
    content = path.read_text(encoding="utf-8")
    directory_name = path.parent.name
    raw_name = (
        frontmatter_value(content, "openwebui-name")
        or frontmatter_value(content, "name")
        or directory_name
    )
    return {
        "id": normalize_id(directory_name),
        "name": strip_lmlab_prefix(raw_name),
        "description": (
            frontmatter_value(content, "openwebui-description")
            or frontmatter_value(content, "description")
        ),
        "content": content,
        "meta": {"tags": ["desktop", "local-skill"], "source": source},
        "is_active": True,
        "access_grants": [],
    }


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--include-local',action='store_true',help='Explicitly include personal skills; review before publishing')
    args=parser.parse_args()
    roots=[]
    if args.include_local:
        roots.extend([(Path.home()/'.codex/skills','codex'),(Path.home()/'.agents/skills','agents'),(Path.home()/'.claude/skills','claude')])
    roots.append((ROOT/'resources/openwebui-managed-skills','desktop-managed'))
    # Reproducible default: retain the existing reviewed bundle, then overlay
    # managed sources; do not ingest unrelated newly added personal skills.
    skills={item['id']:item for item in json.loads(OUTPUT.read_text())} if OUTPUT.exists() else {}
    for root, source in roots:
        if not root.exists():
            continue
        for skill_file in sorted(root.glob("*/SKILL.md")):
            skill = load_skill(skill_file, source)
            skills[skill["id"]] = skill

    if not skills:
        raise SystemExit("No local skills found")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(sorted(skills.values(), key=lambda item: item["name"].casefold()), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(skills)} Open WebUI skill(s) to {OUTPUT}")


if __name__ == "__main__":
    main()
