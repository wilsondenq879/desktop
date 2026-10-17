"""Validate offline libraries, SVG safety, brand choice and real layout renders."""
import asyncio
import importlib.util
import json
import os
import re
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables/architecture-icon-pack-v2'

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

builder=load('icon_builder','build-extended-icon-library.py')
renderer=load('icon_renderer','openwebui-fireworks-renderer-tool.py').Tools()
fixtures=[
    {'slug':'layered','title':'Local AI 分層架構','layout':'layered','nodes':[
        {'id':'u','label':'遠端使用者','level':0,'icon':'users'},
        {'id':'v','label':'Tailscale VPN','level':1,'icon':'vpn'},
        {'id':'s','label':'10G 桌上型交換器','level':2,'icon':'hardware:desktop-switch'},
        {'id':'a','label':'ASUS GX10','detail':'網路介面待核實','level':3,'icon':'hardware:mini-ai-pc'},
        {'id':'b','label':'AI 工作站','level':3,'icon':'hardware:ai-workstation'}],
     'edges':[{'from':'u','to':'v','tone':'remote','dashed':True},{'from':'v','to':'s'},{'from':'s','to':'a'},{'from':'s','to':'b'}]},
    {'slug':'star','title':'工作室星狀拓撲','layout':'star','nodes':[
        {'id':'s','label':'桌上型交換器','level':1,'icon':'hardware:desktop-switch'},
        {'id':'a','label':'ASUS GX10','level':0,'icon':'hardware:mini-ai-pc'},
        {'id':'b','label':'AI 工作站','level':0,'icon':'hardware:ai-workstation'},
        {'id':'n','label':'NAS 儲存','level':2,'icon':'hardware:nas-appliance'},
        {'id':'u','label':'使用者電腦','level':2,'icon':'lucide:monitor'}],
     'edges':[{'from':'s','to':n} for n in ['a','b','n','u']]},
    {'slug':'dual-compute','title':'雙機 AI 互連（概念）','layout':'dual_compute','nodes':[
        {'id':'a','label':'AI 工作站 A','level':0,'icon':'hardware:ai-workstation','group':'A'},
        {'id':'b','label':'AI 工作站 B','level':0,'icon':'hardware:ai-workstation','group':'B'},
        {'id':'na','label':'Intel E800 A','level':1,'icon':'hardware:pcie-nic','group':'A'},
        {'id':'nb','label':'Intel E800 B','level':1,'icon':'hardware:pcie-nic','group':'B'}],
     'groups':[{'id':'A','label':'主機 A'},{'id':'B','label':'主機 B'}],
     'edges':[{'from':'a','to':'na','label':'PCIe'},{'from':'b','to':'nb','label':'PCIe'},{'from':'na','to':'nb','label':'RDMA：條件待核實','tone':'active','direction':'both'}]},
    {'slug':'rack','title':'Mini rack 配置示意','layout':'rack','subtitle':'概念配置，實際尺寸、承重、散熱與固定方式皆須另行確認。',
     'nodes':[{'id':'s','label':'桌上型交換器','level':0,'icon':'hardware:desktop-switch','group':'rack'},
        {'id':'a','label':'ASUS GX10','level':1,'icon':'hardware:mini-ai-pc','group':'rack'},
        {'id':'n','label':'NAS 儲存','level':2,'icon':'hardware:nas-appliance','group':'rack'},
        {'id':'u','label':'遠端使用者','level':0,'icon':'users'}],
     'edges':[{'from':'u','to':'s','label':'已核准存取','tone':'remote','dashed':True},{'from':'s','to':'a'},{'from':'s','to':'n'}]},
    {'slug':'dataflow','title':'本地 AI 資料流','layout':'dataflow','nodes':[
        {'id':'u','label':'使用者問題','level':0,'icon':'lucide:message-square'},
        {'id':'o','label':'Open WebUI','level':1,'icon':'lobe:openwebui'},
        {'id':'m','label':'Ollama','level':2,'icon':'lobe:ollama'},
        {'id':'q','label':'Qwen3 模型','level':3,'icon':'lobe:qwen-color'}],
     'edges':[{'from':'u','to':'o','direction':'forward'},{'from':'o','to':'m','direction':'forward'},{'from':'m','to':'q','direction':'forward'}]},
    {'slug':'ecosystem','title':'Local AI 軟體生態圈','layout':'ecosystem','nodes':[
        {'id':'o','label':'Open WebUI','level':0,'icon':'lobe:openwebui'},
        {'id':'m','label':'Ollama','level':1,'icon':'lobe:ollama'},
        {'id':'d','label':'Docker','level':1,'icon':'dashboard:docker'},
        {'id':'v','label':'Tailscale','level':2,'icon':'simple:tailscale'},
        {'id':'q','label':'Qwen3 模型','level':2,'icon':'lobe:qwen-color'}],
     'edges':[{'from':'o','to':'m','label':'模型 API'},{'from':'o','to':'d','label':'部署環境'},{'from':'o','to':'v','label':'遠端存取','tone':'remote','dashed':True},{'from':'m','to':'q','label':'模型載入'}]}
]

async def main():
    for bad in ['<svg><script>alert(1)</script></svg>','<svg><image href="https://example.invalid/x"/></svg>',
        '<!DOCTYPE svg><svg/>','<svg><path onclick="x()" d="M0 0"/></svg>',
        '<svg><use href="file:///private/etc/passwd"/></svg>','<svg><path fill="url(https://example.invalid/p)"/></svg>']:
        try: builder.sanitize_svg(bad,'test')
        except (ValueError,ET.ParseError): pass
        else: raise AssertionError(bad)
    catalog=renderer._icon_catalog()
    assert len(catalog)>9000
    for id in ['lucide:router','lobe:ollama','dashboard:docker','simple:asus','hardware:pcie-nic']:
        assert id in catalog
        ET.fromstring(ET.tostring(renderer._glyph(catalog[id],prefix='one')))
    assert renderer._pick_icon({'label':'ASUS GX10'},catalog)=='hardware:mini-ai-pc'
    assert renderer._pick_icon({'label':'Ollama'},catalog)=='lobe:ollama'
    assert renderer._pick_icon({'label':'Qwen3 模型'},catalog)=='lobe:qwen-color'
    assert renderer._pick_icon({'label':'GPU','icon':'../../private'},catalog)=='gpu'
    assert renderer._brand_icon({'label':'ASUS GX10'},catalog)=='simple:asus'
    assert renderer._brand_palette(catalog['dashboard:ollama-dark'])[0]=='#172235'
    search=json.loads(await renderer.search_diagram_assets('ollama',8))
    assert len(search['matches'])<=8 and any(i['id']=='lobe:ollama' for i in search['matches'])
    assert not any('body' in i for i in search['matches'])
    before=time.monotonic()
    for _ in range(10): renderer._icon_catalog()
    assert time.monotonic()-before<1, 'Cached catalog reads must not reload 25MB for every node'
    print('PASS: four providers, SVG injection rejection, local cache, semantic icons, brand badges, compact search',flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'examples.json').write_text(json.dumps(fixtures,ensure_ascii=False,indent=2))
    if not os.environ.get('OPENWEBUI_TEST_RENDER'): return
    os.environ['OPENWEBUI_FIREWORKS_SKILL_ROOT']=str(ROOT/'resources/openwebui-managed-skills/fireworks-tech-graph')
    os.environ['OPENWEBUI_FIREWORKS_OUTPUT_DIR']=str(OUT/'generated')
    for fixture in fixtures:
        data={k:v for k,v in fixture.items() if k!='slug'}
        result=await renderer.render_technical_architecture(**data)
        match=re.search(r'/([0-9]+-[a-f0-9]+)\.png',result)
        assert match,fixture['slug']+': '+result
        base=OUT/'generated'/match[1]
        for ext in ('svg','png','html'):
            shutil.copy2(base.with_suffix('.'+ext),OUT/(fixture['slug']+'.'+ext))
        root=ET.parse(OUT/(fixture['slug']+'.svg')).getroot()
        assert len(root.findall('.//*[@data-graph-role="node"]'))==len(data['nodes'])
        assert len(root.findall('.//*[@data-graph-role="edge"]'))==len(data['edges'])
        assert root.find('.//*[@id="icon-provenance"]') is not None
        assert '改採分層構圖' not in result, 'All six reference topologies should pass without fallback'
        assert all(n['label'] in ''.join(root.itertext()) for n in data['nodes'])
        print('PASS render:',fixture['slug'],flush=True)

asyncio.run(main())
