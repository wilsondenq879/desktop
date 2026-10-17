"""Synthetic geometry stress probe: no model calls, user data or production writes."""
import argparse, importlib.util, json, os, random, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('WEBUI_SECRET_KEY','synthetic-layout-probe-only')
os.environ['OPENWEBUI_FIREWORKS_SKILL_ROOT']=str(ROOT/'resources/openwebui-managed-skills/fireworks-tech-graph')
spec=importlib.util.spec_from_file_location('renderer',ROOT/'scripts/openwebui-fireworks-renderer-tool.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
tool=module.Tools()
parser=argparse.ArgumentParser();parser.add_argument('--count',type=int,default=30);parser.add_argument('--layout');args=parser.parse_args()
rng=random.Random(20261017);failures=[]
with tempfile.TemporaryDirectory(prefix='architecture-geometry-probe-') as directory:
    for i in range(args.count):
        count=3+i%10
        nodes=[{'id':f'n{j}','label':('25G 交換器' if j==0 else f'GPU 工作站 {j}'),
            'detail':('PFC / ECN / Jumbo Frame；參數須端到端確認' if i%3 else 'Local Compute / RDMA NIC'),
            'level':(j%3 if i%2 else int(j>0)), 'group':(f'group-{j%3}' if i%4==0 else ''),
            'icon':'hardware:desktop-switch' if j==0 else 'hardware:ai-workstation'} for j in range(count)]
        edges=[{'from':'n0','to':f'n{j}','label':'25GbE / RoCE v2','direction':'both'} for j in range(1,count)]
        if i%5==0:edges += [{'from':f'n{j}','to':f'n{j+1}','label':'控制流','dashed':True} for j in range(1,count-1)]
        layout=['star','layered','dual_compute','dataflow','ecosystem'][i%5]
        layout=args.layout or layout
        file=Path(directory)/'input.json';svg=Path(directory)/'output.svg'
        data=tool._layout('GPU Cluster 25G 技術架構','概念拓撲；不代表效能實測',nodes,edges,[],3,layout)
        file.write_text(json.dumps(data,ensure_ascii=False))
        r=subprocess.run([sys.executable,str(Path(os.environ['OPENWEBUI_FIREWORKS_SKILL_ROOT'])/'scripts/fireworks.py'),
            'render','architecture',str(file),str(svg)],capture_output=True,text=True,timeout=40)
        if r.returncode:
            failures.append({'case':i,'layout':layout,'error':(r.stderr or r.stdout)[-1200:]})
        print(json.dumps({'case':i,'ok':r.returncode==0},ensure_ascii=False),flush=True)
    print(json.dumps({'total':args.count,'failures':failures},ensure_ascii=False),flush=True)
