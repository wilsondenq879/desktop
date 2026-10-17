"""Fast architecture prose, source suppression, and honest throughput metrics."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Filter()

async def main():
    guard = load("visual", "openwebui-visual-diagram-filter.py")
    req = SimpleNamespace(state=SimpleNamespace())
    body = {"messages":[{"role":"user","content":"畫一張 AI 工作站網路架構圖"}]}
    await guard.inlet(body, req)
    shown = []
    for text in ["上層是遠端使用者", "，透過 VPN 連到管理層。", "\n\n", "`", "``json\n", '{"nodes":', "[]}"]:
        event = {"choices":[{"delta":{"content":text}}]}
        shown.append(guard.stream(event, req)["choices"][0]["delta"]["content"])
    assert "管理層。" in "".join(shown[:2]), "Prose must show before diagram/source finishes"
    assert "```" not in "".join(shown) and '"nodes"' not in "".join(shown)
    req.state.fireworks_diagram["artifact"] = "![架構](/static/test.png)"
    body["messages"].append({"role":"assistant","content":""})
    answer = (await guard.outlet(body, __request__=req))["messages"][-1]
    assert "管理層。" in answer["content"] and "test.png" in answer["content"]
    # With no preface, complete tool node data can provide a grounded summary.
    req2 = SimpleNamespace(state=SimpleNamespace())
    await guard.inlet({"messages":[{"role":"user","content":"畫架構圖"}]}, req2)
    tool = [{"index":0,"function":{"name":"render_technical_architecture","arguments":'{"nodes":[{"id":"a","label":"工作站","level":0},{"id":"b","label":"NAS","level":1}],"edges":[{"from":"a","to":"b"}]}'}}]
    event = guard.stream({"choices":[{"delta":{"tool_calls":tool}}]}, req2)
    assert "工作站" in event["choices"][0]["delta"]["content"]
    assert event["choices"][0]["delta"]["tool_calls"] == tool
    short_guard = load("short_visual", "openwebui-visual-diagram-filter.py")
    async def short_pass(body, text, request, user):
        return "交換器作為中心，三台設備各自連入。\n\n", {"eval_count":20,"eval_duration":500000000}
    short_guard._generate_preface = short_pass
    req3 = SimpleNamespace(state=SimpleNamespace())
    await short_guard.inlet({"model":"test","messages":[{"role":"user","content":"畫架構圖"}]}, req3, __user__={"id":"test"})
    first = short_guard.stream({"choices":[{"delta":{}}]}, req3)
    assert "交換器作為中心" in first["choices"][0]["delta"]["content"]
    async def empty_pass(*args):return '',None
    short_guard._generate_preface=empty_pass
    cold=SimpleNamespace(state=SimpleNamespace())
    await short_guard.inlet({'model':'test','messages':[{'role':'user','content':'畫兩台GPU工作站連接25G交換機架構圖'}]},cold,__user__={'id':'test'})
    assert '兩台GPU工作站' in cold.state.fireworks_diagram['prelude'] and '25G交換機' in cold.state.fireworks_diagram['prelude']
    second = short_guard.stream({"choices":[{"delta":{}}]}, req3)
    assert "交換器作為中心" not in second["choices"][0]["delta"].get("content", "")
    structured = {"model":"gemma4:26b-mlx","tool_ids":["openwebui_fireworks_renderer"],"messages":[{"role":"system","content":"old tool instructions"},{"role":"user","content":"請繪製 ASUS AI 階層圖"}]}
    req4 = SimpleNamespace(state=SimpleNamespace())
    await guard.inlet(structured, req4)
    assert structured["tool_ids"] == [] and structured["response_format"]["type"] == "json_schema"
    assert "不要工具呼叫" in structured["messages"][0]["content"]
    assert "old tool instructions" not in structured["messages"][0]["content"]
    final_request = guard.request({"tools":[{"type":"function","function":{"name":"run_command"}}],"messages":[{"role":"system","content":"late skill catalog"}]},req4)
    assert final_request["tools"] == [] and final_request["tool_choice"] == "none"
    assert "late skill catalog" not in str(final_request["messages"])
    assert final_request["options"]["think"] is False
    ordinary_gemma = {"model":"gemma4:26b-mlx","tool_ids":["existing"],"messages":[{"role":"user","content":"你好"}]}
    await guard.inlet(ordinary_gemma, SimpleNamespace(state=SimpleNamespace()))
    assert ordinary_gemma["tool_ids"] == ["existing"] and "response_format" not in ordinary_gemma
    # A model which returns only explanatory prose must still have a server-
    # owned constrained recovery path, not a fabricated image/false success.
    recover_guard = load("native_recovery", "openwebui-visual-diagram-filter.py")
    async def recover_plan(request, user, model, text, context):
        return {"title":"復原", "nodes":[{"id":"a","label":"A","level":0},{"id":"b","label":"B","level":1}],"edges":[{"from":"a","to":"b"}]}, {"eval_count":20,"eval_duration":1e9}
    class Renderer:
        async def render_technical_architecture(self, **kwargs):
            assert kwargs["edges"][0]["to"] == "b"
            return "![已完成](/static/recovery.png)"
    recover_guard._recover_plan = recover_plan
    recover_guard._renderer = lambda: Renderer()
    req5 = SimpleNamespace(state=SimpleNamespace(response_speed={"calls":{}}))
    recover_body = {"model":"gpt-oss:20b","messages":[{"role":"user","content":"請繪製架構圖"}]}
    await recover_guard.inlet(recover_body, req5)
    req5.state.fireworks_diagram["intro"] = "分開運算與儲存。"
    req5.state.fireworks_diagram["chunks"] = ["只有文字，未呼叫工具。"]
    recover_body["messages"].append({"role":"assistant","content":"只有文字"})
    recovered = (await recover_guard.outlet(recover_body,__request__=req5,__user__={"id":"test"}))["messages"][-1]
    assert "recovery.png" in recovered["content"] and "未完成" not in recovered["content"]
    assert len(req5.state.response_speed["extra_usage"]) == 1
    indented = {"pending":"", "intro":""}
    assert recover_guard._preview(indented,"                            架構說明。") == "架構說明。"
    hardware = {"title":"測試","nodes":[{"id":"gx","label":"GX10"},{"id":"ws","label":"AI 工作站"},{"id":"nic","label":"Intel E800"},{"id":"access","label":"10G Switch"},{"id":"fabric","label":"25G RDMA Switch"}],"edges":[{"from":"nic","to":"gx"},{"from":"fabric","to":"ws"}]}
    safe = guard._enforce_host_constraint(hardware,"GX10／AI 工作站與 Intel E800")
    assert any(e["from"]=="nic" and e["to"]=="ws" for e in safe["edges"])
    assert not any({e["from"],e["to"]}=={"nic","gx"} for e in safe["edges"])
    assert any(e["to"]=="gx" and e["dashed"] for e in safe["edges"])
    assert any({e["from"],e["to"]}=={"fabric","nic"} for e in safe["edges"])
    assert hardware["edges"][0]["to"]=="gx", "Do not mutate raw model data"
    speed = load("speed", "openwebui-response-speed-filter.py")
    state = {"calls":{}}
    metric_req = SimpleNamespace(state=SimpleNamespace(response_speed=state))
    for usage_id, count, seconds in [("first",100,2), ("second",60,2), ("second",60,2)]:
        speed.stream({"id":usage_id,"usage":{"eval_count":count,"eval_duration":seconds*1e9}}, metric_req)
    assert "40.0 tokens/s" in speed._footer(state, {}, None), "Use weighted per-call decode duration, not average of speeds"
    assert len(state["calls"]) == 2, "Do not count duplicate usage snapshots"
    assert "50.0 tokens/s" in speed._footer({}, {"eval_count":100,"eval_duration":2e9,"output_tokens":500}, 50)
    assert "50.0 tokens/s" in speed._footer({}, {"predicted_n":100,"predicted_ms":2000}, None)
    assert speed._footer({}, {"output_tokens":100}, 10) == "≈ 10.0 tokens/s"
    for usage in ({}, {"eval_count":10,"eval_duration":0}, {"output_tokens":float("nan")}, {"output_tokens":True}):
        assert "N/A" in speed._footer({},usage,None)
    assert "38.5 tokens/s" in speed._footer({}, {"response_token/s":38.5},None)
    message = {"id":"target","role":"assistant","content":"分析內容", "output":[{"type":"function_call","id":"keep"},{"type":"message","content":[{"type":"output_text","text":"分析內容"}]}], "usage":{"eval_count":100,"eval_duration":2e9}}
    history = {"id":"target", "messages":[{"id":"old","role":"assistant","content":"舊回答"}, message]}
    speed.outlet(history)
    speed.outlet(history)
    assert message["content"] == "分析內容\n\n50.0 tokens/s"
    assert "<!--" not in message["content"] and "生成速度" not in message["content"]
    legacy = "分析內容\n\n<!-- openwebui-response-speed -->\n> 生成速度：55.0 tokens/s（模型解碼平均；不含繪圖／工具等待）\n<!-- /openwebui-response-speed -->"
    assert speed._strip_footer(legacy) == "分析內容"
    assert speed._strip_footer("結果 55.0 tokens/s\n\n補充說明") == "結果 55.0 tokens/s\n\n補充說明"
    assert message["output"][0]["id"] == "keep" and history["messages"][0]["content"] == "舊回答"
    assert message["content"] == message["output"][1]["content"][0]["text"]
    task = {"messages":[{"role":"assistant","content":"{\"title\":\"test\"}"}]}
    speed.outlet(task, __metadata__={"task":"title_generation"})
    assert "生成速度" not in task["messages"][0]["content"]
    print("PASS: early prose, split fences, hidden JSON, grounded tool-first summary, weighted decode metrics, units, missing usage, deduplication, persistence and tool history")

asyncio.run(main())
