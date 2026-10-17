"""Exercise the actual authenticated chat endpoint, without a desktop session."""
import argparse
import atexit
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
import jwt
import requests
from dotenv import dotenv_values

parser = argparse.ArgumentParser()
parser.add_argument("runtime", type=Path)
parser.add_argument("--model", default="gemma4:26b-mlx")
parser.add_argument("--chat", help="Regenerate the current assistant of an existing requested chat")
parser.add_argument("--stop-task", help="Cancel only a preceding verification task")
parser.add_argument("--prompt", help="Use a specific architecture verification prompt")
parser.add_argument("--expect-icons", action="store_true")
parser.add_argument("--expect-brand-icons", action="store_true")
parser.add_argument("--expect-chart", action="store_true")
parser.add_argument("--expect-chart-type", help="Assert the numeric template type instead of the legacy bar fixture")
parser.add_argument("--expect-mixed", action="store_true", help="Require both architecture and numeric artifacts")
parser.add_argument("--expect-report", action="store_true", help="Require complete report sections, not only a preface")
parser.add_argument("--expect-speed", action="store_true")
parser.add_argument("--expect-intro", action="store_true")
parser.add_argument("--expect-separate-compute", action="store_true")
parser.add_argument("--cleanup-chat", help="Archive only a preceding synthetic verification chat")
args = parser.parse_args()
values = dotenv_values(args.runtime / ".env")
secret = values.get("WEBUI_SECRET_KEY") or (args.runtime / ".webui_secret_key").read_text()
db = sqlite3.connect(args.runtime / "data/webui.db")
owner = db.execute("SELECT user_id FROM tool WHERE id=?", ("openwebui_fireworks_renderer",)).fetchone()
assert owner, "Deploy the renderer before running authenticated live verification"
user_id = owner[0]
token = jwt.encode({"id":user_id, "exp":int(time.time())+900, "iat":int(time.time()), "jti":str(uuid.uuid4())}, secret, algorithm="HS256")
session = requests.Session()
session.headers["Authorization"] = "Bearer " + token
base = "http://127.0.0.1:3000"
if args.stop_task:
    session.post(base+"/api/tasks/stop/"+args.stop_task, timeout=30).raise_for_status()
if args.cleanup_chat:
    session.post(base+"/api/v1/chats/"+args.cleanup_chat+"/archive",timeout=30).raise_for_status()
tools = session.get(base+"/api/v1/tools/", timeout=30)
tools.raise_for_status()
assert "openwebui_fireworks_renderer" in tools.text, tools.status_code
prompt = "請繪製 Local AI 分層架構圖：遠端使用者、安全管理層、10G 資料邊緣、25G RDMA AI 骨幹、兩台 AI 工作站與儲存。分開畫 10G 交換器與 25G 交換器，標示資料與控制流。直接產生圖，不要程式碼。"
prompt = args.prompt or prompt
uid, aid = str(uuid.uuid4()), str(uuid.uuid4())
payload = {"model":args.model, "stream":True, "session_id":"server-render-regression", "params":{"function_calling":"native"}, "features":{}, "background_tasks":{}}
if args.chat:
    chat_id=args.chat
    row=db.execute("SELECT current_message_id FROM chat WHERE id=?", (chat_id,)).fetchone()
    previous_aid=row[0]
    row=db.execute("SELECT parent_id FROM chat_message WHERE id=?", (chat_id+"-"+previous_aid,)).fetchone()
    uid=row[0]
    prompt=json.loads(db.execute("SELECT content FROM chat_message WHERE id=?", (chat_id+"-"+uid,)).fetchone()[0])
    payload["chat_id"]=chat_id
else:
    chat=session.post(base+"/api/v1/chats/new", json={"chat":{"title":"[驗證] 伺服器架構圖整合","models":[args.model],"history":{"currentId":uid,"messages":{uid:{"id":uid,"role":"user","content":prompt,"childrenIds":[],"parentId":None}}},"messages":[{"role":"user","content":prompt}]}}, timeout=30)
    chat.raise_for_status()
    chat_id=chat.json()["id"]
    payload["chat_id"]=chat_id
    def archive_synthetic():
        try:
            current=session.get(base+'/api/v1/chats/'+chat_id,timeout=10)
            if current.ok and not current.json().get('archived'):
                session.post(base+'/api/v1/chats/'+chat_id+'/archive',timeout=10).raise_for_status()
        except requests.RequestException:pass
    atexit.register(archive_synthetic)
payload.update({"id":aid,"messages":[{"role":"user","content":prompt}], "user_message":{"id":uid,"role":"user","content":prompt,"parentId":None,"childrenIds":[aid]}})
socket = None
stream_observations = []
if args.expect_intro:
    import socketio
    socket = socketio.Client(reconnection=False)
    @socket.on("events")
    def observe(event):
        if event.get("chat_id") != chat_id:
            return
        item = event.get("data") or {}
        data = item.get("data") or {}
        now = time.monotonic()
        if item.get("type") == "response:completion" and data.get("type") == "response.output_text.delta" and data.get("delta", "").strip():
            stream_observations.append(("text", now, data["delta"]))
        if item.get("type") == "status" and any(label in data.get("description", "") for label in ("正在繪製技術架構圖","正在整理數據並繪製比較圖")):
            stream_observations.append(("render_start", now, ""))
    socket.connect(base, auth={"token":token}, socketio_path="ws/socket.io", transports=["websocket"], wait_timeout=15)
    payload["session_id"] = socket.get_sid()
started_at = time.monotonic()
response=session.post(base+"/api/chat/completions", json=payload, timeout=60)
response.raise_for_status()
print(json.dumps({"chat_id":chat_id,"started":response.json()},ensure_ascii=False),flush=True)
deadline=time.monotonic()+240
seen_code=False
while time.monotonic()<deadline:
    time.sleep(3)
    row=db.execute("SELECT content,output,done,files FROM chat_message WHERE id=?", (chat_id+"-"+aid,)).fetchone()
    if not row:
        continue
    content=json.loads(row[0] or '""')
    output=json.loads(row[1] or '[]') or []
    visible="".join(p.get("text","") for o in output if o.get("type")=="message" for p in o.get("content",[]))
    seen_code |= "```" in visible or "placeholder.com" in visible
    if args.expect_speed and not re.search(r"\n\n(?:≈ )?[\d.]+ tokens/s$", visible):
        continue  # done is persisted briefly before outlet filters finish.
    if row[2] and ("架構圖未能產生" in visible or "本次架構圖未完成" in visible):
        if socket:
            socket.disconnect()
        raise RuntimeError("Renderer failed: "+visible[-900:])
    if row[2] and args.expect_speed and re.search(r"\n\n(?:≈ )?[\d.]+ tokens/s$", visible) and not re.search(r"!\[.*?\]\(/static/.*?\.png\)",visible):
        if socket:socket.disconnect()
        raise RuntimeError('Completed reply has no rendered chart: '+visible[-700:])
    if row[2] and (re.search(r"!\[.*?\]\(/static/.*?\.png\)",visible) or "本次架構圖未完成" in visible):
        assert not seen_code, "Code was exposed in visible streaming output"
        assert content==visible, "Legacy content and structured output disagree"
        if args.expect_speed:
            assert "<!-- openwebui-response-speed" not in visible and "生成速度：" not in visible
        if args.expect_intro:
            text_events = [e for e in stream_observations if e[0] == "text"]
            render_events = [e for e in stream_observations if e[0] == "render_start"]
            assert text_events and render_events, str([(e[0],e[2][:80]) for e in stream_observations])
            assert text_events[0][1] < render_events[0][1], "Text arrived after rendering started"
            assert len(visible.split("![",1)[0].strip()) > 12, "Intro disappeared from persisted answer"
            print(json.dumps({"first_text_s":round(text_events[0][1]-started_at,2),"render_start_s":round(render_events[0][1]-started_at,2),"text_before_render":True,"speed":visible.splitlines()[-1]},ensure_ascii=False),flush=True)
        match=re.search(r"\]\((/static/[^)]+\.png)\)",visible)
        assert match, "No rendered artifact: "+visible
        image=session.get(base+match[1],timeout=30)
        assert image.status_code==200 and image.content.startswith(b"\x89PNG")
        if args.expect_icons:
            vector=session.get(base+match[1].replace('.png','.svg'),timeout=30)
            vector.raise_for_status()
            assert re.search(r'data-icon-pack="(?:local-architecture-v[12]|lucide|lobe|dashboard|simple)"',vector.text)
            assert vector.text.count('data-icon-id=') >= 3
        if args.expect_brand_icons:
            vector=session.get(base+match[1].replace('.png','.svg'),timeout=30)
            vector.raise_for_status()
            assert 'lobe:ollama' in vector.text and 'lobe:qwen-color' in vector.text
            assert 'icon-provenance' in vector.text and 'license-lobe' in vector.text
        if args.expect_chart:
            assert "/chart-" in match[1], "Architecture placeholder is not a numeric chart"
            vector=session.get(base+match[1].replace('.png','.svg'),timeout=30)
            vector.raise_for_status()
            assert 'data-chart-type=' in vector.text
            if args.expect_chart_type:
                assert 'data-chart-type="'+args.expect_chart_type+'"' in vector.text, "Wrong statistical template"
            else:
                assert '52' in vector.text and '68' in vector.text and 'tokens/s' in vector.text
                assert '+30.8%' in vector.text
            assert len(re.sub(r"!?\[[^\]]*\]\([^)]+\)", "", visible).strip()) > 12, "The numeric analysis was dropped"
        if args.expect_report:
            assert len(visible)>700 and len(re.findall(r'^#{1,4}\s',visible,re.M))>=3, 'Full report was replaced by a diagram summary'
        if args.expect_mixed:
            vectors=[]
            for path in re.findall(r'!\[[^\]]*\]\((/static/[^)]+\.png)\)',visible):
                value=session.get(base+path.replace('.png','.svg'),timeout=30);value.raise_for_status();vectors.append(value.text)
            assert any('data-chart-type=' in v for v in vectors),'Numeric result missing from mixed report'
            assert any('data-graph-role="node"' in v for v in vectors),'Architecture result missing from mixed report'
        if args.expect_separate_compute:
            import xml.etree.ElementTree as ET
            vector=session.get(base+match[1].replace('.png','.svg'),timeout=30)
            vector.raise_for_status()
            nodes=ET.fromstring(vector.text).findall('.//*[@data-graph-role="node"]')
            assert len(nodes) >= 7
            assert any(n.get("data-icon-id") in {"mini-pc","hardware:mini-ai-pc"} for n in nodes), "GX10 needs its own node"
            assert any(n.get("data-icon-id") in {"workstation","hardware:ai-workstation"} for n in nodes), "AI workstation needs a separate node"
            root=ET.fromstring(vector.text)
            drawn_edges=root.findall('.//*[@data-graph-role="edge"]')
            neighbors={n.get("data-node-id"):set() for n in nodes}
            for edge in drawn_edges:
                a,b=edge.get("data-source"),edge.get("data-target")
                neighbors[a].add(b)
                neighbors[b].add(a)
            reached=set()
            stack=[next(iter(neighbors))]
            while stack:
                node=stack.pop()
                if node not in reached:
                    reached.add(node)
                    stack.extend(neighbors[node]-reached)
            assert len(reached)==len(nodes), "An AI host/card was left disconnected from the network"
        # Verify the same representation fetched by frontend after reopening.
        loaded=session.get(base+"/api/v1/chats/"+chat_id,timeout=30)
        loaded.raise_for_status()
        actual=loaded.json()["chat"]["history"]["messages"][aid]
        assert actual["content"]==content and actual["output"]==output
        print(json.dumps({"ok":True,"chat_id":chat_id,"artifact":match[1],"png_bytes":len(image.content),"no_code_streamed":not seen_code,"content_output_identical":True,"reload_verified":True},ensure_ascii=False),flush=True)
        # The exit handler also archives a failed synthetic regression, so
        # test failures never become the user's apparent latest conversation.
        if socket:
            socket.disconnect()
        break
else:
    for task in response.json().get("task_ids", []):
        session.post(base+"/api/tasks/stop/"+task, timeout=30)
    raise RuntimeError("Live test did not produce a completed diagram within 240 seconds")
