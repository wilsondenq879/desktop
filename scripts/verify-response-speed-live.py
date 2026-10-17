"""Check a plain, non-diagram answer receives a measured persistent footer."""
import argparse
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
parser.add_argument("runtime",type=Path)
parser.add_argument("--model",default="gpt-oss:20b")
args = parser.parse_args()
db = sqlite3.connect(args.runtime/"data/webui.db")
owner = db.execute("SELECT user_id FROM tool WHERE id=?",("openwebui_fireworks_renderer",)).fetchone()[0]
values = dotenv_values(args.runtime/".env")
secret = values.get("WEBUI_SECRET_KEY") or (args.runtime/".webui_secret_key").read_text()
session = requests.Session()
session.headers["Authorization"] = "Bearer "+jwt.encode({"id":owner,"iat":int(time.time()),"exp":int(time.time())+600,"jti":str(uuid.uuid4())},secret,algorithm="HS256")
base = "http://127.0.0.1:3000"
uid, aid = str(uuid.uuid4()), str(uuid.uuid4())
prompt = "請用繁體中文以一句話解釋網路交換器的用途，不要畫圖。"
user = {"id":uid,"role":"user","content":prompt,"parentId":None,"childrenIds":[aid]}
response = session.post(base+"/api/v1/chats/new",json={"chat":{"title":"[驗證] 一般回答速度","models":[args.model],"history":{"currentId":uid,"messages":{uid:user}},"messages":[user]}},timeout=30)
response.raise_for_status()
chat_id = response.json()["id"]
response = session.post(base+"/api/chat/completions",json={"chat_id":chat_id,"id":aid,"model":args.model,"stream":True,"session_id":"speed-regression","params":{},"features":{},"background_tasks":{},"messages":[{"role":"user","content":prompt}],"user_message":user},timeout=60)
response.raise_for_status()
print(json.dumps({"chat_id":chat_id,"started":True}),flush=True)
try:
    deadline = time.monotonic()+180
    while time.monotonic()<deadline:
        row = db.execute("SELECT content,output,done FROM chat_message WHERE id=?",(chat_id+"-"+aid,)).fetchone()
        if row and row[2]:
            content, output = json.loads(row[0] or '""'), json.loads(row[1] or "[]")
            visible = "".join(p.get("text","") for item in output if item.get("type")=="message" for p in item.get("content",[]) if p.get("type")=="output_text")
            if not re.search(r"\n\n(?:≈ )?[\d.]+ tokens/s$", visible):
                time.sleep(.5)
                continue
            assert content == visible
            assert "<!-- openwebui-response-speed" not in visible and "生成速度：" not in visible
            assert "交換器" in visible and "![" not in visible
            loaded = session.get(base+"/api/v1/chats/"+chat_id,timeout=30)
            loaded.raise_for_status()
            actual = loaded.json()["chat"]["history"]["messages"][aid]
            assert actual["content"] == content and actual["output"] == output
            print(json.dumps({"ok":True,"plain_answer":True,"speed":visible.splitlines()[-1],"reload_verified":True},ensure_ascii=False),flush=True)
            break
        time.sleep(2)
    else:
        for task in response.json().get("task_ids",[]):
            session.post(base+"/api/tasks/stop/"+task,timeout=30)
        raise RuntimeError("Plain speed verification timed out")
finally:
    session.post(base+"/api/v1/chats/"+chat_id+"/archive",timeout=30).raise_for_status()
