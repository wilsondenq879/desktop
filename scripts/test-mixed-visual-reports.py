"""The actual missing-image regression: reports may contain both visual kinds."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mixed_guard',ROOT/'scripts/openwebui-visual-diagram-filter.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
prompt='你思考一下 桌面型25G SFP28 交換機市場，技術角度繪製25G交換機對GPU cluster用途架構，文字解說與RDMA/PFC/jumbo frame，用圖表繪製與非RDMA差異，整理完整評估報告，要有文字圖表資訊。'
architecture='![架構](/static/openwebui-generated/fireworks/architecture.png)'
numeric='![數值](/static/openwebui-generated/fireworks/chart-test.png)'
prose='## 一、市場\n市場資料須查證。\n\n## 二、架構\n設備關係。\n\n## 三、比較\n|方式|路徑|\n|--|--|\n|RDMA|NIC|\n\n## 四、限制\n無可比實測，不宣稱效能倍數。'


async def main():
    for model in ['gemma4:26b-mlx','gemma4:26b-nvfp4','gpt-oss:20b']:
        guard=module.Filter();req=SimpleNamespace(state=SimpleNamespace())
        body={'model':model,'messages':[{'role':'user','content':prompt}]}
        await guard.inlet(body,req)
        assert not req.state.fireworks_diagram.get('structured')
        assert req.state.fireworks_diagram['mixed'] and req.state.fireworks_diagram['report']
        assert 'openwebui-mixed-visual-report' in body['messages'][0]['content']
        # Native renderer completed, but old chart-only outlet deleted it.
        state=req.state.fireworks_diagram
        state.update(artifact=architecture,chunks=[prose+'\n'+architecture],architecture_artifacts=[architecture])
        body['messages'].append({'role':'assistant','content':prose+'\n'+architecture})
        result=(await guard.outlet(body,__request__=req))['messages'][-1]
        assert architecture in result['content'] and '## 四、限制' in result['content']
        assert '未取得可驗證' in result['content'] and '本次圖表未完成' not in result['content']
        assert result['content']==result['output'][0]['content'][0]['text']
        # Both tools succeeded: retain both exactly once and keep full report.
        state['chart_artifacts']=[numeric,numeric]
        result=(await guard.outlet(body,__request__=req))['messages'][-1]['content']
        assert result.count(architecture)==1 and result.count(numeric)==1
        assert '## 一、市場' in result and '## 四、限制' in result
    # A missing native tool call is recoverable without rewriting the report.
    guard=module.Filter();req=SimpleNamespace(state=SimpleNamespace())
    body={'model':'gemma4:26b-mlx','messages':[{'role':'user','content':prompt}]}
    await guard.inlet(body,req)
    async def recover(*args,**kwargs):return {'title':'示意','nodes':[],'edges':[]},None
    class FakeRenderer:
        async def render_technical_architecture(self,**kwargs):return architecture
    guard._recover_plan=recover;guard._renderer=lambda:FakeRenderer()
    body['messages'].append({'role':'assistant','content':prose+'\n{{render_technical_architecture}}'})
    result=(await guard.outlet(body,__request__=req,__user__={'id':'synthetic'}))['messages'][-1]['content']
    assert architecture in result and '{{render_' not in result and '## 四、限制' in result
    data=json.dumps({'nodes':[],'edges':[]})
    assert guard._remove_visual_data('重點'+data+'結論')=='重點結論'
    for query in ['畫一張雷達圖','請畫長條圖','畫一張圓餅圖']:
        assert not module.Filter._visual_intents(query)[1],query
    print('PASS: mixed reports, both artifact types, legacy image, no invented data, report preservation, native-miss recovery, content/output sync')


asyncio.run(main())
