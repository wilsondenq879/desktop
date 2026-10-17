"""Export only portable prompts/code. Never export users, chats, credentials or endpoints."""
import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'resources/openwebui-server-profile'
SAFE_CONFIG={'models.default_params','models.default_metadata','ui.default_locale','ui.prompt_suggestions','ui.prompt_suggestions_i18n',
    'task.follow_up.enable','task.query.search.enable','task.query.retrieval.enable','web.search.engine','web.search.enable',
    'web.search.result_count','web.search.ddgs_backend','skills.content_max_chars','skills.preview_max_chars'}
SAFE_PARAMS={'system','num_ctx','temperature','top_p','top_k','repeat_penalty','max_tokens','function_calling','think','reasoning_effort'}
SAFE_FUNCTIONS={'openwebui_visual_diagram_guard','openwebui_skill_semantic_router','openwebui_response_speed','taiwan_terminology_output_guard'}
SOURCE_FILES={'openwebui_visual_diagram_guard':'openwebui-visual-diagram-filter.py','openwebui_skill_semantic_router':'openwebui-skill-semantic-router.py',
    'openwebui_response_speed':'openwebui-response-speed-filter.py','openwebui_fireworks_renderer':'openwebui-fireworks-renderer-tool.py'}
SECRET=re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16})\b')


def export(runtime):
    db=sqlite3.connect((runtime/'data/webui.db').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    settings={}
    for row in db.execute('SELECT key,value FROM config'):
        key=row['key']
        if key in SAFE_CONFIG or key.endswith('.prompt_template') or key=='subagents.system_prompt':
            settings[key]=json.loads(row['value']) if isinstance(row['value'],str) else row['value']
    models=[]
    for row in db.execute('SELECT id,name,base_model_id,params FROM model'):
        params=json.loads(row['params'] or '{}')
        models.append({'id':row['id'],'name':row['name'],'base_model_id':row['base_model_id'],
            'params':{k:v for k,v in params.items() if k in SAFE_PARAMS}})
    functions=[]
    for row in db.execute('SELECT id,name,content,valves,is_active,is_global FROM function WHERE type=?',('filter',)):
        if row['id'] not in SAFE_FUNCTIONS:continue
        file=SOURCE_FILES.get(row['id'],row['id']+'.py')
        # Checked-in managed code wins over any stale running release.
        source=ROOT/'scripts'/file
        content=source.read_text() if source.exists() else row['content']
        functions.append({'id':row['id'],'name':row['name'],'content':content,'valves':json.loads(row['valves'] or '{}'),
            'is_active':bool(row['is_active']),'is_global':bool(row['is_global'])})
    tool=db.execute('SELECT id,name FROM tool WHERE id=?',('openwebui_fireworks_renderer',)).fetchone()
    profile={'format':1,'release':'0.0.34','tested_open_webui':'0.12.3',
        'privacy':'No user IDs, grants, conversations, credentials, connection URLs, SSH keys or pairing data. Config import is allowlisted and opt-in.',
        'functions':functions,'tools':[{'id':tool['id'],'name':tool['name'],'content':(ROOT/'scripts/openwebui-fireworks-renderer-tool.py').read_text()}],
        'settings':settings,'model_profiles':models}
    text=json.dumps(profile,ensure_ascii=False,indent=2)+'\n'
    if SECRET.search(text):raise RuntimeError('Possible credential detected; refused to export')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'profile.json').write_text(text)
    for row in functions:
        if row['id'] not in SOURCE_FILES:(ROOT/'scripts'/(row['id']+'.py')).write_text(row['content'])
    print(json.dumps({'ok':True,'functions':len(functions),'tools':1,'settings':len(settings),'model_profiles':len(models),'credentials_exported':False},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('runtime',type=Path);export(parser.parse_args().runtime.resolve())
