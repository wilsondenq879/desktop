// Generate a real-browser fixture with the DOM from FollowUps/Tooltip.svelte.
// No login or production chat submission required. The page runs layout checks.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'deliverables/mobile-followups');
fs.mkdirSync(out, {recursive:true});
const css = fs.readFileSync(path.join(root, 'resources/openwebui-mobile-followups.css'), 'utf8');
const questions = [
  '既然轉向消費級，那 NVIDIA 的 CUDA 跟 AMD 的 ROCm，在本地 AI 推論與開發支援上有什麼差異？',
  '如果我想組一台預算 5–8 萬台幣左右的 AI 入門主機，主要用於本地模型推論與程式開發，你會如何分配 GPU、記憶體與電源預算？',
  '在 Windows 環境下使用消費級 GPU 跑 AI，是用 WSL2 還是原生環境比較適合？請比較安裝難度與限制。',
  '長網址換行測試：https://example.invalid/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmno'
];
const escape = s => s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
function frame(dark, large, width) {
  return `<!doctype html><html class="${dark?'dark':''}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  *{box-sizing:border-box}html{font-size:${large?32:16}px}body{margin:0;padding:16px;background:${dark?'#171717':'#fff'};color:${dark?'#eee':'#111'};font-family:system-ui}
  .flex{display:flex}.flex-col{flex-direction:column}.text-left{text-align:left}.gap-1{gap:4px}.line-clamp-1{display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}.w-full{width:100%}button{font:inherit;border:0;background:transparent;text-align:left;color:inherit;padding:4px 0;cursor:pointer}hr{width:100%}
  ${css}</style><h3>跟進 · ${width}px${large?' · 200% 文字':''}</h3><div class="mt-4"><div>跟進</div><div class="flex flex-col text-left gap-1 mt-1.5">${questions.map((q,i)=>`<div class="line-clamp-1"><button class="py-1 bg-transparent text-left text-sm flex items-center gap-2 w-full" aria-label="跟進：${escape(q)}" onclick="document.getElementById('selected').textContent=this.textContent.trim()"><div class="line-clamp-1">${escape(q)}</div></button></div>${i<questions.length-1?'<hr>':''}`).join('')}</div></div>
  <p id="selected" aria-live="polite"></p><div id="unrelated"><div class="line-clamp-1">模型選單不應被全域解除截斷</div></div></html>`;
}
const cases = [
  {width:375,dark:true}, {width:390,dark:false}, {width:375,dark:true,large:true},
  {width:767,dark:true}, {width:1024,dark:true,desktop:true}
];
const frames = cases.map((c,i)=>`<section><iframe title="${c.width}px ${c.dark?'深色':'淺色'} ${c.large?'大字':''}" id="case-${i}" style="width:${c.width}px;height:${c.large?1670:760}px" srcdoc="${escape(frame(c.dark,c.large,c.width))}"></iframe></section>`).join('');
const testScript = `const cases=${JSON.stringify(cases)};const results=[];
window.addEventListener('load',()=>{
  cases.forEach((test,i)=>{
    const doc=document.getElementById('case-'+i).contentDocument;
    const win=doc.defaultView;const buttons=[...doc.querySelectorAll('button[aria-label]')];
    const mobile=win.matchMedia('(max-width:767px), (hover:none) and (pointer:coarse)').matches;
    const checks=[];
    for(const button of buttons){
      const inner=button.firstElementChild,outer=button.parentElement;
      if(mobile){
        checks.push(win.getComputedStyle(inner).webkitLineClamp==='none');
        checks.push(win.getComputedStyle(outer).webkitLineClamp==='none');
        checks.push(button.getBoundingClientRect().height>=48);
        checks.push(button.scrollWidth<=button.clientWidth+1);
        checks.push(inner.scrollHeight<=inner.clientHeight+1);
      }else checks.push(win.getComputedStyle(inner).webkitLineClamp==='1');
    }
    checks.push(win.getComputedStyle(doc.querySelector('#unrelated > div')).webkitLineClamp==='1');
    checks.push(doc.documentElement.scrollWidth<=test.width+1);
    // This fixture has no network submission; confirm full question survives click.
    buttons[1].click();checks.push(doc.getElementById('selected').textContent===buttons[1].textContent.trim());
    results.push({width:test.width,large:!!test.large,dark:test.dark,mobile,ok:checks.every(Boolean),checks:checks.length});
  });
  document.getElementById('results').textContent=JSON.stringify(results,null,2);
  document.title=results.every(r=>r.ok)?'PASS 手機跟進問題':'FAIL 手機跟進問題';
});`;
const html = `<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>跟進問題測試</title><style>body{margin:24px;background:#0b0f17;color:#f8fafc;font:16px system-ui}main{display:flex;gap:24px;flex-wrap:wrap}iframe{border:1px solid #475569;border-radius:16px}pre{white-space:pre-wrap}section{max-width:100%;overflow:auto}</style><h1>手機跟進問題：完整問句</h1><pre id="results">正在測試…</pre><main>${frames}</main><script>${testScript}</script></html>`;
fs.writeFileSync(path.join(out,'preview.html'), html);
console.log(path.join(out, 'preview.html'));
