"""Install only bundled local assets; never copy secrets or mutate server settings."""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path


def install(bundle,data_dir,package=None):
    bundle=bundle.resolve();data_dir=data_dir.resolve()
    manifest=json.loads((bundle/'bundle-manifest.json').read_text())
    for relative,digest in manifest['files'].items():
        source=(bundle/relative).resolve()
        if not source.is_relative_to(bundle) or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('Bundle integrity failed: '+relative)
    if package is None:
        spec=importlib.util.find_spec('open_webui')
        if not spec or not spec.origin:raise RuntimeError('Open WebUI must be installed first')
        package=Path(spec.origin).parent
    state=data_dir/'visual-profile';state.mkdir(parents=True,exist_ok=True)
    signature=state/'assets.sha256'
    if signature.exists() and signature.read_text()==manifest['sha256'] and (package/'static/statistical-charts/v1/preview.html').exists():return {'changed':False}
    backup=state/('before-'+manifest['sha256'][:12]);backup.mkdir(exist_ok=True)
    for name in ['index.html','_app/version.json']:
        path=package/'frontend'/name
        if path.exists():
            dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    for source in (bundle/'runtime/skills').iterdir():
        if source.is_dir():shutil.copytree(source,data_dir/'skills'/source.name,dirs_exist_ok=True)
    shutil.copy2(bundle/'runtime/openwebui-fireworks-renderer-tool.py',state/'openwebui-fireworks-renderer-tool.py')
    for target in [package/'static',package/'frontend/static']:
        shutil.copytree(bundle/'static',target,dirs_exist_ok=True)
    index=package/'frontend/index.html'
    if index.exists():
        content=index.read_text()
        content=re.sub(r'<(?:script|link)\b[^>]*(?:src|href)="/static/(?:openwebui-(?:react-18\.min|react-dom-18\.min|react-svg-diagram-renderer|mobile-followups)\.(?:js|css)|custom\.css)(?:\?[^\"]*)?"[^>]*>(?:</script>)?','',content)
        version=manifest['sha256'][:12]
        tags=''.join(f'<script defer src="/static/{name}?v={version}"></script>\n' for name in ['openwebui-react-18.min.js','openwebui-react-dom-18.min.js','openwebui-react-svg-diagram-renderer.js','openwebui-mobile-followups.js'])
        tags+=''.join(f'<link rel="stylesheet" href="/static/{name}?v={version}">\n' for name in ['custom.css','openwebui-mobile-followups.css'] if (bundle/'static'/name).exists())
        if '</head>' not in content:raise ValueError('Unsupported Open WebUI frontend')
        index.write_text(content.replace('</head>',tags+'</head>',1))
    version_file=package/'frontend/_app/version.json'
    if version_file.exists():
        value=json.loads(version_file.read_text())
        value['version']=re.sub(r'-visual-profile-[a-f0-9]+$','',value['version'])+'-visual-profile-'+manifest['sha256'][:12]
        version_file.write_text(json.dumps(value))
    signature.write_text(manifest['sha256'])
    return {'changed':True,'release':manifest['release'],'assets_sha256':manifest['sha256']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--data-dir',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(install(args.bundle,args.data_dir)))
