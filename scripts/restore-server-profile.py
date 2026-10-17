"""Explicit portable profile restore; dry-run by default and credentials only in env."""
import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Profile API redirects are refused; credentials stay on the selected server')


def restore(bundle,base,backup_dir,apply=False,settings=False,allow_remote=False):
    profile=json.loads((bundle/'profile.json').read_text())
    digest=hashlib.sha256((bundle/'profile.json').read_bytes()+str(settings).encode()).hexdigest()
    if not apply:return {'dry_run':True,'release':profile['release'],'functions':[v['id'] for v in profile['functions']],
        'tools':[v['id'] for v in profile['tools']],'settings':list(profile['settings']) if settings else []}
    parsed=urllib.parse.urlsplit(base)
    if parsed.scheme not in {'http','https'} or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Invalid server URL')
    if parsed.hostname not in {'127.0.0.1','localhost','::1'} and not allow_remote:raise ValueError('Remote restore requires explicit --allow-remote')
    token=os.environ.get('OPENWEBUI_PROFILE_TOKEN','')
    if not token:raise ValueError('Set OPENWEBUI_PROFILE_TOKEN to an administrator session/API token')
    base=base.rstrip('/')
    opener=urllib.request.build_opener(NoRedirect())
    def api(path,payload=None,missing=False):
        body=json.dumps(payload).encode() if payload is not None else None
        request=urllib.request.Request(base+path,data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            with opener.open(request,timeout=90) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            if missing and error.code==404:return None
            raise RuntimeError(f'Profile API failed: {path}, HTTP {error.code}') from None
    user=api('/api/v1/auths/')
    if user.get('role')!='admin':return {'skipped':True,'reason':'administrator required'}
    backup_dir.mkdir(parents=True,exist_ok=True)
    marker=backup_dir/(hashlib.sha256(base.encode()).hexdigest()[:16]+'.json')
    if marker.exists() and json.loads(marker.read_text()).get('sha256')==digest:return {'changed':False,'release':profile['release']}
    snapshot={'functions':[],'tools':[],'settings':{},'models':[]}
    stamp=str(time.time_ns());snap=backup_dir/('before-'+stamp+'.json')
    changed=[]
    for kind in ['functions','tools']:
        for item in profile[kind]:
            id=item['id'];path='/api/v1/'+kind+'/id/'+id
            current=api(path,missing=True)
            if current:snapshot[kind].append(current)
            # Persist rollback before every external write; never store token.
            snap.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
            payload={'id':id,'name':item['name'],'content':item['content'],'meta':(current or {}).get('meta') or {},'commit_message':'Restore managed visual profile '+profile['release']}
            result=api(path+'/update' if current else '/api/v1/'+kind+'/create',payload)
            if kind=='functions':
                if item.get('valves'):api(path+'/valves/update',item['valves'])
                if result.get('is_active')!=item['is_active']:result=api(path+'/toggle',{})
                if result.get('is_global')!=item['is_global']:api(path+'/toggle/global',{})
            changed.append(id)
    if settings:
        current=api('/api/v1/configs/export')
        snapshot['settings']={k:current.get(k) for k in profile['settings']}
        snap.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
        # API upserts only these allowlisted keys; auth/provider settings remain untouched.
        api('/api/v1/configs/import',{'config':profile['settings']})
        for model in profile['model_profiles']:
            current=api('/api/v1/models/model?id='+urllib.parse.quote(model['id'],safe=''),missing=True)
            if not current:continue  # Never create non-existent hardware/provider aliases.
            snapshot['models'].append(current);snap.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
            api('/api/v1/models/model/update',{'id':current['id'],'name':current['name'],'base_model_id':current.get('base_model_id'),
                'params':(current.get('params') or {})|model['params'],'meta':current.get('meta') or {},'is_active':current.get('is_active',True),
                'commit_message':'Restore prompt/decoding defaults '+profile['release']})
    marker.write_text(json.dumps({'sha256':digest,'release':profile['release'],'backup':str(snap)}))
    return {'changed':True,'release':profile['release'],'updated':changed,'settings_applied':settings,'backup':str(snap)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--base',default='http://127.0.0.1:3000')
    parser.add_argument('--backup-dir',type=Path,default=Path.cwd()/'profile-backups');parser.add_argument('--apply',action='store_true')
    parser.add_argument('--settings',action='store_true');parser.add_argument('--allow-remote',action='store_true');args=parser.parse_args()
    print(json.dumps(restore(args.bundle,args.base,args.backup_dir,args.apply,args.settings,args.allow_remote)))
