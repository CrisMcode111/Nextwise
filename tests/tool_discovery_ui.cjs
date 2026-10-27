// Execute the actual app script against a small DOM fixture; no browser/network dependency.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const preview=JSON.parse(fs.readFileSync(0,'utf8'));
class Element {
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.ownText='';this.classList={add(){},toggle(){}};}
  set textContent(value){this.ownText=String(value);this.children=[];}
  get textContent(){return this.ownText+this.children.map(x=>x.textContent).join(' ');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;this.ownText='';}
  addEventListener(){}
}
const nodes=new Map();
const document={querySelector(selector){if(!nodes.has(selector))nodes.set(selector,new Element('div'));return nodes.get(selector);},
  createElement:tag=>new Element(tag),addEventListener(){},getElementById(){return null;}};
const context=vm.createContext({document,window:{addEventListener(){}},location:{hash:''},URL,
  fetch:()=>new Promise(()=>{}),setTimeout(){},clearTimeout(){}});
vm.runInContext(fs.readFileSync('web/app.js','utf8'),context);
context.preview=preview;
vm.runInContext('paintToolCandidates(preview)',context);
const root=nodes.get('#tool-candidates');
function descendants(node){return [node,...node.children.flatMap(descendants)];}
assert.equal(root.children.filter(n=>n.tagName==='ARTICLE').length,3);
assert.equal(root.textContent.split('Discovery candidate — not yet validated').length-1,3);
assert(root.textContent.includes('coverage is incomplete'));
assert(root.textContent.includes(preview.candidates[0].description));
assert(!descendants(root).some(n=>['BUTTON','FORM','TEXTAREA'].includes(n.tagName)));
const opportunity=nodes.get('#opportunities');
const before=opportunity?.textContent;
context.preview={...preview,candidates:[{...preview.candidates[0],title:'<img src=x onerror=alert(1)>',description:'<script>untrusted()</script>'}]};
vm.runInContext('paintToolCandidates(preview)',context);
assert(root.textContent.includes('<script>untrusted()</script>'));
assert(!descendants(root).some(n=>['IMG','SCRIPT'].includes(n.tagName)));
assert.equal(opportunity?.textContent,before);
context.preview={...preview,candidates:[]};
vm.runInContext('paintToolCandidates(preview)',context);
assert(root.textContent.includes('No new tool candidates met'));
assert.equal(root.children.filter(n=>n.tagName==='ARTICLE').length,0);
const calls=[];
context.fetch=async(path,options)=>{calls.push([path,options?.method||'GET']);return {ok:true,json:async()=>({status:{running:false,message:'Fixture complete'},tool_preview:preview})};};
(async()=>{
  await nodes.get('#check-updates').onclick();
  assert.deepEqual(calls,[['/api/discovery/check?scope=tools','POST'],['/api/discovery?scope=tools','GET']]);
  assert.equal(root.children.filter(n=>n.tagName==='ARTICLE').length,3);
  assert.equal(nodes.get('#check-updates').disabled,false);
  document.querySelector('#opportunities-status').textContent='Saved opportunities preserved';
  context.fetch=async(path)=>{if(path.includes('/check?'))return {ok:true,json:async()=>({})};throw new Error('Fixture polling failure');};
  await nodes.get('#check-updates').onclick();
  assert.equal(nodes.get('#opportunities-status').textContent,'Saved opportunities preserved');
  assert.equal(nodes.get('#check-updates').disabled,false);
  assert.equal(vm.runInContext('discoveryBusy || toolCheckActive',context),false);
  assert.equal(root.children.filter(n=>n.tagName==='ARTICLE').length,0);
  console.log('PASS actual app rendering: candidates, labels, empty state, unavailable feeds, safe text, opportunity separation, manual preview routes');
})().catch(error=>{console.error(error);process.exitCode=1;});
