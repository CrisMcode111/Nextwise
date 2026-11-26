'use strict';
const $=s=>document.querySelector(s), project=$('#project-text'), status=$('#status');
const STORE='nextwise.online.project.v1';
let choices={}, history=[];
try { const saved=JSON.parse(localStorage.getItem(STORE)||'{}'); project.value=saved.project||''; choices=saved.choices||{}; history=Array.isArray(saved.history)?saved.history:[]; } catch (_) { status.textContent='Browser storage is unavailable.'; }
function save(){try{localStorage.setItem(STORE,JSON.stringify({project:project.value,choices,history}));}catch(_){status.textContent='Browser storage is unavailable; changes are not saved.';}}
function discoveryHistory(){
  const entries=history.slice(-10).map(({innovation,source_url,decision})=>({innovation,source_url,decision}));
  for(const [id,decision] of Object.entries(choices)){
    const prefix=project.value.trim()+'\n';
    if(id.startsWith(prefix)&&['remember','explore','dismiss'].includes(decision)){
      const source_url=id.slice(prefix.length);if(source_url.length<=300&&!entries.some(x=>x.source_url===source_url))entries.push({innovation:'Previously reviewed opportunity',source_url,decision});
    }
  }
  return entries.slice(-10);
}
project.addEventListener('input',save);
function add(tag,text,parent){const e=document.createElement(tag);e.textContent=text;parent.append(e);return e;}
$('#project-file').onchange=async e=>{const file=e.target.files?.[0];if(!file)return;try{project.value=await readProjectFile(file);save();status.textContent='Review the extracted text before discovery.';}catch(error){status.textContent=error.message;}finally{e.target.value='';}};
$('#read-github').onclick=async()=>{const button=$('#read-github');button.disabled=true;status.textContent='Reading public repository…';try{const r=await fetch('/api/github',{method:'POST',headers:{'Content-Type':'application/json','X-Nextwise-Access':$('#access-code').value},body:JSON.stringify({url:$('#github-url').value})});const data=await r.json();if(!r.ok)throw new Error(data.message);project.value=data.text;save();status.textContent=data.notice;}catch(error){status.textContent=error.message||'Repository could not be read.';}finally{button.disabled=false;}};
$('#discover').onclick=async()=>{
  if(project.value.trim().length<20){status.textContent='Describe your project in at least 20 characters.';return;}
  const button=$('#discover');button.disabled=true;status.textContent='Understanding your project and researching public sources…';
  $('#recommendations').replaceChildren();$('#understanding').replaceChildren();$('#clarifications').replaceChildren();
  try{
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),55000);
    let response;
    try{response=await fetch('/api/discover',{method:'POST',headers:{'Content-Type':'application/json','X-Nextwise-Access':$('#access-code').value},body:JSON.stringify({project:project.value,history:discoveryHistory()}),signal:controller.signal});}finally{clearTimeout(timer);}
    const result=await response.json();if(!response.ok)throw new Error(result.message||'Discovery did not complete.');
    add('h2','Project understanding',$('#understanding'));add('p',result.understanding,$('#understanding'));
    if(result.clarifications.length){add('p','Please add answers to your project description and discover again.',$('#clarifications'));for(const q of result.clarifications)add('p',q,$('#clarifications'));}
    for(const item of result.recommendations){
      const card=add('article','',$('#recommendations'));card.className='card recommendation';
      add('h2',item.innovation,card);
      for(const [label,key] of [['What is new','novelty'],['Project area','project_area'],['Potential improvement','improvement'],['Why it matters','relevance'],['How to apply','application'],['Why this opportunity','comparison'],['Feasibility','feasibility'],['Cost','cost'],['Integration effort','effort'],['Uncertainty','uncertainty'],['Next action','next_action']]){if(item[key]){add('h3',label,card);add('p',item[key],card);}}
      add('p',item.publication_date?'Publication date reported by search provider: '+item.publication_date+' (not independently verified).':'Publication date: not verified.',card);add('blockquote',item.source_quote,card);
      const link=add('a',item.source_title||'Source',card);link.href=item.source_url;link.target='_blank';link.rel='noopener noreferrer';
      const id=project.value.trim()+'\n'+item.source_url;
      let previous=history.find(x=>x.source_url===item.source_url);
      if(!previous){previous={innovation:item.innovation.slice(0,300),source_url:item.source_url.slice(0,300),decision:choices[id]||'seen'};history.push(previous);history=history.slice(-10);save();}
      for(const [label,value] of [['Remember','remember'],['Explore','explore'],['Dismiss','dismiss']]){const b=add('button',label,card);b.type='button';b.className='button quiet';b.onclick=()=>{choices[id]=value;previous.decision=value;save();if(value==='dismiss')card.hidden=true;else status.textContent='Choice saved in this browser.';};}
      if(choices[id]==='dismiss')card.hidden=true;
    }
    status.textContent=result.notice|| (result.clarifications.length?'More context is needed.':result.recommendations.length?'Potential opportunities are ready to review.':'No supported opportunities found.');
  }catch(error){status.textContent=error.message||'Discovery failed; no recommendations were substituted.';}
  finally{button.disabled=false;}
};
