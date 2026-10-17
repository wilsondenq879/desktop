#!/usr/bin/env python3
"""Smoke-test the semantic router against the live skill catalog and Ollama."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "scripts" / "openwebui-skill-semantic-router.py"
MODEL = "jeffh/intfloat-multilingual-e5-small:f16"


def load_router():
    spec = importlib.util.spec_from_file_location("openwebui_skill_semantic_router", ROUTER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.Filter()


def load_skills(db_path: Path):
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id,name,description,content,meta,is_active,updated_at FROM skill WHERE is_active=1"
        ).fetchall()
    result = []
    for row in rows:
        values = dict(row)
        values["meta"] = json.loads(values["meta"] or "{}")
        result.append(SimpleNamespace(**values))
    return result


async def embed(value, prefix=None, user=None):
    payload = json.dumps({"model": MODEL, "input": value}).encode("utf-8")

    def request():
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            embeddings = json.loads(response.read())["embeddings"]
        return embeddings if isinstance(value, list) else embeddings[0]

    return await asyncio.to_thread(request)


async def main(db_path: Path):
    router = load_router()
    skills = load_skills(db_path)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(EMBEDDING_FUNCTION=embed)))
    queries = [
        "幫我畫一張 25G RDMA 的網路架構圖",
        "研究華碩路由器市場與主要競爭對手",
        "wifi8 路由器哪些已經在販售",
        "幫我用 React 做一個有質感的產品網頁",
        "今天心情不錯，跟我聊聊天",
    ]
    for query in queries:
        ranked = await router._rank(query, skills, request, {})
        print(f"\n{query}")
        for item in ranked[:5]:
            print(
                f"  {item['skill'].id:<42} score={item['score']:.4f} "
                f"semantic={item['semantic']:.4f} lexical={item['lexical']:.4f} intent={item['intent']:.2f}"
            )

    ranked = await router._rank(queries[0], skills, request, {})
    if ranked[0]["skill"].id != "fireworks-tech-graph":
        raise SystemExit("Technical architecture query did not select Fireworks Tech Graph")
    if ranked[0]["intent"] < 0.30 or ranked[0]["lexical"] < 0.08:
        raise SystemExit("Fireworks must retain a high-confidence offline routing signal")

    current_router = await router._rank(queries[2], skills, request, {})
    if current_router[0]["skill"].id != "lmlab-source-grounded-research":
        raise SystemExit(
            "Current router/product questions must select source-grounded research, "
            f"got {current_router[0]['skill'].id}"
        )

    casual = await router._rank(queries[-1], skills, request, {})
    casual_signal = casual[0]["score"] >= router.valves.min_score and (
        casual[0]["lexical"] >= 0.08 or casual[0]["semantic"] >= 0.925
    )
    if casual_signal:
        raise SystemExit(f"Casual conversation was routed to {casual[0]['skill'].id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: test-openwebui-skill-semantic-router.py /path/to/webui.db")
    asyncio.run(main(Path(sys.argv[1]).expanduser().resolve()))
