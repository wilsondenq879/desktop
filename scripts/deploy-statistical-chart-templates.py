"""Backed-up versioned deployment. Preserve current tools, access, and chat history."""
import argparse
import importlib.util
import json
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

import jwt
import requests
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('runtime',type=Path)
parser.add_argument('--base',default='http://127.0.0.1:3000')
args=parser.parse_args()
pack=ROOT/'deliverables/statistical-chart-templates-v1'
catalog=json.loads((pack/'catalog.json').read_text())
assert len(catalog['templates'])==19
for template in catalog['templates']:
    for extension in ['svg','png','html','csv']:
        assert (pack/(template['id']+'.'+extension)).is_file()

stamp=str(time.time_ns())
db=sqlite3.connect(args.runtime/'data/webui.db')
backup=args.runtime/'data'/('webui-before-statistical-templates-'+stamp+'.db')
with sqlite3.connect(backup) as target:db.backup(target)
owner=db.execute('SELECT user_id FROM tool WHERE id=?',('openwebui_fireworks_renderer',)).fetchone()[0]
config=dotenv_values(args.runtime/'.env')
secret=config.get('WEBUI_SECRET_KEY') or (args.runtime/'.webui_secret_key').read_text()
session=requests.Session()
session.headers['Authorization']='Bearer '+jwt.encode({'id':owner,'iat':int(time.time()),'exp':int(time.time())+900,'jti':str(uuid.uuid4())},secret,algorithm='HS256')


def api(path,payload=None):
    response=session.get(args.base+path,timeout=30) if payload is None else session.post(args.base+path,json=payload,timeout=90)
    response.raise_for_status()
    return response.json()


versions={}
snapshot_dir=args.runtime/'data'/('statistical-templates-backup-'+stamp)
snapshot_dir.mkdir()
# Update the tiny raster runtime as well as the Tool/Filter code. An explicit
# server skill-root environment variable may still point to the legacy path.
for root in [args.runtime/'skills/fireworks-tech-graph',args.runtime/'data/skills/fireworks-tech-graph']:
    if not root.is_dir():continue
    for name in ['png_export.py','fireworks.py']:
        dest=root/'scripts'/name
        if dest.exists():
            target=snapshot_dir/('runtime-root' if root.parent==args.runtime/'skills' else 'data-root')
            target.mkdir(exist_ok=True);shutil.copy2(dest,target/name)
            shutil.copy2(ROOT/'resources/openwebui-managed-skills/fireworks-tech-graph/scripts'/name,dest)
static=Path(importlib.util.find_spec('open_webui').origin).parent/'static/statistical-charts/v1'
for destination in (args.runtime/'data/statistical-charts/v1',static):
    if destination.exists():
        shutil.copytree(destination,snapshot_dir/('persistent-gallery' if destination==args.runtime/'data/statistical-charts/v1' else 'static-gallery'))
    shutil.copytree(pack,destination,dirs_exist_ok=True,ignore=shutil.ignore_patterns('generated'))
for kind,id,file in [('tools','openwebui_fireworks_renderer','openwebui-fireworks-renderer-tool.py'),('functions','openwebui_visual_diagram_guard','openwebui-visual-diagram-filter.py')]:
    current=api(f'/api/v1/{kind}/id/{id}')
    (snapshot_dir/(id+'.json')).write_text(json.dumps(current,ensure_ascii=False,indent=2))
    dest=args.runtime/file
    if dest.exists():shutil.copy2(dest,snapshot_dir/file)
    shutil.copy2(ROOT/'scripts'/file,dest)
    saved=api(f'/api/v1/{kind}/id/{id}/update',{'id':id,'name':current['name'],'content':dest.read_text(),'meta':current.get('meta') or {},
        'commit_message':'可重用統計圖表樣板：先文字再成品，資料驗證，維持既有架構圖與圖庫'})
    versions[id]=saved['version_id']

id='numeric-comparison-charts'
current=api('/api/v1/skills/id/'+id)
(snapshot_dir/(id+'.json')).write_text(json.dumps(current,ensure_ascii=False,indent=2))
source=ROOT/'resources/openwebui-managed-skills'/id/'SKILL.md'
skill=args.runtime/'skills'/id
if skill.exists():shutil.copytree(skill,snapshot_dir/'skill')
(skill/'references').mkdir(parents=True,exist_ok=True)
shutil.copy2(source,skill/'SKILL.md')
shutil.copy2(pack/'catalog.json',skill/'references/chart-template-catalog.json')
saved=api('/api/v1/skills/id/'+id+'/update',{'id':id,'name':current['name'],
    'description':'比較、趨勢、組成、關聯與專案時程的可重用統計樣板：先文字後成品，不顯示繪圖代碼。',
    'content':source.read_text(),'expected_version_id':current['version_id'],
    'operations':[{'op':'put','path':'references/chart-template-catalog.json','content':(pack/'catalog.json').read_text()}],
    'commit_message':'加入19種統計圖表配置、資料型態與按需範例；不變更權限'})
versions[id]=saved['version_id']
assert saved.get('access_grants')==current.get('access_grants'),'Skill access changed'
tool=api('/api/v1/tools/id/openwebui_fireworks_renderer')
assert {s['name'] for s in tool['specs']}=={'render_technical_architecture','render_data_chart','search_diagram_assets'}
spec=next(s for s in tool['specs'] if s['name']=='render_data_chart')
assert 'options' in spec['parameters']['properties']
assert 'version: 6.2.0' in tool['content']
guard=api('/api/v1/functions/id/openwebui_visual_diagram_guard')
assert guard.get('is_active') and guard.get('is_global')
for file in ['preview.html','gantt.png','radar.svg','gantt.html','catalog.json']:
    response=session.get(args.base+'/static/statistical-charts/v1/'+file,timeout=30)
    response.raise_for_status();assert len(response.content)>100
print(json.dumps({'ok':True,'backup':str(backup),'file_backup':str(snapshot_dir),'versions':versions,'templates':19,
    'policy_global':True,'preview':args.base+'/static/statistical-charts/v1/preview.html'},ensure_ascii=False))
