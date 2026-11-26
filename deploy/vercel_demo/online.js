'use strict';
const $=s=>document.querySelector(s), project=$('#project-text'), status=$('#status');
const STORE='nextwise.online.project.v1';
let choices={};
try { const saved=JSON.parse(localStorage.getItem(STORE)||'{}'); project.value=saved.project||''; choices=saved.choices||{}; } catch (_) { status.textContent='Browser storage is unavailable.'; }
function save(){try{localStorage.setItem(STORE,JSON.stringify({project:project.value,choices}));}catch(_){status.textContent='Browser storage is unavailable; changes are not saved.';}}
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
    try{response=await fetch('/api/discover',{method:'POST',headers:{'Content-Type':'application/json','X-Nextwise-Access':$('#access-code').value},body:JSON.stringify({project:project.value}),signal:controller.signal});}finally{clearTimeout(timer);}
    const result=await response.json();if(!response.ok)throw new Error(result.message||'Discovery did not complete.');
    add('h2','Project understanding',$('#understanding'));add('p',result.understanding,$('#understanding'));
    if(result.clarifications.length){add('p','Please add answers to your project description and discover again.',$('#clarifications'));for(const q of result.clarifications)add('p',q,$('#clarifications'));}
    for(const item of result.recommendations){
      const card=add('article','',$('#recommendations'));card.className='card recommendation';
      add('h2',item.innovation,card);
      for(const [label,key] of [['Project area','project_area'],['Potential improvement','improvement'],['Why it matters','relevance'],['Feasibility','feasibility'],['Cost','cost'],['Integration effort','effort'],['Uncertainty','uncertainty'],['Next action','next_action']]){add('h3',label,card);add('p',item[key],card);}
      add('p','Publication date: not verified.',card);add('blockquote',item.source_quote,card);
      const link=add('a',item.source_title||'Source',card);link.href=item.source_url;link.target='_blank';link.rel='noopener noreferrer';
      const id=project.value.trim()+'\n'+item.source_url;for(const [label,value] of [['Remember','remember'],['Explore','explore'],['Dismiss','dismiss']]){const b=add('button',label,card);b.type='button';b.className='button quiet';b.onclick=()=>{choices[id]=value;save();if(value==='dismiss')card.hidden=true;else status.textContent='Choice saved in this browser.';};}
      if(choices[id]==='dismiss')card.hidden=true;
    }
    status.textContent=result.notice|| (result.clarifications.length?'More context is needed.':result.recommendations.length?'Potential opportunities are ready to review.':'No supported opportunities found.');
  }catch(error){status.textContent=error.message||'Discovery failed; no recommendations were substituted.';}
  finally{button.disabled=false;}
};
