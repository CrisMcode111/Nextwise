'use strict';
const DEMO_STORAGE='nextwise.public-demo.decisions.v1';
let demoContext=null,demoBusy=false,demoPreview=null,demoStorageFailed=false,reviewedProject=null,reviewedText='',reviewedKey='';
const sourceCache=new Map();
let demoDecisions={};
try{
  const saved=JSON.parse(localStorage.getItem(DEMO_STORAGE)||'{}');
  if(saved&&typeof saved==='object'&&!Array.isArray(saved)){
    for(const [id,record] of Object.entries(saved)){
      if((['project','instructor','pydantic','promptfoo',...GUIDED_SCENARIO.candidates.map(item=>item.demo_source_id)].includes(id)||/^repo-[a-f0-9]{16}$/.test(id))&&record
        &&['Adopt','Test','Defer','Reject'].includes(record.choice)&&typeof record.rationale==='string'
        &&typeof record.saved_at==='string')demoDecisions[id]=record;
    }
  }
}catch(_){demoStorageFailed=true;}

// Suggested next steps, not measured benefits. Guided cards use checked official
// excerpts; ordinary discovery cards require evidence from the current checks.
const DEMO_STEPS={
  structured_extraction:{heading:'Make free text easier to work with',why:'This may help turn the free-text information you described into a consistent format.',
    action:'Compare one sample from your project with the format this tool supports.'},
  constraint_validation:{heading:'Check the details before using your data',why:'This may help check the data fields and formats you said you need to validate.',
    action:'Pick one sample and list the fields and types you want checked.'},
  extraction_evaluation:{heading:'See whether AI outputs keep the right details',why:'This may help build repeatable tests for the AI output checks you described.',
    action:'Write three example inputs and the results you would expect before trying it.'}
};
function isDeferred(id){return ['Reject','Defer'].includes(demoDecisions[id]?.choice);}
function isCandidateDeferred(item){
  return isDeferred(item.demo_source_id)||demoContext.sources.some(source=>isDeferred(source.id)&&source.name.toLowerCase()===item.title.toLowerCase());
}

function paintDemoChoices(){
  const target=$('#demo-choices');target.replaceChildren();
  if(demoStorageFailed)paragraph('Browser storage is unavailable. Choices may not persist; no server storage is used.',target,'notice');
  const records=Object.entries(demoDecisions).filter(([id])=>id!=='project');
  if(!records.length)paragraph('You haven’t saved any choices yet.',target,'meta');
  for(const [id,record] of records){
    const source=demoContext.sources.find(source=>source.id===id);
    paragraph(`${source?.name||(typeof record.tool_name==='string'?record.tool_name.slice(0,100):id)}: ${record.choice==='Test'?'Explored earlier':isDeferred(id)?'Not interested':record.choice} · ${record.saved_at}`,target,'meta');
  }
}

function selectedOpportunity(){
  return Object.entries(demoDecisions).find(([,record])=>record.choice==='Test'&&record.selected===true&&record.project_key===reviewedKey);
}

function paintDemoSelection(){
  const target=$('#selection-status');
  const selected=reviewedKey&&selectedOpportunity();
  target.hidden=!selected;
  target.replaceChildren();
  if(selected){
    el('h2','selection-heading',`You chose ${selected[1].tool_name} to explore.`,target);
    paragraph(`Next step: ${selected[1].next_step}`,target,'selection-action');
    paragraph('Saved only in this browser. No trial has been started and nothing has been purchased.',target,'meta');
  }
}

function saveDemoChoice(id,choice,title,nextStep=''){
  const record={choice,rationale:choice==='Test'?'Selected to explore; not adopted or tested.':'Not interested.',saved_at:new Date().toISOString(),tool_name:String(title||id).slice(0,100)};
  const updated={...demoDecisions};
  if(choice==='Test'){
    for(const [key,value] of Object.entries(updated)){
      if(value.project_key===reviewedKey&&value.selected)updated[key]={...value,selected:false};
    }
    Object.assign(record,{project_key:reviewedKey,selected:true,next_step:String(nextStep).slice(0,1200)});
  }
  updated[id]=record;
  try{localStorage.setItem(DEMO_STORAGE,JSON.stringify(updated));}
  catch(_){$('#choice-status').textContent='Browser storage is unavailable. Your choice was not saved; no server fallback was used.';$('#selection-status').hidden=false;$('#selection-status').textContent=$('#choice-status').textContent;return;}
  demoDecisions=updated;
  $('#choice-status').textContent=choice==='Test'?'Your next step is saved only in this browser.':'Got it. I’ll leave that out on your next visit. Your choice is saved only in this browser.';
  paintDemoChoices();
  paintDemoCandidates();paintDemoSelection();
}

function paintDemoCandidates(){
  const target=$('#tool-candidates');target.replaceChildren();
  if(!demoPreview)return;
  const candidates=demoPreview.candidates.filter(item=>!isCandidateDeferred(item)).slice(0,2);
  for(const item of candidates){
    const row=el('article','card recommendation',null,target);
    const rule=BUSINESS_NEEDS[item.need_id];
    const step=item.guided?{why:item.business_benefit,action:item.next_step}:rule?{heading:rule.label,why:rule.why,action:rule.action}:DEMO_STEPS[item.need_id];
    el('h2','',item.title,row);
    paragraph(`${item.guided?'Prepared for this demo:':'I found'} ${item.title}. ${step?.why||item.reasons[0]}`,row);
    paragraph(item.business_summary||item.description,row);
    paragraph(`A small next step: ${step?.action||'Compare what it offers with one sample customer request.'}`,row);
    paragraph(item.guided?'Official product and advertised features checked; business fit, dietary safety and integration remain untested.':'A possible fit, not yet tested for your business. Pricing, setup and results still need checking.',row,'meta');
    const source=link('Source',item.url,row);
    source.setAttribute('aria-label',`Source for ${item.title}`);
    const choices=el('div','reason-links',null,row);
    const choose=el('button','button','Explore this',choices);choose.type='button';
    const selected=selectedOpportunity()?.[0]===item.demo_source_id;
    choose.textContent=selected?'Selected to explore':'Explore this';
    choose.setAttribute('aria-pressed',String(selected));
    choose.onclick=()=>saveDemoChoice(item.demo_source_id,'Test',item.title,step?.action||'Compare what it offers with one sample customer request.');
    const explain=el('button','button','Explain why',choices);explain.type='button';
    const later=el('button','button quiet','Not interested',choices);later.type='button';
    later.onclick=()=>saveDemoChoice(item.demo_source_id,'Defer',item.title);
    const evidence=el('div','suggestion-evidence',null,row);
    evidence.id='why-'+item.demo_source_id;evidence.hidden=true;
    explain.setAttribute('aria-controls',evidence.id);explain.setAttribute('aria-expanded','false');
    explain.onclick=()=>{evidence.hidden=!evidence.hidden;explain.setAttribute('aria-expanded',String(!evidence.hidden));};
    paragraph('Why this might fit',evidence);
    const needSummary=item.guided?'Generate and adapt recipes and meal plans to user constraints.':step?.heading||'Review this capability against your stated business task.';
    paragraph(`Your stated goal: ${needSummary}`,evidence);
    paragraph('What the source says',evidence);paragraph(item.description,evidence);
    link(item.kind==='discovered_repository'?'Read the repository source':'Read the official source',item.url,evidence);
    if(item.product_url)link('Product website — availability and pricing not checked',item.product_url,evidence);
    paragraph(`Checked ${item.retrieved_at}. This doesn’t tell us when the tool was released.`,evidence,'meta');
    paragraph('What we still need to check',evidence);
    paragraph('This is an idea to explore, not a tested recommendation for your business.',evidence);
    list(item.limitations||[],evidence);
  }
  if(demoPreview.mode==='guided'){
    $('#state').textContent=candidates.length===2?'Two prepared opportunities for AI Raw Gourmet. Choose one to explore; no live AI search was performed.':`${candidates.length} prepared opportunity shown after your browser preferences. Use “Clear this browser’s demo choices” below to reconsider hidden products. No replacements were invented.`;
    return;
  }
  $('#state').textContent=candidates.length?(candidates.length===2?'I found two possible opportunities. Choose one small next step to explore.':'I found one possible opportunity, not two. The checked sources do not support another credible match. You can explore this one.'):
    'I don’t have a usable product to suggest from the checked sources. Public GitHub descriptions may not cover this business challenge, or the matches may need technical setup. I haven’t replaced them with developer libraries; this is not a search of all commercial products or the whole web.';
}

function paintDemoEvidence(){
  const target=$('#demo-evidence');target.replaceChildren();
  el('h3','','What I checked',target);
  for(const source of demoPreview.sources){
    link(source.publisher,source.url,target);
    paragraph(source.error||(source.eligible_items?'Supporting capability passage found; suitability remains unverified.':'No supporting capability passage found.'),target,'meta');
  }
}

async function demoRead(path){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
  try{
    const response=await fetch(path,{signal:controller.signal,cache:'no-store',credentials:'omit'});
    const result=await response.json();
    if(!response.ok)throw new Error('Public demo request did not complete.');
    return result;
  }finally{clearTimeout(timer);}
}

async function checkDemoSources(){
  if(demoBusy||!demoContext||!reviewedProject)return;
  if($('#project-text').value.trim()!==reviewedText){$('#project-status').textContent='Your text has changed. Review it first so I use the right needs.';return;}
  const needs=reviewedProject.needs;
  const sourceNeeds={instructor:'structured_extraction',pydantic:'constraint_validation',promptfoo:'extraction_evaluation'};
  const searchMode=Array.isArray(demoContext.search_sources);
  const needFor=source=>source.need_id||sourceNeeds[source.id];
  const active=(searchMode?demoContext.search_sources:demoContext.sources).filter(source=>needs.some(need=>need.id===needFor(source))&&(searchMode||!isDeferred(source.id))).slice(0,3);
  setProjectBusy(true);
  demoPreview={checked_at:new Date().toISOString(),candidates:[],sources:[],status:'success'};
  try{
    // A project fingerprint scopes selections without storing the project text.
    const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(reviewedText));
    reviewedKey=Array.from(new Uint8Array(bytes),byte=>byte.toString(16).padStart(2,'0')).join('');
    paintDemoSelection();
    if(isGuidedRawGourmet(reviewedText)){
      demoPreview={mode:'guided',checked_at:'2026-10-27',status:'success',
        candidates:GUIDED_SCENARIO.candidates.map(item=>({...item,guided:true,kind:'official_product',
          project_evidence:reviewedText,reasons:[item.business_benefit]})),
        sources:GUIDED_SCENARIO.candidates.map(item=>({url:item.url,publisher:item.publisher,eligible_items:1,
          error:'Official product page checked on 27 October 2026; retained excerpt, not a live check or tested business outcome.'}))};
      $('#guided-notice').hidden=false;
      $('#guided-notice').textContent=GUIDED_SCENARIO.label+'. '+GUIDED_SCENARIO.scope;
      paintDemoCandidates();paintDemoEvidence();paintDemoSelection();
      $('#discovery-status').textContent='Prepared official-source evidence; zero discovery requests, model calls or paid API calls. Existing browser preferences still apply.';
      return;
    }
    $('#guided-notice').hidden=true;
    for(const source of active){
      let result=sourceCache.get(source.id);
      if(!result){
        if(sourceCache.size>=3){
          demoPreview.status='partial_failure';
          demoPreview.sources.push({url:source.url,publisher:source.name,error:'This visit’s three-search limit is reached. This need was not searched; no extra request was made.'});
          continue;
        }
        $('#search-progress').hidden=false;
        $('#progress-message').textContent=searchMode?`Searching public repositories for ${source.name}…`:`Checking ${source.name}’s public documentation…`;
        try{result=await demoRead('/api/discover?'+(searchMode?'need=':'source=')+encodeURIComponent(source.id));}
        catch(_){result={candidates:[],sources:[{url:source.url,publisher:source.name,eligible_items:0,error:'Public source unavailable or timed out; coverage is incomplete. No retry was made.'}],status:'partial_failure'};}
        finally{$('#search-progress').hidden=true;}
        // Cache failures too. Each fixed source gets at most one attempt this visit.
        sourceCache.set(source.id,result);
      }
      const matchedNeed=needs.find(need=>need.id===needFor(source));
      for(const item of result.candidates){
        if(item.need_id!==matchedNeed.id||(!searchMode&&item.demo_source_id!==source.id)||isCandidateDeferred(item)||demoPreview.candidates.some(prior=>prior.demo_source_id===item.demo_source_id))continue;
        demoPreview.candidates.push({...item,project_evidence:matchedNeed.evidence,
          reasons:[`Your stated goal: “${reviewedProject.goal}”. You mentioned: “${matchedNeed.evidence}”. The owner describes a matching capability; this is a possible trial, not a proven benefit.`]});
      }
      demoPreview.sources.push(...result.sources);
      if(result.status!=='success')demoPreview.status='partial_failure';
    }
    // Give each confirmed need a first slot before filling from the remaining matches.
    const pool=demoPreview.candidates;
    const firstMatches=needs.map(need=>pool.find(item=>item.need_id===need.id)).filter(Boolean);
    demoPreview.candidates=[...new Set([...firstMatches,...pool])].slice(0,3);
    paintDemoCandidates();paintDemoEvidence();paintDemoSelection();
    $('#discovery-status').textContent=`${active.length} relevant source(s); ${demoPreview.candidates.filter(item=>!isCandidateDeferred(item)).slice(0,2).length} unvalidated opportunities shown. ${demoPreview.status==='success'?'Checks complete.':'Some checks failed; coverage is incomplete.'} ${sourceCache.size}/3 source requests used this visit. Pages already checked are reused, including failures. No retries, models, paid search or background monitoring. Your project and file contents never leave this browser.`;
  }catch(_){$('#state').textContent='I couldn’t complete this check. No opportunities were inferred and no selection was saved.';}
  finally{$('#search-progress').hidden=true;setProjectBusy(false);}
}

function setProjectBusy(busy){
  demoBusy=busy;
  $('#assistant-identity').dataset.processing=String(busy);
  for(const id of ['project-text','project-file','review-project','find-ideas','clear-choices'])$('#'+id).disabled=busy;
  for(const input of $('#project-review').querySelectorAll('input'))input.disabled=busy;
}

function reviewProject(){
  if(demoBusy)return;
  const target=$('#project-review');target.replaceChildren();reviewedKey='';paintDemoSelection();$('#guided-notice').hidden=true;
  try{
    reviewedText=$('#project-text').value.trim();reviewedProject=extractProject(reviewedText);
    el('h3','','Your business goal',target);
    paragraph(reviewedProject.goal,target);
    if(reviewedProject.challenges.length){el('h3','','Challenges you mentioned',target);list(reviewedProject.challenges,target);}
    el('h3','','Where I can look for help',target);
    paragraph('These are rule-based matches to what you wrote, not AI reasoning. Edit your description if I missed the point; no technical classification is needed.',target,'meta');
    for(const need of reviewedProject.needs){
      paragraph(need.label,target);el('blockquote','',need.evidence,target);
    }
    $('#project-status').textContent=reviewedProject.needs.length?'I’ve picked possible areas to explore from your description. You can correct the text, or use these needs.':
      'I couldn’t identify a supported business job. Describe a concrete task that costs you time or customers; I won’t invent one.';
    if(isGuidedRawGourmet(reviewedText))$('#project-status').textContent='Supported AI Raw Gourmet guided scenario recognized. Continue to see two prepared, official-source opportunities; no live AI discovery.';
    $('#find-ideas').disabled=false;
  }catch(error){reviewedProject=null;$('#find-ideas').disabled=true;$('#project-status').textContent=error.message;}
  // Never leave suggestions for the previous project on screen after a review.
  demoPreview=null;$('#tool-candidates').replaceChildren();$('#demo-evidence').replaceChildren();
  $('#state').textContent='Review your project on the left, and I’ll use the needs you confirm.';
}

async function initializeDemo(){
  try{
    demoContext=await demoRead('/api/demo');
    if(demoContext.mode!=='public_demo'||demoContext.tavily_enabled!==false)throw new Error('Invalid demo mode');
    const context=$('#demo-context');context.replaceChildren();
    paragraph('Suggestions use your reviewed description. Matching is rule-based, not model reasoning. Project text stays in this browser; it is never included in a source request.',context,'meta');
    paintDemoChoices();
    $('#review-project').onclick=reviewProject;
    $('#project-text').oninput=()=>{if(!demoBusy){reviewedKey='';paintDemoSelection();$('#guided-notice').hidden=true;$('#find-ideas').disabled=true;$('#project-status').textContent='Review your changes before looking for ideas.';demoPreview=null;$('#tool-candidates').replaceChildren();$('#state').textContent='Your project changed. Review the updated needs to continue.';}};
    $('#find-ideas').onclick=async()=>{
      if(demoBusy)return;
      const checkedBefore=sourceCache.size;
      await checkDemoSources();
      if(!demoPreview)return;
      if(demoPreview.mode==='guided'){$('#project-status').textContent='Guided demo — pre-verified opportunities. Official-source checks were prepared in advance; no live search or product trial was run.';return;}
      $('#project-status').textContent=`Applied your selected needs: ${demoPreview.candidates.length} idea(s) available. ${sourceCache.size===checkedBefore?'Reused this visit’s checked results; no new search was made.':demoPreview.status==='success'?'Source checks completed.':'Some sources were unavailable; coverage is incomplete.'}`;
    };
    $('#project-file').onchange=async()=>{
      const file=$('#project-file').files?.[0];if(!file||demoBusy)return;
      setProjectBusy(true);$('#project-status').textContent='Reading this file in your browser…';
      try{$('#project-text').value=await readProjectFile(file);setProjectBusy(false);reviewProject();}
      catch(error){$('#project-status').textContent=error.message;}
      finally{setProjectBusy(false);$('#project-file').value='';}
    };
    $('#clear-choices').onclick=()=>{
      try{localStorage.removeItem(DEMO_STORAGE);}catch(_){$('#choice-status').textContent='Browser storage is unavailable. Choices were not cleared.';return;}
      demoDecisions={};demoStorageFailed=false;paintDemoChoices();paintDemoCandidates();paintDemoSelection();
      $('#choice-status').textContent='Browser choices cleared. Use these needs again to reconsider tools; checked pages will be reused.';
    };
    if($('#project-text').value.trim()){
      reviewProject();await checkDemoSources();
    }else{$('#state').textContent='Tell me about your business or choose a document. I’ll look for up to two evidence-backed opportunities after you review it.';}
  }catch(_){$('#state').textContent='The public demo could not initialize. Refresh to retry; private services will not be contacted.';}
}
initializeDemo();
