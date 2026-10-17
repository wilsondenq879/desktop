"""Exercise offline integrity/assets and API restore against an isolated fake server."""
import contextlib
import importlib.util
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'resources/openwebui-server-profile'


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


install=load('profile_install','install-server-profile-assets.py').install
restore=load('profile_restore','restore-server-profile.py').restore
profile=json.loads((BUNDLE/'profile.json').read_text())
assert len(profile['functions'])==4 and len(profile['tools'])==1
assert not any(any(word in k for word in ['api_key','password','secret','connections','auth.']) for k in profile['settings'])
assert all(set(m['params'])<= {'system','num_ctx','temperature','top_p','top_k','repeat_penalty','max_tokens','function_calling','think','reasoning_effort'} for m in profile['model_profiles'])
calls=[]


class Fake(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path.startswith('/redirect/'):
            self.send_response(302);self.send_header('Location','/must-not-follow');self.end_headers();return
        if self.path=='/api/v1/auths/':value={'id':'test-admin','role':'admin'}
        elif self.path=='/api/v1/configs/export':value=profile['settings']|{'openai.api_keys':['private-test-value-not-exported']}
        elif '/models/model?' in self.path:self.send_error(404);return
        else:value={'id':self.path.split('/')[-1],'name':'current','content':'previous source','meta':{'tags':['preserve']},'is_active':True,'is_global':True}
        raw=json.dumps(value).encode();self.send_response(200);self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        value=json.loads(self.rfile.read(int(self.headers['Content-Length'])));calls.append((self.path,value))
        raw=json.dumps(value|{'version_id':'synthetic','is_active':True,'is_global':True}).encode();self.send_response(200);self.end_headers();self.wfile.write(raw)


with tempfile.TemporaryDirectory(prefix='openwebui-profile-test-') as folder:
    root=Path(folder);package=root/'package';data=root/'data'
    (package/'frontend/_app').mkdir(parents=True)
    (package/'frontend/index.html').write_text('<html><head><title>Upstream</title></head><body>untouched</body></html>')
    (package/'frontend/_app/version.json').write_text('{"version":"upstream"}')
    assert install(BUNDLE,data,package)['changed']
    assert not install(BUNDLE,data,package)['changed']
    content=(package/'frontend/index.html').read_text()
    assert content.count('src="/static/openwebui-react-svg-diagram-renderer.js?')==1 and 'untouched' in content
    assert (data/'skills/fireworks-tech-graph/assets/icons/technical/extended/catalog.json').is_file()
    assert (package/'static/statistical-charts/v1/preview.html').is_file()
    assert (data/'visual-profile/openwebui-fireworks-renderer-tool.py').is_file()
    assert restore(BUNDLE,'http://127.0.0.1:1',root/'backups')['dry_run']
    server=HTTPServer(('127.0.0.1',0),Fake);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    previous=os.environ.get('OPENWEBUI_PROFILE_TOKEN');os.environ['OPENWEBUI_PROFILE_TOKEN']='synthetic-token-only'
    try:
        base='http://127.0.0.1:'+str(server.server_port)
        result=restore(BUNDLE,base,root/'backups',True,True)
        assert result['changed'] and len(result['updated'])==5
        assert not restore(BUNDLE,base,root/'backups',True,True)['changed']
        assert any(path.endswith('/configs/import') for path,payload in calls)
        assert all('access_grants' not in payload for path,payload in calls)
        assert all('synthetic-token-only' not in p.read_text() and 'private-test-value-not-exported' not in p.read_text() for p in (root/'backups').glob('*.json'))
        try:restore(BUNDLE,base+'/redirect',root/'redirect-backups',True)
        except RuntimeError as error:assert 'redirect' in str(error)
        else:raise AssertionError('Credentials must not follow redirects')
    finally:
        server.shutdown();server.server_close()
        if previous is None:os.environ.pop('OPENWEBUI_PROFILE_TOKEN',None)
        else:os.environ['OPENWEBUI_PROFILE_TOKEN']=previous
print('PASS: profile privacy allowlist, 9k-asset integrity, portable install, frontend preservation, idempotent API restore, access preservation, no credentials in backup')
