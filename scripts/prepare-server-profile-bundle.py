"""Reproducible offline packaging from checked-in assets and pinned npm dependencies."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'resources/openwebui-server-profile'


def prepare():
    assert (DEST/'profile.json').is_file(),'Export the sanitized profile first'
    runtime=DEST/'runtime'
    shutil.copytree(ROOT/'resources/openwebui-managed-skills',runtime/'skills',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    icons=runtime/'skills/fireworks-tech-graph/assets/icons/technical'
    shutil.copytree(ROOT/'resources/architecture-icon-pack',icons,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (icons/'bundle-sha256.txt').write_text(hashlib.sha256(b''.join((icons/p).read_bytes() for p in ['manifest.json','hardware.json','extended/catalog.json'])).hexdigest())
    references=runtime/'skills/numeric-comparison-charts/references'
    references.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'resources/statistical-chart-templates/catalog.json',references/'chart-template-catalog.json')
    shutil.copy2(ROOT/'scripts/openwebui-fireworks-renderer-tool.py',runtime/'openwebui-fireworks-renderer-tool.py')
    shutil.copy2(ROOT/'scripts/install-server-profile-assets.py',DEST/'install-assets.py')
    shutil.copy2(ROOT/'scripts/restore-server-profile.py',DEST/'restore-profile.py')
    static=DEST/'static';static.mkdir(exist_ok=True)
    for name in ['openwebui-mobile-followups.css','openwebui-mobile-followups.js','openwebui-react-svg-diagram-renderer.js']:
        shutil.copy2(ROOT/'resources'/name,static/name)
    # Audited server custom CSS is a source asset, not an upstream frontend build.
    custom=ROOT/'resources/openwebui-server-custom.css'
    if custom.exists():shutil.copy2(custom,static/'custom.css')
    for package,name in [('react','openwebui-react-18.min.js'),('react-dom','openwebui-react-dom-18.min.js')]:
        source=ROOT/'node_modules'/package/'umd'/('react.production.min.js' if package=='react' else 'react-dom.production.min.js')
        shutil.copy2(source,static/name)
        shutil.copy2(ROOT/'node_modules'/package/'LICENSE',static/(package+'-LICENSE.txt'))
    for source,destination in [(ROOT/'deliverables/architecture-icon-pack-v2',static/'architecture-icons/v2'),
        (ROOT/'deliverables/statistical-chart-templates-v1',static/'statistical-charts/v1')]:
        if not source.exists():raise RuntimeError('Build visual previews first: '+str(source))
        shutil.copytree(source,destination,dirs_exist_ok=True,ignore=shutil.ignore_patterns('generated'))
    hashes={str(p.relative_to(DEST)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='bundle-manifest.json'}
    fingerprint=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    (DEST/'bundle-manifest.json').write_text(json.dumps({'format':1,'release':'0.0.34','sha256':fingerprint,'files':hashes},indent=2)+'\n')
    print(json.dumps({'ok':True,'files':len(hashes),'sha256':fingerprint,'bytes':sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())}))


if __name__=='__main__':prepare()
