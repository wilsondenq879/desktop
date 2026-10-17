"""Build an offline, paginated SVG gallery with per-provider provenance."""
import html
import importlib.util
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables/architecture-icon-pack-v2'
spec=importlib.util.spec_from_file_location('gallery_renderer',ROOT/'scripts/openwebui-fireworks-renderer-tool.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
catalog=module.Tools._icon_catalog()
OUT.mkdir(parents=True,exist_ok=True)
index=[]
for id,item in catalog.items():
    provider=item.get('provider') or ('hardware' if id.startswith('hardware:') else 'local')
    slug=id.split(':')[-1]
    directory=OUT/'svg'/provider
    directory.mkdir(parents=True,exist_ok=True)
    plate,ink=module.Tools._brand_palette(item) if item.get('category')=='brand' else ('','#E5E7EB')
    svg=module.Tools._glyph(item,ink,id.replace(':','-'))
    svg.set('width','64');svg.set('height','64')
    desc=ET.SubElement(svg,'desc')
    desc.text=f"{item.get('source','Original local generic equipment')} | {item.get('license','MIT')} | See ../../licenses/{provider} and NOTICE.html. Brand marks identify products; no endorsement."
    (directory/(slug+'.svg')).write_text(ET.tostring(svg,encoding='unicode'))
    index.append({'id':id,'label':item['label'],'provider':provider,'license':item.get('license','MIT'),
        'aliases':item.get('aliases',[]),'brand':item.get('category')=='brand','plate':plate,
        'src':'svg/'+provider+'/'+slug+'.svg'})
shutil.copytree(ROOT/'resources/architecture-icon-pack/extended/licenses',OUT/'licenses',dirs_exist_ok=True)
# Local original notices remain separate from third-party trademarks.
local_license=ROOT/'deliverables/architecture-icon-pack-v1/LICENSE'
if local_license.is_file():
    for provider in ('local','hardware'):
        (OUT/'licenses'/provider).mkdir(exist_ok=True)
        shutil.copy2(local_license,OUT/'licenses'/provider/'LICENSE')
lock=json.loads((ROOT/'resources/architecture-icon-pack/extended/sources.lock.json').read_text())
(OUT/'sources.lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2))
(OUT/'index.json').write_text(json.dumps(index,ensure_ascii=False,separators=(',',':')))
notices=['<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>圖示來源與授權</title><style>body{max-width:900px;margin:32px auto;padding:16px;font:16px/1.6 system-ui;background:#0b0f17;color:#e5e7eb}a{color:#38bdf8}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>圖示來源與授權</h1><p>品牌標誌僅供識別，不表示背書。開源圖庫授權不取代各品牌商標、外觀及使用規範。</p><p><a href="preview.html">回到圖庫</a></p>']
for provider,data in lock['providers'].items():
    notices.append('<h2>'+html.escape(provider)+'</h2><p>'+html.escape(data['version'])+' · '+html.escape(data['license'])+'</p><a href="'+html.escape(data['source'])+'">上游來源</a>')
    for file in sorted((OUT/'licenses'/provider).iterdir()):
        notices.append('<h3>'+html.escape(file.name)+'</h3><pre>'+html.escape(file.read_text())+'</pre>')
notices.append('<h2>原創設備圖示</h2><p>MIT；通用設備示意，不是官方產品圖。機箱、埠位、尺寸與機櫃安裝相容性不得由圖示推定。</p></html>')
(OUT/'NOTICE.html').write_text(''.join(notices))
payload=json.dumps(index,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
page='''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Open WebUI 技術圖庫 v2</title>
<style>:root{color-scheme:dark;font-family:system-ui,"PingFang TC",sans-serif;background:#0b0f17;color:#f8fafc}*{box-sizing:border-box}body{margin:0}main{max-width:1280px;margin:auto;padding:32px 20px}h1{font-size:clamp(26px,4vw,38px);line-height:1.3}p{line-height:1.7;color:#b4c1d1}.tools{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}input,select,button,.link{font:inherit;border:1px solid #475569;border-radius:9px;background:#172235;color:#f8fafc;min-height:44px;padding:10px 14px}input{flex:1;min-width:180px}button{cursor:pointer}button:hover,.link:hover{border-color:#38bdf8}button:focus-visible,input:focus-visible,select:focus-visible,a:focus-visible{outline:2px solid #38bdf8;outline-offset:3px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(175px,1fr));gap:12px}.card{min-height:180px;display:flex;align-items:center;flex-direction:column;gap:10px;padding:16px 10px}.card img{width:64px;height:64px;object-fit:contain}.card.brand img{background:#f8fafc;padding:7px;border-radius:9px}.card span{font-size:14px}.card code{font-size:11px;color:#b4c1d1;overflow-wrap:anywhere}.card small{font-size:11px;color:#b4c1d1}.links{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.link{text-decoration:none}nav{display:flex;justify-content:space-between;gap:16px;align-items:center;margin:24px 0}.status{min-height:26px;color:#b4c1d1}.examples{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.examples img{width:100%;height:auto;display:block;border:1px solid #475569;border-radius:12px}.examples a{color:#e5e7eb;text-decoration:none}.examples span{display:block;padding:12px}footer{padding:20px 0;color:#b4c1d1;line-height:1.6}@media(max-width:420px){main{padding:20px 12px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.tools{gap:8px}.card{min-height:174px}.examples{grid-template-columns:1fr}}</style>
<main><p>OPEN WEBUI · LOCAL TECHNICAL ASSETS V2</p><h1>設備、品牌、服務，各有自己的符號。</h1><p>四套向量圖庫與原創網通／Local AI 元件，在伺服器本機搜尋、選取與渲染。品牌標誌只作識別；通用機箱並非官方產品外觀或規格。</p><div class="links"><a class="link" href="NOTICE.html">來源與授權</a><a class="link" href="sources.lock.json">版本紀錄</a></div>
<section aria-labelledby="templates"><h2 id="templates">六種構圖，不改變設備與連線</h2><div class="examples">EXAMPLES</div></section>
<div class="tools"><input type="search" id="query" aria-label="搜尋圖示" placeholder="搜尋 ASUS、Ollama、GPU、NAS、網卡…"><select id="provider" aria-label="圖庫來源"><option value="">所有圖庫</option><option value="hardware">Local AI／網通硬體</option><option value="local">原創通用符號</option><option value="lucide">Lucide</option><option value="lobe">Lobe Icons</option><option value="dashboard">Dashboard Icons</option><option value="simple">Simple Icons</option></select></div><p id="status" class="status" role="status"></p><div id="grid" class="grid"></div><nav aria-label="圖庫分頁"><button id="prev">上一頁</button><span id="page"></span><button id="next">下一頁</button></nav><footer>點選圖示複製 nodes[].icon ID；每頁最多 60 個，不一次載入所有圖像。SVG 來源已清理，無須外部 CDN。<br>模型可省略 icon 自動選圖，或用 search_diagram_assets 查詢。授權與品牌限制請見上方來源頁。</footer></main>
<script>const all=PAYLOAD;let page=0,list=all;const grid=document.getElementById('grid'),query=document.getElementById('query'),provider=document.getElementById('provider'),status=document.getElementById('status');function render(){const terms=query.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);list=all.filter(i=>(!provider.value||provider.value===i.provider)&&terms.every(t=>[i.id,i.label,...i.aliases].join(' ').toLowerCase().includes(t)));const pages=Math.max(1,Math.ceil(list.length/60));page=Math.min(page,pages-1);grid.replaceChildren();for(const i of list.slice(page*60,(page+1)*60)){const b=document.createElement('button');b.className='card'+(i.brand?' brand':'');b.setAttribute('aria-label','複製圖示 ID：'+i.id);const img=document.createElement('img');img.src=i.src;img.alt='';img.loading='lazy';img.width=64;img.height=64;b.append(img);for(const [tag,text]of [['span',i.label],['code',i.id],['small',i.provider+' · '+i.license]]){const e=document.createElement(tag);e.textContent=text;b.append(e)}b.onclick=async()=>{try{await navigator.clipboard.writeText(i.id);status.textContent='已複製 '+i.id}catch{status.textContent='圖示 ID：'+i.id}};grid.append(b)}status.textContent='顯示 '+list.length+' / '+all.length+' 個圖示';document.getElementById('page').textContent=(page+1)+' / '+pages;document.getElementById('prev').disabled=page===0;document.getElementById('next').disabled=page===pages-1;}query.oninput=provider.onchange=()=>{page=0;render()};document.getElementById('prev').onclick=()=>{page--;render()};document.getElementById('next').onclick=()=>{page++;render()};render();</script></html>'''
names={'layered':'分層架構','star':'星狀拓撲','dual-compute':'雙機互連','rack':'Mini rack 配置','dataflow':'資料流','ecosystem':'生態圈'}
examples=''.join('<a href="'+slug+'.html"><img src="'+slug+'.png" alt="'+name+'示意範例" loading="lazy"><span>'+name+'</span></a>' for slug,name in names.items())
page=page.replace("img.alt='';", "img.alt='';if(i.plate)img.style.background=i.plate;")
(OUT/'preview.html').write_text(page.replace('PAYLOAD',payload).replace('EXAMPLES',examples))
print(json.dumps({'icons':len(index),'preview':str(OUT/'preview.html'),'sources':list(lock['providers'])},ensure_ascii=False))
