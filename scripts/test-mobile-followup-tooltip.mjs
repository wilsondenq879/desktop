import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const code = fs.readFileSync(new URL('../resources/openwebui-mobile-followups.js', import.meta.url), 'utf8');
const make = enabled => ({state:{isEnabled:enabled,isDestroyed:false},disable(){this.state.isEnabled=false;this.disabled=(this.disabled||0)+1;},enable(){this.state.isEnabled=true;}});
const active = make(true), preDisabled=make(false), unrelated=make(true);
let mutation, resize, observerCount=0;
const media={matches:true,addEventListener(type,callback){assert.equal(type,'change');resize=callback;}};
const wrappers=[active,preDisabled,unrelated].map((tooltip,i)=>({_tippy:tooltip,querySelector(){return i===2?null:{};}}));
const context={window:{},matchMedia:()=>media,document:{readyState:'complete',body:{},querySelectorAll:()=>wrappers},
  MutationObserver:class{constructor(callback){mutation=callback;observerCount++;}observe(){}},
  requestAnimationFrame(callback){callback();}};
vm.runInNewContext(code,context);
assert.equal(active.state.isEnabled,false);
assert.equal(preDisabled.state.isEnabled,false);
assert.equal(unrelated.state.isEnabled,true);
mutation();assert.equal(active.disabled,1,'Do not repeatedly disable or retrigger observers');
media.matches=false;resize();
assert.equal(active.state.isEnabled,true);
assert.equal(preDisabled.state.isEnabled,false,'Never enable tooltips disabled by another component');
const later=make(true);wrappers.push({_tippy:later,querySelector:()=>({})});
media.matches=true;mutation();assert.equal(later.state.isEnabled,false,'Newly streamed follow-ups must be handled');
vm.runInNewContext(code,context);assert.equal(observerCount,1,'No duplicate observers');
console.log('PASS: mobile tooltips disabled, desktop restored, unrelated controls unchanged, streamed additions, idempotent installation');
