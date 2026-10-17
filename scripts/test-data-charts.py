"""Data validation, rendering and response-policy regression tests."""
import asyncio
import importlib.util
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables/data-chart-examples"

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

renderer = load("renderer", "openwebui-fireworks-renderer-tool.py").Tools()
guard = load("guard", "openwebui-visual-diagram-filter.py").Filter()
base = dict(title="落地 AI 推論效能比較（示意）", labels=["方案 A", "方案 B"],
    series=[{"name":"推論速度", "values":[52, 68]}], unit="tokens/s",
    chart_type="bar", data_kind="illustrative", sources=[], note="僅供圖表樣式示範，非任何設備的實測或效能承諾。", better="higher")
quadrant_source = '''quadrantChart
title 路由器品牌定位（測試示意）
x-axis 低單價 (大眾市場) --> 高單價 (高端/專業市場)
y-axis 低功能 (簡單/家用) --> 高功能 (進階/電競/企業)
quadrant-1 示意
"TP-Link": [0.25, 0.4]
"Xiaomi": [0.15, 0.3]
"Google Nest": [0.3, 0.25]
"Amazon Eero": [0.35, 0.2]
"ASUS (ROG/AiMesh)": [0.75, 0.85]
"Netgear (Nighthawk)": [0.8, 0.75]
"Ubiquiti (UniFi)": [0.9, 0.95]'''
quadrant = guard._quadrant_data(quadrant_source)

async def main():
    for change in [dict(data_kind="reported"), dict(data_kind="unknown"), dict(unit=""),
        dict(series=[{"values":[float("nan"), 3]}]), dict(series=[{"values":[True, 3]}]),
        dict(series=[{"values":[None, 3]}]), dict(series=[{"values":[1]}]),
        dict(labels=["A", "A"]), dict(note=""), dict(sources="not a list")]:
        try:
            renderer._chart_data(**(base | change))
        except ValueError:
            pass
        else:
            raise AssertionError(change)
    assert renderer._chart_number(.000002) == "2e-06"
    for prompt in ["比較兩個方案的推論效能", "畫長條圖", "分析每季營收趨勢", "比較延遲 12ms 與 7ms", "能否研究一下市場站比給我圖表", "品牌定位矩陣", "四象限圖"]:
        assert guard._wants_chart(prompt), prompt
    for prompt in ["192.168.50.166:3000 登入不了", "請畫 25G RDMA 架構圖", "比較 API 的使用方法", "給我折線圖的 Python 程式碼"]:
        assert not guard._wants_chart(prompt), prompt
    req = SimpleNamespace(state=SimpleNamespace())
    body = {"messages":[{"role":"user", "content":"比較推論速度 52 tokens/s 和 68 tokens/s"}]}
    await guard.inlet(body, req)
    assert req.state.fireworks_diagram["mode"] == "chart"
    assert "render_data_chart" in body["messages"][0]["content"]
    event = {"choices":[{"delta":{"content":"方案 B 較快，但這是示意資料。\n```svg\n<svg/>\n```"}}]}
    guard.stream(event, req)
    assert event["choices"][0]["delta"]["content"] == "方案 B 較快，但這是示意資料。\n"
    req.state.fireworks_diagram["chart_artifacts"] = ["![比較](/static/test.png)"]
    body["messages"].append({"role":"assistant", "content":""})
    response = (await guard.outlet(body, __request__=req))["messages"][-1]
    assert "方案 B 較快" in response["content"] and "test.png" in response["content"]
    assert "```" not in response["content"] and "<svg" not in response["content"]
    assert response["content"] == response["output"][0]["content"][0]["text"]
    # An unfenced data object is also recovered without showing source or
    # executing model code. The fake renderer proves this path deterministically.
    recovered_guard = load("recovery_guard", "openwebui-visual-diagram-filter.py").Filter()
    class FakeRenderer:
        async def render_data_chart(self, **kwargs):
            assert kwargs["series"][0]["values"] == [52,68]
            return "![已繪製](/static/recovered.png)"
    recovered_guard._renderer = lambda: FakeRenderer()
    req2 = SimpleNamespace(state=SimpleNamespace())
    body2 = {"messages":[{"role":"user","content":"畫長條圖"}]}
    await recovered_guard.inlet(body2, req2)
    body2["messages"].append({"role":"assistant","content":"比較結論。"+json.dumps(base)+"![猜測](https://example.invalid/fake.png)"})
    recovered = (await recovered_guard.outlet(body2, __request__=req2))["messages"][-1]["content"]
    assert "recovered.png" in recovered and "比較結論" in recovered
    assert '"series"' not in recovered and "example.invalid" not in recovered
    assert quadrant["data_kind"] == "illustrative" and quadrant["series"][0]["values"][4] == .75
    assert "非市場調查" in quadrant["note"]
    assert guard._quadrant_data(quadrant_source.replace('[0.25, 0.4]', '[1.25, 0.4]')) is None
    assert guard._quadrant_data(quadrant_source+'\nimport os') is None
    assert guard._quadrant_data(quadrant_source.replace('x-axis','bad-axis')) is None
    for change in [dict(series=[quadrant["series"][0]]), dict(series=[quadrant["series"][0], {"name":"Y", "values":[2]*7}])]:
        try:
            renderer._chart_data(**(quadrant | change))
        except ValueError:
            pass
        else:
            raise AssertionError(change)
    class QuadrantRenderer:
        async def render_data_chart(self, **kwargs):
            assert kwargs["chart_type"] == "quadrant" and kwargs["data_kind"] == "illustrative"
            return "![定位圖](/static/quadrant.png)"
    recovered_guard._renderer = lambda: QuadrantRenderer()
    # This previously missed all diagram/chart intent checks. It must still
    # recover unsolicited Mermaid without evaluating source or losing prose.
    body3 = {"messages":[{"role":"user","content":"分析市場"},{"role":"assistant","content":"分析摘要。\n```mermaid\n"+quadrant_source+"\n```\n定性示意。"}]}
    fixed = (await recovered_guard.outlet(body3))["messages"][-1]
    assert "quadrant.png" in fixed["content"] and "分析摘要" in fixed["content"]
    assert "```" not in fixed["content"] and "quadrantChart" not in fixed["content"]
    assert fixed["content"] == fixed["output"][0]["content"][0]["text"]
    ET.fromstring(renderer._chart_svg(renderer._chart_data(**quadrant)))
    print("PASS: invalid/missing data, provenance, chart intent, no code streaming, analysis preserved, content/output sync")
    if not os.environ.get("OPENWEBUI_TEST_RENDER"):
        return
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ["OPENWEBUI_FIREWORKS_SKILL_ROOT"] = str(ROOT / "resources/openwebui-managed-skills/fireworks-tech-graph")
    os.environ["OPENWEBUI_FIREWORKS_OUTPUT_DIR"] = str(OUT / "generated")
    examples = {
        "brand-positioning":quadrant,
        "inference-comparison":base,
        "latency-grouped":base | dict(title="網路延遲比較（示意）", labels=["輕量工作負載", "中量工作負載", "重度工作負載"], unit="ms", better="lower", series=[{"name":"方案 A", "values":[12, 24, 38]}, {"name":"方案 B", "values":[8, 15, 27]}]),
        "throughput-trend":base | dict(title="吞吐量時間趨勢（示意）", chart_type="line", labels=["09:00", "09:05", "09:10", "09:15", "09:20", "09:25"], unit="Gbps", series=[{"name":"資料流量", "values":[2.1, 3.8, 3.2, 5.6, 4.8, 6.2]}]),
        "horizontal":base | dict(title="路由器方案功耗比較（示意）", chart_type="horizontal_bar", labels=["方案 A：單機工作模式", "方案 B：雙節點協同工作模式", "方案 C：多節點工作模式"], unit="W", better="lower", series=[{"name":"功耗", "values":[21, 32, 47]}]),
        "negative-values":base | dict(title="季度變化（示意）", labels=["第一季", "第二季", "第三季"], unit="%", series=[{"name":"變化", "values":[-5, 0, 8]}]),
        "all-zero":base | dict(title="零值比較（示意）", series=[{"name":"數值", "values":[0, 0]}]),
    }
    for slug, example in examples.items():
        result = await renderer.render_data_chart(**example)
        match = re.search(r"/(chart-[\w-]+)\.png", result)
        assert match, result
        for ext in ("svg", "png", "html", "csv"):
            source = OUT / "generated" / (match[1]+"."+ext)
            assert source.is_file()
            shutil.copy2(source, OUT / (slug+"."+ext))
        svg = (OUT/(slug+".svg")).read_text()
        ET.fromstring(svg)
        assert "示意資料" in svg
        assert ("非市場調查" if slug == "brand-positioning" else "非任何設備") in svg
        if slug == "inference-comparison":
            assert "+30.8%" in svg
        if slug == "all-zero":
            assert "%</text>" not in svg
        assert (OUT/(slug+".png")).read_bytes().startswith(b"\x89PNG")
        print("PASS render:", slug)

asyncio.run(main())
