"""Build the original, offline SVG library and searchable preview from its manifest."""
import argparse
import html
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE = {"network":"#19b5a5", "compute":"#7eafff", "storage":"#73cba3", "security":"#e8b760", "edge":"#b2bfce", "ai":"#83c4df", "software":"#99b1d2", "operations":"#a7b6c5"}


def svg(icon, color="currentColor"):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" role="img"><title>{html.escape(icon["label"])}</title>{icon["body"]}</svg>'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "deliverables/architecture-icon-pack-v1")
    parser.add_argument("--demo-svg", type=Path)
    parser.add_argument("--png", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "resources/architecture-icon-pack/manifest.json").read_text())
    icons = manifest["icons"]
    assert len(icons) == 64 and len({i["id"] for i in icons}) == 64
    for icon in icons:
        tree = ET.fromstring(svg(icon))
        assert all(e.tag.rsplit("}", 1)[-1] in {"svg", "title", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon"} for e in tree.iter())
        assert not any("href" in k or k.startswith("on") for e in tree.iter() for k in e.attrib)
    args.out.mkdir(parents=True, exist_ok=True)
    for variant, color in (("svg", "#f4f6f8"), ("svg-light", "#263443"), ("svg-accent", None)):
        folder = args.out / variant
        folder.mkdir(exist_ok=True)
        for icon in icons:
            (folder / (icon["id"] + ".svg")).write_text(svg(icon, color or PALETTE[icon["category"]]), encoding="utf-8")
    shutil.copy2(ROOT / "resources/architecture-icon-pack/manifest.json", args.out / "manifest.json")
    symbols = ''.join(f'<symbol id="{i["id"]}" viewBox="0 0 48 48">{i["body"]}</symbol>' for i in icons)
    (args.out / "symbols.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+symbols+'</svg>')
    sheet = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 1580"><rect width="1440" height="1580" fill="#0e1012"/><g font-family="PingFang TC, sans-serif" fill="#f4f6f8"><text x="48" y="64" font-size="30" font-weight="600">網通與本地 AI · 架構圖示庫</text><text x="48" y="96" font-size="16" fill="#94a3b8">64 個原創 SVG 圖示 / 8 類 / 3 色版本 / 可編輯向量</text>']
    for idx, icon in enumerate(icons):
        x, y = 36 + idx % 8 * 172, 128 + idx // 8 * 176
        sheet.append(f'<rect x="{x}" y="{y}" width="160" height="158" rx="10" fill="#14191f" stroke="#2c333b"/><svg x="{x+54}" y="{y+22}" width="52" height="52" viewBox="0 0 48 48" fill="none" stroke="{PALETTE[icon["category"]]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{icon["body"]}</svg><text x="{x+80}" y="{y+106}" text-anchor="middle" font-size="15">{html.escape(icon["label"])}</text><text x="{x+80}" y="{y+132}" text-anchor="middle" font-size="11" fill="#8c9baa">{icon["id"]}</text>')
    sheet.append('</g></svg>')
    overview = args.out / "overview.svg"
    overview.write_text(''.join(sheet))
    if args.png:
        import cairosvg
        cairosvg.svg2png(url=str(overview), write_to=str(args.out / "overview.png"), output_width=1440)
    demo = args.demo_svg.read_text() if args.demo_svg else ""
    if demo:
        shutil.copy2(args.demo_svg, args.out / "example-network.svg")
    examples = ROOT / "deliverables/architecture-diagram-examples"
    if examples.is_dir():
        shutil.copytree(examples, args.out / "examples", dirs_exist_ok=True, ignore=shutil.ignore_patterns("generated"))
    payload = json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c")
    preview = """<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Local Architecture Icons</title>
<style>:root{color-scheme:dark;--bg:#0e1012;--card:#14191f;--line:#303841;--text:#f4f6f8;--muted:#95a3b3;--accent:#19b5a5}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:'Avenir Next','PingFang TC',sans-serif}main{max-width:1280px;margin:auto;padding:40px 28px}h1{font-size:clamp(27px,4vw,42px);font-weight:600;letter-spacing:-.04em;margin:12px 0}p{color:var(--muted);line-height:1.7;text-wrap:pretty}small{color:var(--accent);letter-spacing:.16em;font-size:11px}.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:26px 0 16px}input,select,button,a.button{font:inherit;color:var(--text);background:var(--card);border:1px solid var(--line);border-radius:7px;padding:11px 14px;min-height:44px;text-decoration:none}input{flex:1;min-width:180px}button{cursor:pointer}button:hover,a.button:hover{border-color:var(--accent)}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:3px}.grid{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:12px}.icon{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:11px;min-height:154px;padding:18px 8px;text-align:center}.icon svg{width:var(--size,44px);height:var(--size,44px);color:var(--ink)}.icon span{font-size:13px}.icon code{font:10px ui-monospace,monospace;color:var(--muted);word-break:break-word}.example{border:1px solid var(--line);border-radius:12px;margin:32px 0;overflow:auto;background:#0e1012}.example>svg{display:block;width:100%;height:auto;min-width:640px}.example header{padding:18px 24px;border-bottom:1px solid var(--line);font-size:14px;color:var(--muted)}.status{min-height:24px;color:var(--muted);font-size:13px;margin:12px 0}.light{color-scheme:light;--bg:#f5f6f8;--card:#fff;--line:#d8dee6;--text:#263443;--muted:#607080}footer{margin:32px 0;font-size:13px;color:var(--muted)}@media(max-width:1000px){.grid{grid-template-columns:repeat(6,minmax(0,1fr))}}@media(max-width:700px){main{padding:24px 16px}.grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.icon{min-height:144px}.icon span{font-size:12px}.toolbar{gap:8px}}@media(max-width:400px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}</style>
<main><small>LOCAL ARCHITECTURE ICONS · V1</small><h1>讓架構圖，看得出設備。</h1><p>64 個通用設備與服務圖示，涵蓋網通、本地 AI、儲存與安全。點選圖示即可複製可編輯 SVG。圖示代表設備類別；實際產品規格仍由圖表內容決定。</p>DEMO
<div class="toolbar"><input id="query" aria-label="搜尋圖示" placeholder="搜尋 NAS、VPN、GPU、交換器…"><select id="category" aria-label="圖示分類"><option value="">全部分類</option></select><button id="theme">切換明暗</button><a class="button" href="../Local-Architecture-Icons-v1.zip" download>下載整包 ZIP</a></div><div class="toolbar"><label for="size">預覽尺寸</label><input id="size" type="range" min="32" max="64" value="44" aria-label="圖示尺寸"></div><div class="status" id="status" role="status"></div><div class="grid" id="grid"></div><footer>48 × 48 viewBox · 1.8px 圓角線條 · 64 種造形 × 3 色版本 · SVG Sprite + Manifest · MIT</footer></main>
<script>const catalog=PAYLOAD;const grid=document.querySelector('#grid'),status=document.querySelector('#status'),q=document.querySelector('#query'),category=document.querySelector('#category');const palette=PALETTE;Object.entries(catalog.categories).forEach(([id,name])=>category.add(new Option(name,id)));function source(i,color='currentColor'){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${i.body}</svg>`}function render(){grid.replaceChildren();const term=q.value.trim().toLowerCase(),list=catalog.icons.filter(i=>(!category.value||i.category===category.value)&&[i.id,i.label,...i.aliases].join(' ').toLowerCase().includes(term));status.textContent=`顯示 ${list.length} / 64 · 點選複製 SVG`;list.forEach(i=>{const b=document.createElement('button');b.className='icon';b.style.setProperty('--ink',palette[i.category]);b.setAttribute('aria-label','複製 '+i.label+' SVG');b.innerHTML=source(i)+`<span>${i.label}</span><code>${i.id}</code>`;b.onclick=async()=>{try{await navigator.clipboard.writeText(source(i));status.textContent='已複製 '+i.label+' SVG'}catch{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([source(i)],{type:'image/svg+xml'}));a.download=i.id+'.svg';a.click();URL.revokeObjectURL(a.href);status.textContent='已下載 '+i.label+' SVG'}};grid.append(b)})}q.oninput=category.onchange=render;document.querySelector('#theme').onclick=()=>document.body.classList.toggle('light');document.querySelector('#size').oninput=e=>document.documentElement.style.setProperty('--size',e.target.value+'px');render();</script></html>"""
    demo_html = '<section class="example"><header>範例：圖示、設備面板與真實分支連線。示意配置，非特定型號規格。</header>'+demo+'</section><div class="toolbar"><a class="button" href="examples/smb-topology.html">SMB 網路</a><a class="button" href="examples/local-ai-fabric.html">Local AI 分層</a><a class="button" href="examples/mcp-services.html">模型 / MCP 整合</a></div>' if demo else ''
    preview = preview.replace("PAYLOAD", payload).replace("PALETTE", json.dumps(PALETTE)).replace("DEMO", demo_html)
    (args.out / "preview.html").write_text(preview, encoding="utf-8")
    (args.out / "README.md").write_text("# Local Architecture Icons v1\n\n64 個原創通用技術圖示，192 個 SVG 色彩版本。\n\n- svg/: 白色線條，供深底使用\n- svg-light/: 深色線條，供淺底使用\n- svg-accent/: 分類色\n- symbols.svg: 可用 `<use href=\"symbols.svg#nas\">` 複用\n- manifest.json: id、中文名稱、語意別名與向量資料\n- preview.html: 離線可搜尋、可複製 SVG 的圖庫\n- overview.svg / overview.png: 圖示總覽\n\nOpen WebUI 繪圖工具的 nodes 可傳入 `icon: \"nas\"`。未指定時依設備名稱自動選圖示。交換器可傳入 `port_groups: [{\"label\":\"25G\",\"count\":4,\"tone\":\"active\"}]`；僅依已知規格標示，不自動假設埠數或速度。通用符號不宣稱為品牌官方圖像。\n\n設計：48px 網格、1.8px 線條、圓角端點；黑底搭配青綠與藍色連線。擴充模式保留既有工具名稱、成品網址與禁止串流程式碼行為。參考圖為使用者已選定的視覺基準。Design Read: 技術圖示庫；變化3、動態1、密度7、素材6、參考忠實度9。\n", encoding="utf-8")
    (args.out / "LICENSE").write_text("MIT License\n\nCopyright (c) 2026 Local Architecture Icons contributors\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files, to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies, subject to inclusion of this copyright and permission notice.\n\nTHE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY ARISING FROM THE SOFTWARE OR ITS USE.\n")
    archive = args.out.parent / "Local-Architecture-Icons-v1.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(args.out.rglob("*")):
            if file.is_file(): bundle.write(file, file.relative_to(args.out.parent))
    print(json.dumps({"icons":len(icons),"svg_files":len(list(args.out.glob('svg*/*.svg'))),"preview":str(args.out / 'preview.html'),"zip":str(archive)},ensure_ascii=False))


if __name__ == "__main__":
    main()
