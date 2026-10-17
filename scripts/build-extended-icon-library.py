"""Fetch pinned SVG-only libraries; no npm install, lifecycle hooks or model SVG execution."""
import argparse
import base64
import concurrent.futures
import hashlib
import html
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'resources/architecture-icon-pack/extended'
PACKAGES = {'lucide':('lucide-static','1.59.0','ISC', 'https://github.com/lucide-icons/lucide'),
    'lobe':('@lobehub/icons-static-svg','1.95.1','MIT','https://github.com/lobehub/lobe-icons'),
    'simple':('simple-icons','16.35.0','CC0-1.0','https://github.com/simple-icons/simple-icons')}
TAGS = {'svg','g','path','rect','circle','ellipse','line','polyline','polygon','defs','linearGradient','radialGradient','stop','clipPath','mask','use','title','desc'}
ATTRS = {'id','viewBox','fill','fill-rule','clip-rule','stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-miterlimit','stroke-dasharray','stroke-dashoffset','opacity','fill-opacity','stroke-opacity','d','x','y','x1','x2','y1','y2','cx','cy','r','rx','ry','width','height','points','transform','gradientTransform','gradientUnits','spreadMethod','offset','stop-color','stop-opacity','clip-path','clipPathUnits','mask','maskUnits','maskContentUnits','fx','fy','fr','href','color','preserveAspectRatio'}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'OpenWebUI-local-icons/2.0'}), timeout=90) as response:
        value = response.read(100_000_001)
    if len(value)>100_000_000:
        raise ValueError('Source exceeds download size limit')
    return value


def sanitize_svg(raw, prefix):
    if len(raw)>300_000 or re.search(r'<!DOCTYPE|<!ENTITY', raw, re.I):
        raise ValueError('Unsafe or oversized SVG')
    root = ET.fromstring(raw)
    local = lambda name:name.rsplit('}',1)[-1]
    if local(root.tag)!='svg':
        raise ValueError('Not SVG')
    ids = {node.attrib['id']:prefix+'-'+re.sub(r'[^a-zA-Z0-9_-]','_',node.attrib['id']) for node in root.iter() if node.get('id')}
    for node in root.iter():
        node.tag = local(node.tag)
        if node.tag not in TAGS:
            raise ValueError('Unsupported SVG element: '+node.tag)
        attributes = {}
        for key,value in node.attrib.items():
            key = local(key)
            if key=='style':
                for rule in value.split(';'):
                    if ':' in rule:
                        prop, val = map(str.strip,rule.split(':',1))
                        if prop in ATTRS:
                            attributes[prop]=val
            elif key in ATTRS:
                attributes[key]=value
            elif key.lower().startswith('on'):
                raise ValueError('SVG event handler')
        for key,value in attributes.items():
            if key=='href':
                if not value.startswith('#') or value[1:] not in ids:
                    raise ValueError('External or unresolved href')
                value='#'+ids[value[1:]]
            if key=='id':
                if value not in ids:
                    raise ValueError('Nonstandard namespaced or styled id')
                value=ids[value]
            for match in re.findall(r'url\(([^)]+)\)',value,re.I):
                ref=match.strip(' \"\'')
                if not ref.startswith('#') or ref[1:] not in ids:
                    raise ValueError('External paint reference')
                value=value.replace('url('+match+')','url(#'+ids[ref[1:]]+')')
            if re.search(r'javascript:|data:|https?:|expression\(|@import',value,re.I):
                raise ValueError('External content')
            attributes[key]=value
        node.attrib.clear()
        node.attrib.update(attributes)
    viewbox=root.get('viewBox','0 0 '+root.get('width','24')+' '+root.get('height','24'))
    values=[float(v) for v in re.split(r'[ ,]+',viewbox.strip())]
    if len(values)!=4 or not all(abs(v)<100_000 for v in values) or min(values[2:])<=0:
        raise ValueError('Invalid viewBox')
    body=''.join(ET.tostring(child,encoding='unicode') for child in root)
    defaults={key:root.get(key) for key in ('fill','stroke','stroke-width','stroke-linecap','stroke-linejoin') if root.get(key)}
    if not defaults.get('fill'):
        defaults['fill']='currentColor'
    return {'viewBox':' '.join(f'{v:g}' for v in values),'body':body,'defaults':defaults}


def package(provider, package_name, version, license_name, repo):
    meta=json.loads(fetch('https://registry.npmjs.org/'+package_name+'/'+version))
    data=fetch(meta['dist']['tarball'])
    integrity='sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode()
    assert integrity==meta['dist']['integrity'], 'npm integrity mismatch'
    files={}
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        for member in archive.getmembers():
            if not member.isfile() or member.size>400_000:
                continue
            name=member.name
            svg=(provider=='lucide' and name.startswith('package/icons/') and name.endswith('.svg')) or (provider=='lobe' and name.startswith('package/icons/') and name.endswith('.svg')) or (provider=='simple' and name.startswith('package/icons/') and name.endswith('.svg'))
            notice=Path(name).name.upper().startswith(('LICENSE','COPYING','DISCLAIMER','NOTICE'))
            if svg or notice:
                files[name.removeprefix('package/')]=archive.extractfile(member).read().decode('utf-8')
    return provider,files,{'package':package_name,'version':version,'license':license_name,'source':repo,'integrity':integrity,'url':meta['dist']['tarball']}


def dashboard():
    with tempfile.TemporaryDirectory(prefix='webui-dashboard-icons-') as temp:
        checkout=Path(temp)/'repo'
        subprocess.run(['git','clone','--depth=1','--filter=blob:none','--sparse','https://github.com/homarr-labs/dashboard-icons.git',str(checkout)],check=True,capture_output=True,timeout=180)
        subprocess.run(['git','-C',str(checkout),'sparse-checkout','set','svg'],check=True,capture_output=True,timeout=180)
        commit=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
        # Some upstream .svg filenames contain binary/raster content. Keep
        # decoding failures visible to the sanitizer instead of importing it.
        files={str(path.relative_to(checkout)):path.read_text(errors='replace') for path in (checkout/'svg').glob('*.svg') if path.is_file() and path.stat().st_size<400_000}
        for path in checkout.iterdir():
            if path.is_file() and path.name.upper().startswith(('LICENSE','NOTICE','DISCLAIMER')):
                files[path.name]=path.read_text()
    return 'dashboard',files,{'version':commit,'license':'Apache-2.0','source':'https://github.com/homarr-labs/dashboard-icons','commit':commit}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    notice=OUT/'licenses/lobe/LICENSE'
    if not notice.exists():
        # The static npm bundle omits its repository's MIT notice.
        raw=fetch('https://raw.githubusercontent.com/lobehub/lobe-icons/49a2130df7bfa5eb1b088261bff20a37e2967789/LICENSE')
        assert b'Copyright' in raw and b'Permission is hereby granted' in raw
        notice.parent.mkdir(parents=True,exist_ok=True)
        notice.write_bytes(raw)
    if (OUT/'catalog.json').is_file() and not args.refresh:
        print('Using existing version-pinned local catalog:',OUT/'catalog.json')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    icons,providers,rejected=[],{},[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(package,provider,*spec) for provider,spec in PACKAGES.items()]+[pool.submit(dashboard)]
        for future in concurrent.futures.as_completed(jobs):
            provider,files,metadata=future.result()
            count=0
            notices=OUT/'licenses'/provider
            notices.mkdir(parents=True,exist_ok=True)
            for name,raw in sorted(files.items()):
                if not name.endswith('.svg'):
                    (notices/Path(name).name).write_text(raw)
                    continue
                slug=Path(name).stem.lower()
                if not re.fullmatch(r'[a-z0-9_-]+',slug):
                    rejected.append([provider,name,'invalid slug']);continue
                identifier=provider+':'+slug
                try:
                    safe=sanitize_svg(raw,provider+'-'+slug)
                except (ValueError,ET.ParseError) as error:
                    rejected.append([provider,name,str(error)]);continue
                entry={'id':identifier,'label':slug.replace('-',' '),'aliases':[slug.replace('-',' ')],
                    'provider':provider,'category':'generic' if provider=='lucide' else 'brand','license':metadata['license'],
                    'source':metadata['source'],'source_file':name,'sha256':hashlib.sha256(raw.encode()).hexdigest(),**safe}
                icons.append(entry);count+=1
            metadata['icons']=count
            providers[provider]=metadata
            print(json.dumps({'provider':provider,'icons':count,'version':metadata['version']},ensure_ascii=False),flush=True)
    assert all(providers[p]['icons']>100 for p in ('lucide','lobe','simple','dashboard'))
    catalog={'version':2,'providers':providers,'icons':sorted(icons,key=lambda i:i['id']),
        'notice':'Library licenses do not grant trademark rights; brand marks identify products, not endorsement.',
        'rejected':rejected}
    (OUT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':')))
    (OUT/'sources.lock.json').write_text(json.dumps({'providers':providers,'rejected':rejected},ensure_ascii=False,indent=2))
    print(json.dumps({'ok':True,'icons':len(icons),'rejected':len(rejected),'catalog':str(OUT/'catalog.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
