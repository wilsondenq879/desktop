"""Install local icon assets first, then publish versioned renderer/filter/skill updates."""
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
args=parser.parse_args()
pack=ROOT/'deliverables/architecture-icon-pack-v2'
source=ROOT/'resources/architecture-icon-pack'
assert all((pack/(name+'.png')).is_file() for name in ['layered','star','dual-compute','rack','dataflow','ecosystem'])
assert (pack/'NOTICE.html').is_file()
db=sqlite3.connect(args.runtime/'data/webui.db')
stamp=str(time.time_ns())
backup=args.runtime/'data'/('webui-before-extended-icons-'+stamp+'.db')
with sqlite3.connect(backup) as target: db.backup(target)
owner=db.execute('SELECT user_id FROM tool WHERE id=?',('openwebui_fireworks_renderer',)).fetchone()[0]
config=dotenv_values(args.runtime/'.env')
secret=config.get('WEBUI_SECRET_KEY') or (args.runtime/'.webui_secret_key').read_text()
session=requests.Session()
session.headers['Authorization']='Bearer '+jwt.encode({'id':owner,'iat':int(time.time()),'exp':int(time.time())+900,'jti':str(uuid.uuid4())},secret,algorithm='HS256')
base='http://127.0.0.1:3000'

def api(path,payload=None):
    response=session.get(base+path,timeout=30) if payload is None else session.post(base+path,json=payload,timeout=90)
    response.raise_for_status()
    return response.json()

skill=args.runtime/'skills/fireworks-tech-graph'
icons=skill/'assets/icons/technical'
icons.mkdir(parents=True,exist_ok=True)
for name in ('manifest.json','hardware.json'):
    dest=icons/name
    if dest.exists(): shutil.copy2(dest,dest.with_name(dest.name+'.before-v2-'+stamp))
    shutil.copy2(source/name,dest)
if (icons/'extended').exists():
    shutil.copytree(icons/'extended',args.runtime/'data'/('icon-library-before-v2-'+stamp))
shutil.copytree(source/'extended',icons/'extended',dirs_exist_ok=True)
static=Path(importlib.util.find_spec('open_webui').origin).parent/'static/architecture-icons'
for dest in (args.runtime/'data/architecture-icons/v2',static/'v2'):
    shutil.copytree(pack,dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('generated'))
versions={}
for kind,id,file in [('tools','openwebui_fireworks_renderer','openwebui-fireworks-renderer-tool.py'),('functions','openwebui_visual_diagram_guard','openwebui-visual-diagram-filter.py')]:
    dest=args.runtime/file
    if dest.exists(): shutil.copy2(dest,dest.with_name(dest.name+'.before-v2-'+stamp))
    shutil.copy2(ROOT/'scripts'/file,dest)
    current=api(f'/api/v1/{kind}/id/{id}')
    saved=api(f'/api/v1/{kind}/id/{id}/update',{'id':id,'name':current['name'],'content':dest.read_text(),'meta':current.get('meta') or {},
        'commit_message':'加入四套本機 SVG 圖庫、硬體元件、按需搜尋及六種保持真實關係的構圖'})
    versions[id]=saved['version_id']
skill_source=ROOT/'resources/openwebui-managed-skills/fireworks-tech-graph'
reference=skill_source/'references/extended-asset-library.md'
shutil.copy2(skill_source/'SKILL.md',skill/'SKILL.md')
shutil.copy2(reference,skill/'references'/reference.name)
current=api('/api/v1/skills/id/fireworks-tech-graph')
saved=api('/api/v1/skills/id/fireworks-tech-graph/update',{'id':current['id'],'name':current['name'],
    'content':(skill/'SKILL.md').read_text(),'expected_version_id':current['version_id'],
    'operations':[{'op':'put','path':'references/'+reference.name,'content':reference.read_text()}],
    'commit_message':'圖庫由伺服器按需搜尋；統一設備符號與品牌識別，不把整庫加入上下文'})
versions['fireworks-tech-graph']=saved['version_id']
tool=api('/api/v1/tools/id/openwebui_fireworks_renderer')
assert {s['name'] for s in tool['specs']}=={'render_technical_architecture','render_data_chart','search_diagram_assets'}
architecture=next(s for s in tool['specs'] if s['name']=='render_technical_architecture')
assert 'layout' in architecture['parameters']['properties']
for url in ['/static/architecture-icons/v2/preview.html','/static/architecture-icons/v2/svg/lobe/ollama.svg','/static/architecture-icons/v2/NOTICE.html']:
    response=session.get(base+url,timeout=30);response.raise_for_status()
    assert len(response.content)>100
print(json.dumps({'ok':True,'backup':str(backup),'versions':versions,'preview':base+'/static/architecture-icons/v2/preview.html','providers':4},ensure_ascii=False))
