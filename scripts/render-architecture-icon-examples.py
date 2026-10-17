"""Render distinct branched fixtures through the same server tool used by chats."""
import asyncio
import importlib.util
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables/architecture-diagram-examples"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["OPENWEBUI_FIREWORKS_SKILL_ROOT"] = str(ROOT / "resources/openwebui-managed-skills/fireworks-tech-graph")
os.environ["OPENWEBUI_FIREWORKS_OUTPUT_DIR"] = str(OUT / "generated")
spec = importlib.util.spec_from_file_location("architecture_renderer", ROOT / "scripts/openwebui-fireworks-renderer-tool.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


async def main():
    renderer = module.Tools()
    assert len(renderer._icon_catalog()) >= 64
    assert renderer._pick_icon({"label":"NAS 儲存"}, renderer._icon_catalog()) == "nas"
    assert renderer._pick_icon({"icon":"../../secret","label":"GPU"}, renderer._icon_catalog()) == "gpu"
    for example in json.loads((ROOT / "resources/architecture-icon-pack/examples.json").read_text()):
        slug = example.pop("slug")
        if slug == "smb-topology":
            # A model may list connections in any order. The hub's port
            # order must remain spatial and must not create bridge crossings.
            example["edges"] = list(reversed(example["edges"]))
        result = await renderer.render_technical_architecture(**example)
        match = re.search(r"/([0-9]+-[a-f0-9]+)\.png", result)
        assert match, result
        source = OUT / "generated" / match[1]
        for ext in ("svg", "png", "html"):
            assert source.with_suffix('.'+ext).is_file(), f"Missing {ext}: {result}"
            shutil.copy2(source.with_suffix('.'+ext), OUT / (slug+'.'+ext))
        tree = ET.parse(OUT / (slug+'.svg'))
        drawn = tree.findall('.//*[@data-graph-role="node"]')
        assert len(drawn) == len(example["nodes"])
        assert {n.get("data-icon-id") for n in drawn} == {n["icon"] for n in example["nodes"]}
        assert len(tree.findall('.//*[@data-graph-role="edge"]')) == len(example["edges"])
        for node in example["nodes"]:
            assert node["label"] in ''.join(tree.getroot().itertext())
        print(json.dumps({"sample":slug,"nodes":len(drawn),"edges":len(example["edges"]),"icons":sorted({n.get('data-icon-id') for n in drawn}),"svg":str(OUT / (slug+'.svg'))},ensure_ascii=False),flush=True)


asyncio.run(main())
