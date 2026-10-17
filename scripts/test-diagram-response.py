"""Regression checks for code leaks, stale output, and unrelated-topic damage."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("guard", Path(__file__).with_name("openwebui-visual-diagram-filter.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

async def main():
    guard = module.Filter()
    request = SimpleNamespace(state=SimpleNamespace())
    second = SimpleNamespace(state=SimpleNamespace())
    body = {"terminal_id": "disconnected", "messages": [{"role":"user", "content":"請畫 Local AI 架構圖，不要輸出程式碼"}]}
    await guard.inlet(body, request)
    assert "terminal_id" not in body
    assert "openwebui_fireworks_renderer" in body["tool_ids"]
    call = [{"index":0, "function":{"name":"render_technical_architecture", "arguments":"{}"}}]
    event = {"choices":[{"delta":{"content":"```bash\nsecret source", "tool_calls":call}, "finish_reason":None}]}
    guard.stream(event, request)
    assert event["choices"][0]["delta"]["content"] == ""
    assert event["choices"][0]["delta"]["tool_calls"] == call
    ordinary = {"choices":[{"delta":{"content":"一般文字"}}]}
    assert guard.stream(ordinary, second)["choices"][0]["delta"]["content"] == "一般文字"
    artifact = "![專屬圖](/static/openwebui-generated/fireworks/test.png)"
    request.state.fireworks_diagram["artifact"] = artifact
    body["messages"].append({"role":"assistant","content":"old code", "output":[{"type":"message","content":[{"type":"output_text","text":"old code"}]}]})
    result = await guard.outlet(body, __request__=request)
    response = result["messages"][-1]
    assert response["content"] == artifact
    assert response["output"][0]["content"][0]["text"] == artifact
    assert "old code" not in json.dumps(response)
    assert not guard._wants_diagram("分析 ASUS 路由器市場")
    assert not guard._wants_diagram("給我架構圖的 Python 程式碼")
    parsed = guard._diagram_data('untrusted shell\n' + json.dumps({"title":"測試","nodes":[{"id":"a"},{"id":"b"}],"edges":[{"from":"a","to":"b"}]}) + '\nrm -rf stuff')
    assert parsed["nodes"][1]["level"] == 1
    request.state.fireworks_diagram = {"chunks": ["![fake](https://via.placeholder.com/x)"], "size": 50}
    response = (await guard.outlet(body, __request__=request))["messages"][-1]
    assert "未完成" in response["content"] and "placeholder.com" not in json.dumps(response)
    print("PASS: tool selection, streaming/code suppression, request isolation, content/output sync, topic scope, JSON-only recovery, no fabricated images")

    renderer_spec = importlib.util.spec_from_file_location("renderer", Path(__file__).with_name("openwebui-fireworks-renderer-tool.py"))
    renderer_module = importlib.util.module_from_spec(renderer_spec)
    renderer_spec.loader.exec_module(renderer_module)
    renderer = renderer_module.Tools()
    nodes = [{"id": "a", "label": "主機 A", "level": 0}, {"id": "b", "label": "主機 B", "level": 1}]
    for edges in ([], [{"from": "a", "to": "missing"}]):
        try:
            renderer._layout("測試", "", nodes, edges, [], 3)
        except ValueError:
            pass
        else:
            raise AssertionError("Missing/invalid connections must not silently disappear")
    result = renderer._layout("測試", "", nodes, [{"from": "a", "to": "b"}], [], 3)
    assert result["arrows"][0]["source"] == "a"
    print("PASS: required valid diagram connections")
    if os.environ.get("OPENWEBUI_TEST_RENDER"):
        result = await renderer.render_technical_architecture("中文連線驗證", nodes, [{"from":"a", "to":"b", "label":"資料流"}])
        assert ".png" in result, result
        print(result)
        branched = [
            {"id":"remote", "label":"遠端使用者", "level":0, "group":"access"},
            {"id":"mgmt", "label":"管理層", "level":1, "group":"management"},
            {"id":"edge", "label":"10G 資料邊緣", "level":2, "group":"network"},
            {"id":"fabric", "label":"25G RDMA AI 骨幹", "level":3, "group":"network"},
            {"id":"compute", "label":"AI 工作站", "level":4, "group":"compute"},
            {"id":"storage", "label":"儲存層", "level":4, "group":"compute"},
        ]
        relations = [
            {"from":"remote", "to":"mgmt", "label":"控制指令", "tone":"remote"},
            {"from":"mgmt", "to":"edge", "label":"管理配置", "tone":"remote"},
            {"from":"edge", "to":"fabric", "label":"資料流"},
            {"from":"fabric", "to":"compute", "label":"RDMA 通訊", "tone":"active"},
            {"from":"compute", "to":"storage", "label":"資料寫入"},
            {"from":"storage", "to":"compute", "label":"資料回傳"},
        ]
        result = await renderer.render_technical_architecture("階層與同層雙向連線驗證", branched, relations)
        assert ".png" in result, result
        print(result)
        # A parallel compute branch skips the fabric layer. Distinct endpoint
        # counts previously caused 3/9px jogs and rejected the whole diagram.
        skip_nodes = [
            {"id":"user","label":"使用者服務","level":0,"icon":"users"},
            {"id":"vpn","label":"路由器／VPN","level":1,"icon":"vpn"},
            {"id":"access","label":"10G Access Switch","level":2,"icon":"switch"},
            {"id":"rdma","label":"25G RDMA Switch","level":3,"icon":"rdma-switch"},
            {"id":"nic","label":"Intel E800 NIC","level":4,"icon":"network-card"},
            {"id":"gx10","label":"GX10","detail":"連線介面待確認","level":4,"icon":"mini-pc"},
            {"id":"ws","label":"AI 工作站","level":5,"icon":"workstation"},
        ]
        skip_edges = [{"from":a,"to":b,"label":label,"direction":"none"} for a,b,label in [
            ("user","vpn","遠端存取"),("vpn","access","LAN"),("access","rdma","資料互連"),
            ("rdma","nic","RDMA"),("nic","ws","PCIe"),("access","gx10","介面待確認")]]
        result = await renderer.render_technical_architecture("跨層分支路由驗證",skip_nodes,skip_edges)
        assert ".png" in result, result
        print(result)

asyncio.run(main())
