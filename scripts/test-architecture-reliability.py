"""Real PNG/SVG stress suite. No LLM calls or production writes."""
import argparse, asyncio, importlib.util, json, os, random, re, struct, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables/architecture-reliability-v1'
OUT.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('WEBUI_SECRET_KEY','synthetic-architecture-verification-only')
os.environ['OPENWEBUI_FIREWORKS_SKILL_ROOT']=str(ROOT/'resources/openwebui-managed-skills/fireworks-tech-graph')
os.environ['OPENWEBUI_FIREWORKS_OUTPUT_DIR']=str(OUT)
spec=importlib.util.spec_from_file_location('reliability_renderer',ROOT/'scripts/openwebui-fireworks-renderer-tool.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);tool=module.Tools()
parser=argparse.ArgumentParser();parser.add_argument('--count',type=int,default=40);args=parser.parse_args()


def fixtures(count):
    rng=random.Random(20261018)
    # The actual failure: a management connection skips an intervening row.
    yield {'title':'25G GPU Cluster 實際失敗回歸','nodes':[
        {'id':'s','label':'25G SFP28 Switch','level':0},
        {'id':'a','label':'GPU Node A','detail':'RDMA Enabled NIC','level':1},
        {'id':'b','label':'GPU Node B','detail':'RDMA Enabled NIC','level':1},
        {'id':'n','label':'High-Speed Storage','detail':'NVMe over Fabrics','level':1},
        {'id':'m','label':'Management Station','level':2}],
        'edges':[{'from':'s','to':n,'label':'25G RoCE v2','tone':'active'} for n in ['a','b','n']]+[
            {'from':'m','to':'s','label':'Management / Configuration','tone':'remote','dashed':True}]}
    for case in range(count-1):
        n=2+case%13
        nodes=[{'id':f'n{j}' if case%7 else f'設備{j}',
            'label':('25G 桌上型交換器' if j==0 else f'GPU 工作站 {j}'),
            'detail':'端到端 PFC / ECN / Jumbo Frame，條件待核實' if case%3 else 'WWWWWWWWWWMMMMMMMMMMMM Local Compute',
            'level':j%3 if case%2 else int(j>0),'group':f'群組{j%3}' if case%4==0 else '',
            'icon':'hardware:desktop-switch' if j==0 else 'hardware:ai-workstation'} for j in range(n)]
        pairs={(0,j) for j in range(1,n)} if case%3==0 else {(j-1,j) for j in range(1,n)}
        extra=list({(rng.randrange(n),rng.randrange(n)) for _ in range(n*2)}-pairs)
        if case%3==2:pairs.update((a,b) for a,b in extra[:max(0,min(22-len(pairs),n))] if a!=b)
        edges=[{'from':nodes[a]['id'],'to':nodes[b]['id'],'label':'25GbE / RoCE v2 · 管理控制流',
            'direction':['none','forward','both'][i%3],'dashed':bool(i%2),'tone':'active' if i%2 else 'remote'} for i,(a,b) in enumerate(sorted(pairs))]
        if case%6==0:nodes[0]['port_groups']=[{'label':'25G SFP28','count':24,'tone':'active'},{'label':'10G Ethernet','count':24,'tone':'network'}]
        yield {'title':f'可靠性案例 {case+1} [架構]','subtitle':'示意拓撲，非產品規格或效能實測',
            'layout':['auto','star','layered','dual_compute','dataflow','ecosystem'][case%6],'nodes':nodes,'edges':edges}


async def verify(data,force_focus=False):
    request=SimpleNamespace(state=SimpleNamespace(fireworks_diagram={}))
    statuses=[]
    async def emitter(event):statuses.append(event)
    real_run=subprocess.run
    def fail_global(command,*args,**kwargs):
        if 'render' in command and 'architecture' in command:
            source=json.loads(Path(command[-2]).read_text())
            if source.get('layout')!='connection_views':return subprocess.CompletedProcess(command,1,'','COMPOSITION_QUALITY: forced synthetic failure')
        return real_run(command,*args,**kwargs)
    with patch.object(module.subprocess,'run',side_effect=fail_global) if force_focus else patch.object(module.subprocess,'run',wraps=real_run):
        result=await tool.render_technical_architecture(**data,__request__=request,__event_emitter__=emitter)
    assert result.startswith('!['),result
    assert not any(e.get('data',{}).get('description')=='架構圖產生失敗' for e in statuses)
    token=re.search(r'/([0-9]+-[a-f0-9]+)\.png',result)[1]
    root=ET.fromstring((OUT/(token+'.svg')).read_text())
    checked=real_run([sys.executable,str(Path(os.environ['OPENWEBUI_FIREWORKS_SKILL_ROOT'])/'scripts/fireworks.py'),
        'check',str(OUT/(token+'.svg'))],capture_output=True,text=True,timeout=15)
    assert checked.returncode==0,checked.stdout+checked.stderr
    semantic=json.loads(root.find('{http://www.w3.org/2000/svg}desc[@id="architecture-semantic-graph"]').text)
    ids={tool._id(n['id'],i) for i,n in enumerate(data['nodes'])}
    expected=[(tool._id(e['from'],i),tool._id(e['to'],i+1),e.get('direction','none'),bool(e.get('dashed'))) for i,e in enumerate(data['edges'])]
    assert {n['id'] for n in semantic['nodes']}==ids
    assert [(e['source'],e['target'],e['direction'],e['dashed']) for e in semantic['edges']]==expected
    drawn=root.findall('.//*[@data-graph-role="node"]')
    assert {n.get('data-origin-node-id') for n in drawn}==ids
    assert len(root.findall('.//*[@data-graph-role="edge"]'))==len(data['edges'])
    assert root.get('data-text-complete')=='true'
    for rect in root.findall('.//{http://www.w3.org/2000/svg}rect'):
        assert float(rect.get('width',1))>0 and float(rect.get('height',1))>0
    png=(OUT/(token+'.png')).read_bytes();width,height=struct.unpack('>II',png[16:24])
    assert png.startswith(b'\x89PNG') and width==1920 and 0<height<32768
    assert (OUT/(token+'.html')).is_file()
    report=json.loads((OUT/(token+'.report.json')).read_text())
    if force_focus:assert report['layout']=='connection_views'
    return {'title':data['title'],'layout':report['layout'],'nodes':len(ids),'edges':len(expected),'png':token+'.png','attempts':len(report['attempts'])}


async def main():
    results=[]
    for data in fixtures(args.count):
        result=await verify(data);results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    data=list(fixtures(2))[-1]
    result=await verify(data,True);results.append(result);print(json.dumps(result|{'forced_fallback':True},ensure_ascii=False),flush=True)
    for bad in [dict(title='重複',nodes=[{'id':'x'},{'id':'x'}],edges=[{'from':'x','to':'x'}]),
        dict(title='缺端點',nodes=[{'id':'a'},{'id':'b'}],edges=[{'from':'a','to':'missing'}])]:
        assert not (await tool.render_technical_architecture(**bad)).startswith('![')
    (OUT/'results.json').write_text(json.dumps({'passed':len(results),'cases':results},ensure_ascii=False,indent=2))
    print('PASS: real PNG/SVG/HTML, all canonical nodes/edges/directions, CJK IDs, 48 ports, strict text sizing, isolated/focused fallback, no false success')


asyncio.run(main())
