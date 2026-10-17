"""Regression coverage for reusable layouts, arithmetic, safety, and chart routing."""
import asyncio
import copy
import importlib.util
import json
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


tool=load('chart_tool','openwebui-fireworks-renderer-tool.py').Tools()
guard=load('chart_guard','openwebui-visual-diagram-filter.py').Filter()
examples=load('chart_fixtures','build-statistical-chart-templates.py').examples()
ns={'s':'http://www.w3.org/2000/svg'}


def normalize(payload):return tool._chart_data(**payload)


def reject(slug,**change):
    try:normalize(copy.deepcopy(examples[slug])|change)
    except ValueError:return
    raise AssertionError(('accepted invalid data',slug,change))


async def main():
    started=time.perf_counter()
    for slug,payload in examples.items():
        snapshot=copy.deepcopy(payload)
        data=normalize(payload)
        svg=tool._chart_svg(data);root=ET.fromstring(svg)
        assert payload==snapshot, 'input mutated: '+slug
        assert root.get('data-chart-type')==data['chart_type']
        assert root.find('s:title',ns) is not None
        assert data['note'] in ''.join(root.itertext())
        assert 'nan' not in svg.lower() and 'inf' not in svg.lower()
        assert not any(e.tag.rsplit('}',1)[-1] in {'script','foreignObject','image'} for e in root.iter())
        for el in root.iter():
            for key,value in el.attrib.items():
                assert not key.lower().startswith('on')
                if key in {'x','y','cx','cy','r','width','height'}:
                    assert math.isfinite(float(value))
        rows=tool._chart_rows(data)
        assert len(rows)==len(data['labels'])+1 and all(len(r)==len(rows[0]) for r in rows)
        print('PASS template:',slug)
    assert normalize(examples['gantt'])['options']['progress'][-1] is None
    gantt_rows=tool._chart_rows(normalize(examples['gantt']))
    assert gantt_rows[-1][-1]=='未提供' and gantt_rows[1][1]=='2026-10-01'
    assert tool._chart_rows(normalize(examples['waterfall']))[-1][-1]==130
    for row in tool._chart_rows(normalize(examples['percent_stacked_column']))[1:]:
        assert math.isclose(sum(row[-3:]),100)
    # Percentage shares derive from weights, not assumed-to-be-percent input.
    pie=examples['pie']|{'series':[{'name':'樣本','values':[2,2,4,0]}]}
    assert [r[-1] for r in tool._chart_rows(normalize(pie))[1:]]==[25,25,50,0]
    for slug in examples:
        reject(slug,options={'script':'alert(1)'})
    reject('gauge',labels=['A','B'],series=[{'name':'v','values':[50,60]}])
    reject('gauge',options={'min':100,'max':0})
    reject('gauge',options={'target':101})
    reject('gauge',options={'max':True})
    reject('radar',options={'max':50})
    reject('radar',series=[{'name':'A','values':[80,-1,60,85,75]}])
    reject('tornado',series=[{'name':'A','values':[1,2,3,4]}])
    reject('pie',series=[{'name':'A','values':[0,0,0,0]}])
    reject('doughnut',series=[{'name':'A','values':[1,-1,2,3]}])
    reject('waterfall',series=[{'name':'A','values':[100,35,-12,7,999]}])
    reject('waterfall',options={'roles':['total']})
    reject('percent_stacked_column',series=[{'name':'A','values':[0,0,0]}])
    reject('scatter',options={})
    reject('bubble',series=examples['bubble']['series'][:2])
    reject('bubble',series=examples['bubble']['series'][:2]+[{'name':'尺寸','values':[1,0,2,3]}])
    reject('funnel',series=[{'name':'A','values':[10,12,9,8,7]}])
    reject('treemap',options={'parents':['wrong length']})
    reject('treemap',options={'parents':['a/b/c/d/e']*7})
    reject('gantt',options={'tasks':[{'start':'2026-02-30','end':'2026-03-01'}]*4})
    reject('gantt',options={'tasks':[{'start':'2026-10-10','end':'2026-10-01'}]*4})
    reject('gantt',options={'tasks':[{'start':'2026-10-01','end':'2026-10-10','progress':101}]*4})
    for bad in [True,None,'3',float('nan'),float('inf')]:
        reject('pie',series=[{'name':'v','values':[2,3,4,bad]}])
    # Full-circle segments, negative ranges, zero areas and same-day milestones.
    edgecases=[examples['pie']|{'series':[{'name':'A','values':[5,0,0,0]}]},
        examples['doughnut']|{'series':[{'name':'A','values':[0,0,5,0]}]},
        examples['gauge']|{'series':[{'name':'A','values':[-5]}],'options':{'min':-10,'max':10}},
        examples['area']|{'series':[{'name':'A','values':[0]*5}]},
        examples['scatter']|{'series':[{'name':'X','values':[-2]*5},{'name':'Y','values':[-10]*5}]},
        examples['gantt']|{'options':{'tasks':[{'start':'2026-10-01','end':'2026-10-01'}]*4}}]
    for payload in edgecases:ET.fromstring(tool._chart_svg(normalize(payload)))
    # No model HTML/code execution: escape data in every template.
    malicious=examples['treemap']|{'labels':['<script>alert(1)</script>',*examples['treemap']['labels'][1:]]}
    svg=tool._chart_svg(normalize(malicious))
    assert '<script>' not in svg and '&lt;script&gt;' in svg
    for alias,canonical in [('column','bar'),('butterfly','tornado'),('donut','doughnut'),('stacked','stacked_column'),('stacked100','percent_stacked_column')]:
        assert normalize(examples[canonical]|{'chart_type':alias})['chart_type']==canonical
    for name in ['雷達圖','儀表盤','圓餅圖','矩形樹狀圖','氣泡圖','甘特圖','漏斗圖','蝴蝶圖','百分比堆積柱形圖','area chart','bubble plot']:
        assert guard._wants_chart('請畫'+name),name
    assert not guard._wants_chart('請畫網路拓撲圖')
    quick_req=SimpleNamespace(state=SimpleNamespace())
    await guard.inlet({'messages':[{'role':'user','content':'畫雷達圖'}]},quick_req)
    delta={'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'name':'render_data_chart','arguments':json.dumps(examples['radar'],ensure_ascii=False)}}]}}]}
    streamed=guard.stream(delta,quick_req)['choices'][0]['delta']
    assert '現成圖表樣板' in streamed['content'] and '推論' in streamed['content']
    assert '"values"' not in streamed['content'] and streamed['tool_calls']
    # JSON recovery preserves options; code remains hidden and reload state agrees.
    class FakeRenderer:
        async def render_data_chart(self,**kwargs):
            assert kwargs['options']['max']==100
            return '![雷達圖](/static/chart-test.png)'
    guard._renderer=lambda:FakeRenderer()
    req=SimpleNamespace(state=SimpleNamespace())
    body={'messages':[{'role':'user','content':'請畫雷達圖'}]}
    await guard.inlet(body,req)
    event={'choices':[{'delta':{'content':'先比較各維度，再看共同量尺。\n```json\n'+json.dumps(examples['radar'],ensure_ascii=False)+'\n```'}}]}
    guard.stream(event,req)
    assert '```' not in event['choices'][0]['delta']['content']
    body['messages'].append({'role':'assistant','content':'先比較各維度。\n'+json.dumps(examples['radar'],ensure_ascii=False)})
    response=(await guard.outlet(body,__request__=req))['messages'][-1]
    assert 'chart-test.png' in response['content'] and '先比較' in response['content']
    assert '"options"' not in response['content']
    assert response['content']==response['output'][0]['content'][0]['text']
    structured_req=SimpleNamespace(state=SimpleNamespace())
    structured_body={'model':'gemma4:26b-mlx','messages':[{'role':'user','content':'請畫雷達圖'}]}
    await guard.inlet(structured_body,structured_req)
    assert structured_req.state.fireworks_diagram['structured'] and structured_body['tool_ids']==[]
    prepared=guard.request(structured_body,structured_req)
    assert prepared['tools']==[] and prepared['response_format']['json_schema']['name']=='statistical_chart'
    assert '不要工具' in prepared['messages'][0]['content']
    structured_body['messages'].append({'role':'assistant','content':'{"error":"資料不完整"}'})
    failure=(await guard.outlet(structured_body,__request__=structured_req))['messages'][-1]['content']
    assert '未完成' in failure and '"error"' not in failure
    pack=ROOT/'deliverables/statistical-chart-templates-v1'
    if (pack/'preview.html').exists():
        import re
        for name in ['preview',*examples]:
            for link in re.findall(r'(?:href|src)="([^"#]+)"',(pack/(name+'.html')).read_text()):
                assert (pack/link).is_file(),(name,link)
    print('PASS: arithmetic, invalid/missing values, source escaping, aliases, unknown progress, date validation, JSON recovery, no-code streaming')
    print('PASS: all deterministic SVG layouts in',round(time.perf_counter()-started,3),'s (excludes model/PNG time)')


asyncio.run(main())
