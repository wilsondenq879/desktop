"""Build a reusable, data-only catalog and render every trusted chart template."""
import argparse
import asyncio
import html
import importlib.util
import json
import os
import re
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables/statistical-chart-templates-v1'


def examples():
    base = dict(title='統計圖表樣板（示意）', unit='指標值', data_kind='illustrative',
        sources=[], note='純樣板示範資料，不是品牌評分、市佔調查或設備實測。', better='neutral')
    def make(kind, title, labels, series, **kwargs):
        return base | dict(chart_type=kind, title=title+'（示意）', labels=labels,
            series=[dict(name=name, values=values) for name,values in series]) | kwargs
    return {
        'bar':make('bar','落地 AI 推論速度',['配置 A','配置 B','配置 C'],[('推論速度',[42,58,73])],unit='tokens/s'),
        'horizontal_bar':make('horizontal_bar','工作站方案功耗',['單機小型工作站','雙節點小型工作站','四節點協同配置'],[('功耗',[65,130,260])],unit='W',better='lower'),
        'grouped_bar':make('bar','不同工作負載的延遲',['輕量','一般','高負載'],[('配置 A',[4,8,15]),('配置 B',[3,6,11])],unit='ms',better='lower'),
        'tornado':make('tornado','A/B 方案用戶結構',['研究分析','模型開發','內容製作','網路維運'],[('方案 A',[30,45,25,35]),('方案 B',[40,32,48,28])],unit='人'),
        'radar':make('radar','方案多面向能力',['推論','連線','擴充','節能','維護'],[('方案 A',[80,70,60,85,75]),('方案 B',[70,85,90,60,80])],unit='分',options={'max':100},note='虛構且已使用共同 0–100 量尺的樣式示範，不是實際產品評分。'),
        'gauge':make('gauge','研究任務達成率',['本週研究完成率'],[('完成率',[72])],unit='%',options={'min':0,'max':100,'target':85}),
        'line':make('line','每季流量變化',['Q1','Q2','Q3','Q4'],[('資料流量',[12,18,16,25]),('控制流量',[4,6,7,9])],unit='TB'),
        'area':make('area','每日資料處理量',['週一','週二','週三','週四','週五'],[('已處理資料',[20,35,28,48,62])],unit='GB'),
        'waterfall':make('waterfall','專案預算增減',['期初','設備新增','折扣','軟體','期末'],[('金額',[100,35,-12,7,130])],unit='萬元',options={'roles':['total','change','change','change','total']}),
        'pie':make('pie','樣本用途組成',['研究','開發','維運','內容'],[('樣本數',[42,28,18,12])],unit='件'),
        'doughnut':make('doughnut','儲存空間分配',['模型權重','研究資料','成品輸出','其他'],[('空間',[40,30,20,10])],unit='TB'),
        'stacked_column':make('stacked_column','不同部門用量與結構',['研究組','開發組','維運組'],[('模型',[30,40,15]),('資料',[20,35,10]),('輸出',[10,15,5])],unit='TB'),
        'percent_stacked_column':make('percent_stacked_column','不同部門用量佔比',['研究組','開發組','維運組'],[('模型',[30,40,15]),('資料',[20,35,10]),('輸出',[10,15,5])],unit='TB'),
        'treemap':make('treemap','落地 AI 專案成本結構',['GPU','CPU','儲存','交換器','網卡','工具','管理'],[('成本',[40,18,14,10,6,8,4])],unit='萬元',options={'parents':['硬體/運算','硬體/運算','硬體/資料','硬體/網路','硬體/網路','軟體','軟體']}),
        'scatter':make('scatter','功耗與推論速度',['配置 A','配置 B','配置 C','配置 D','配置 E'],[('功耗',[65,95,125,165,210]),('推論速度',[20,42,39,62,68])],unit='分軸標示',options={'x_unit':'W','y_unit':'tokens/s'}),
        'bubble':make('bubble','功耗、推論速度與採購預算',['配置 A','配置 B','配置 C','配置 D'],[('功耗',[65,100,145,210]),('推論速度',[24,42,55,70]),('預算',[4,6,9,14])],unit='分軸標示',options={'x_unit':'W','y_unit':'tokens/s','size_unit':'萬元'}),
        'gantt':make('gantt','小型 AI Demo 專案時程',['需求確認','環境建置','功能開發','驗證展示'],[],unit='日',options={'tasks':[
            {'start':'2026-10-01','end':'2026-10-03','planned_start':'2026-10-01','planned_end':'2026-10-03','progress':100},
            {'start':'2026-10-03','end':'2026-10-07','planned_start':'2026-10-03','planned_end':'2026-10-06','progress':100},
            {'start':'2026-10-06','end':'2026-10-13','planned_start':'2026-10-06','planned_end':'2026-10-12','progress':70},
            {'start':'2026-10-13','end':'2026-10-16','planned_start':'2026-10-12','planned_end':'2026-10-15'}]}),
        'funnel':make('funnel','產品 Demo 轉換流程',['接觸','有興趣','完成 Demo','啟動試用','正式採用'],[('人數',[1000,620,380,200,120])],unit='人'),
        'quadrant':make('quadrant','方案相對定位',['方案 A','方案 B','方案 C','方案 D'],[('成本低至高',[.2,.65,.8,.4]),('能力少至多',[.3,.6,.9,.75])],unit='相對位置',note='模型定性示意，非市佔率、實際評分或市場調查。'),
    }


DESCRIPTIONS = {
    'bar':'同單位類別大小，零基準；柱形／長條比較。', 'horizontal_bar':'長名稱與多項比較，橫向閱讀。',
    'grouped_bar':'相同類別中的多組數據，保留個別數值。', 'tornado':'兩組對應數據左右鏡像；相同尺度，不當負數。',
    'radar':'共同量尺的多維比較；3–8 軸，不捏造評分。', 'gauge':'單一指標、量尺上下限及目標；不是時間趨勢。',
    'line':'依資料順序呈現趨勢，不擅自重排。', 'area':'折線下方填色，強調數量變化；多組非堆疊。',
    'waterfall':'期初、增減與期末；自動累計、驗證總額。', 'pie':'少量分類的組成；分母為圖中所列合計。',
    'doughnut':'組成與合計，內圈顯示總額。', 'stacked_column':'同時比較絕對總量與組成。',
    'percent_stacked_column':'各組正規化為 100%，比較組成而非總量。', 'treemap':'葉節點權重與父層路徑；面積正比權重。',
    'scatter':'兩個連續變數；分軸單位，沒有自動因果推論。', 'bubble':'X/Y 加第三個量；氣泡面積正比第三量。',
    'gantt':'日期區間、計畫與執行、已知完成率；未知進度不填零。', 'funnel':'同母體、遞減階段的留存與轉換率；寬度正比數量。',
    'quadrant':'0–1 定性相對位置，不能冒充市佔或市場調查。',
}


async def build(render=True):
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = examples()
    if render:
        spec=importlib.util.spec_from_file_location('chart_templates',ROOT/'scripts/openwebui-fireworks-renderer-tool.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        tool=module.Tools()
        os.environ['OPENWEBUI_FIREWORKS_SKILL_ROOT']=str(ROOT/'resources/openwebui-managed-skills/fireworks-tech-graph')
        os.environ['OPENWEBUI_FIREWORKS_OUTPUT_DIR']=str(OUT/'generated')
        for key,payload in catalog.items():
            started=time.perf_counter()
            result=await tool.render_data_chart(**payload)
            match=re.search(r'/(chart-[\w-]+)\.png',result)
            if not match:raise AssertionError(key+': '+result)
            for ext in ['svg','png','html','csv']:
                source=OUT/'generated'/(match[1]+'.'+ext)
                shutil.copy2(source,OUT/(key+'.'+ext))
            preview=OUT/(key+'.html')
            preview.write_text(preview.read_text().replace(match[1]+'.csv',key+'.csv').replace(match[1]+'.svg',key+'.svg'))
            print(json.dumps({'template':key,'seconds':round(time.perf_counter()-started,3)},ensure_ascii=False),flush=True)
    catalog_path=ROOT/'resources/statistical-chart-templates/catalog.json'
    catalog_path.parent.mkdir(parents=True,exist_ok=True)
    # Generated data artifacts, not hand-authored source files.
    document={'version':1,'description':'樣板程式碼重用，模型只填資料；範例數值全為示意。','templates':[
        {'id':key,'description':DESCRIPTIONS[key],'payload':payload} for key,payload in catalog.items()]}
    catalog_path.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    shutil.copy2(catalog_path,OUT/'catalog.json')
    cards=[]
    for key,payload in catalog.items():
        cards.append('<article><a href="'+key+'.html"><img loading="lazy" width="960" height="680" src="'+key+'.png" alt="'+html.escape(payload['title'])+'"><h2>'+html.escape(payload['title'].replace('（示意）',''))+'</h2></a><p>'+html.escape(DESCRIPTIONS[key])+'</p><div class="links"><a href="'+key+'.html">放大與數據表</a><a href="'+key+'.svg" download>SVG</a><a href="'+key+'.csv" download>CSV</a></div></article>')
    (OUT/'preview.html').write_text('<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'; base-uri \'none\'"><title>統計圖表樣板庫</title><style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0B0F17;color:#F8FAFC;font:16px/1.6 system-ui}main{max-width:1280px;margin:auto;padding:24px}header{max-width:860px;padding:24px 0}h1{font-size:clamp(26px,5vw,38px);margin:8px 0}header p,article p{color:#CBD5E1}small{color:#94A3B8}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:24px}article{border:1px solid #334155;border-radius:16px;overflow:hidden;background:#111827}article h2,article p,.links{padding:0 20px}article img{display:block;width:100%;height:auto;aspect-ratio:960/680;object-fit:contain;background:#0B0F17}h2{font-size:20px}a{color:#7DD3FC;text-decoration:none}a:focus-visible{outline:3px solid #F8FAFC;outline-offset:2px}.links{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.links a{display:flex;align-items:center;min-height:44px;padding:8px;border-radius:8px;border:1px solid #334155}a:hover{color:white}footer{padding:32px 0;overflow-wrap:anywhere}@media(max-width:480px){main{padding:16px}}</style><main><header><small>OPEN WEBUI · REUSABLE DATA VISUALS · V1</small><h1>統計圖表樣板庫</h1><p>19 種可重用配置：18 種圖型加分組長條。先文字、後成品；模型只填資料與選圖，伺服器套版，不重新生成繪圖程式。每張圖都提供向量檔與完整數據表。</p><p>本頁全部為示意資料，不代表產品效能、品牌能力或市場調查。圖型快取的是程式與版式，不快取舊回答資料。</p><a href="catalog.json">下載資料格式與示例 JSON</a></header><section>'+''.join(cards)+'</section><footer>以原生 SVG 樣板繪製，無新引入第三方圖表套件。樣板重用可減少繪圖程式生成，但模型推理與查證來源仍需時間。手機可點「放大與數據表」橫向捲動閱讀。</footer></main></html>')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--no-render',action='store_true');args=parser.parse_args()
    asyncio.run(build(not args.no_render))
