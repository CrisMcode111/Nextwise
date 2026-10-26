'use strict';
const $ = s => document.querySelector(s);
let discoveryBusy=false, discoveryReading=false, discoveryTimer=null;
const selectionDrafts=new Map();
const discoveryLabels={initial_inventory:'Initial inventory of recently published items',new_article:'Newly discovered article',article_summary_changed:'Feed title/summary changed (article not fetched)',page_baseline:'Initial monitored-page baseline',monitored_page_changed:'Monitored page edited'};
function paintSemantic(record,parent){
  if(!record||record.status!=='validated'){
    paragraph(record?.error||record?.explanation||'Semantic assessment pending. No project connection has been established.',parent,'notice');
    paragraph('Uncertain. Historical deterministic rules are not used as project reasoning. Failed inputs are cached and are not retried automatically.',parent);
    if(record?.provenance){
      const p=record.provenance;
      paragraph(p.coverage.description,parent,'notice');
      const raw=details('Available source passages and provenance — no project conclusion established',parent);json(p,raw);
      if(p.existing_investigation){paragraph('This source already belongs to the existing investigation. Its saved pilot passed 1/4 lexical quality checks, with evaluator limitations; genuine Defer Version 1 remains unchanged. No duplicate investigation is proposed.',parent,'notice');link('Review existing findings and decision','#update',parent);}
    }
    return;
  }
  const a=record.assessment,p=record.provenance;
  paragraph(record.label,parent,'notice');
  paragraph(`Model: ${record.model.returned_model} · Policy: ${record.policy_version} · Assessed: ${record.assessed_at}`,parent,'meta');
  el('h4','','Project need',parent);paragraph(a.project_need,parent);
  el('h4','','What the source describes',parent);paragraph(a.source_observation,parent);
  a.evidence.forEach(e=>{
    const passage=p.passages.find(x=>x.passage_id===e.passage_id);
    const q=details('Supporting passage and provenance',parent);el('blockquote','human-text',e.exact_quote,q);
    if(passage)paragraph(passage.text,q,'human-text');
    link('Saved source URL',p.url,q);paragraph(`Source ${e.source_id} · Passage ${e.passage_id} · Published ${p.publication_date||'unknown'} · Retrieved ${p.retrieved_at}`,q,'meta');
    paragraph(`Snapshot ${p.snapshot_path} · SHA-256 ${p.raw_sha256}`,q,'meta');
  });
  paragraph(p.coverage.description,parent,'notice');paragraph(`${p.coverage.selected_paragraphs} complete paragraph/excerpt blocks selected; ${p.coverage.omitted_paragraphs} omitted. ${p.coverage.selection}`,parent,'meta');
  if(a.application_hypothesis){el('h4','','Potential application — hypothesis, untested',parent);paragraph(a.application_hypothesis,parent);}
  else paragraph('No application hypothesis is established by the available evidence.',parent);
  el('h4','','Limitations',parent);list(a.limitations,parent);el('h4','','Missing information',parent);list(a.missing_information,parent);
  paragraph(`Priority: ${a.priority}. ${a.priority_reason}`,parent);
  if(p.existing_investigation){paragraph('Follow-up to the existing investigation; no duplicate investigation is proposed.',parent,'notice');paragraph(a.existing_findings_connection,parent);link('Existing investigation and findings','#update',parent);}
  el('h4','','Proposed investigation question',parent);paragraph(a.investigation_question,parent);
  el('h4','','Proposed next step — not executed',parent);paragraph(a.next_step,parent);
}
function paintDiscovery(d){
  const scope=$('#discovery-scope'), target=$('#discovery-results');scope.replaceChildren();target.replaceChildren();
  const limits=details('Approved source scope and limits',scope);
  list([...d.scope.pages,d.scope.feed],limits);
  paragraph(`At most ${d.scope.item_cap} recent feed items within ${d.scope.lookback_days} days. Feed and three fixed pages only; linked articles are not fetched. Missing, invalid or future publication dates are excluded.`,limits);
  paragraph(`${d.scope.max_response_bytes} bytes/source; ${d.scope.socket_timeout_seconds}s socket timeout; ${d.scope.source_deadline_seconds}s read deadline (a blocked read can add one socket timeout); at most ${d.scope.max_redirects} redirects. ${d.scope.destinations}`,limits);
  paragraph('Manual source checks. Semantic assessment uses a separately authorized, capped Meterless/Nemotron run; at most three requests total for this milestone and no automatic retries. No scheduled monitoring or automatic investigation.',limits);
  const saved=d.discovery, run=saved.runs.at(-1);
  if(saved.semantic_context_error)paragraph(saved.semantic_context_error,target,'notice');
  paragraph('Nextwise prepares agent proposals automatically from semantic assessments. Human selection is separate from approval and never launches research.',target);
  const reassessment=saved.reassessments?.at(-1);
  if(reassessment)paragraph(`Relevance reassessed under ${reassessment.policy_version} at ${reassessment.assessed_at}. Classification only; no newly published content or source change is implied.`,target,'notice');
  if(run){
    paragraph(`Last persisted check: ${run.retrieved_at} · ${run.status}. ${run.events.length} inventory/change observations.`,target);
    run.sources.forEach(s=>paragraph(`${s.requested_url}: ${s.error||'retrieved (not verified evidence)'}${s.rss_items!==undefined?` · valid RSS, ${s.rss_items} items; ${s.eligible_unique_items} eligible before cap`:''}`,target,s.error?'notice':'meta'));
    const retrieval=details('Retrieval metadata, raw hashes and source errors',target);json(run.sources,retrieval);
    if(!run.events.length)paragraph(run.status==='success'?'No new or changed readable content in this check.':'No changes detected in successfully checked sources; coverage is incomplete.',target);
  }else paragraph('No confirmed check yet. First feed retrieval establishes a recent inventory; it does not detect new releases.',target);
  const events=new Set((run?.events||[]).map(e=>e.item_id));
  const inventory=details(`Saved candidates (${Object.keys(saved.items).length}) · includes low relevance and previous observations`,target);
  inventory.parentElement.open=true;
  Object.values(saved.items).forEach(item=>{
    const semantic=item.semantic_assessment;
    const row=details(`${item.title} · ${semantic?.category||'uncertain relevance'}`,inventory);
    paragraph(`${events.has(item.id)?'In latest check':'Previously observed'} · ${discoveryLabels[item.kind]}`,row);
    link(item.source===d.scope.feed?'Publisher article (not fetched during discovery)':'Monitored publisher page',item.url,row);
    paragraph(`Published: ${item.publication_date||'unknown'} · First seen: ${item.first_seen} · Retrieved: ${item.retrieved_at}`,row,'meta');
    paintSemantic(semantic,row);
    const assessments=details('Assessment history and cache provenance',row);json({current:semantic,semantic_history:item.semantic_history||[],historical_rules:item.relevance_history||[]},assessments);
    const rev=details(`Revision history (${item.revisions.length}) and exact readable differences`,row);json(item.revisions,rev);
    const form=el('form','',null,row);const labelNode=el('label','','Optional user note',form);
    const reason=el('textarea','',null,labelNode);reason.maxLength=2000;reason.value=selectionDrafts.get(item.id)||'';
    reason.oninput=()=>selectionDrafts.set(item.id,reason.value);
    const save=el('button','button','Review and select agent proposal',form);save.type='submit';save.disabled=discoveryBusy||semantic?.status!=='validated'||!!saved.semantic_context_error||!d.semantic_review_supported;
    const msg=el('p','',null,form);msg.setAttribute('role','status');
    form.onsubmit=async e=>{e.preventDefault();if(discoveryBusy)return;save.disabled=true;msg.textContent='Saving your review selection in H-MEM…';
      try{const r=await fetch('/api/discovery/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:item.id,revision_sha256:item.content_sha256,assessment_cache_key:semantic.cache_key,reason:reason.value})});const result=await r.json();if(!r.ok)throw new Error(result.message);selectionDrafts.delete(item.id);await readDiscovery();$('#discovery-status').textContent='Agent proposal selected for investigation review. Human approval remains separate; research has not started.';}
      catch(e){msg.textContent=e.message||'Save failed; keep your reason and retry.';save.disabled=false;}};
  });
  const proposals=details(`Persisted investigation proposals (${saved.proposals.length})`,target);proposals.parentElement.open=true;
  saved.proposals.forEach(p=>{
    const row=details(`${p.title} · ${p.origin==='agent'?'Agent-prepared proposal':'Historical human proposal'}, not a completed investigation`,proposals);
    link('Source',p.source,row);
    if(p.origin==='agent'){
      paragraph(`Prepared ${p.prepared_at} · ${p.proposal_kind} · Human approval: pending`,row,'notice');
      paintSemantic(p.assessment,row);
      const selection=(saved.proposal_selections||[]).find(s=>s.proposal_id===p.id);
      if(selection){paragraph(`Selected for review ${selection.selected_at}; approval remains separate.`,row);if(selection.user_note)paragraph(selection.user_note,row,'human-text');}
    }else {paragraph(p.selection_reason||'',row,'human-text');json(p,row);}
    paragraph('Proposal only. No investigation, trial, adoption or replacement of the existing investigation was launched.',row,'notice');
  });
}
async function readDiscovery(){
  clearTimeout(discoveryTimer);
  if(loading||decisionSaving){discoveryTimer=setTimeout(readDiscovery,1000);return;}
  if(discoveryReading)return;
  discoveryReading=true;
  try{const r=await fetch('/api/discovery');const d=await r.json();if(!r.ok)throw new Error(d.message);discoveryBusy=d.status.running;$('#check-updates').disabled=discoveryBusy;$('#discovery-status').textContent=d.status.message;
    // Keep the current inventory and any typed selection reason intact while polling.
    if(!discoveryBusy)paintDiscovery(d);
    if(discoveryBusy)discoveryTimer=setTimeout(readDiscovery,1000);
  }catch(e){$('#discovery-status').textContent=e.message||'Local discovery service unavailable; reopen saved discovery to retry.';$('#check-updates').disabled=false;}
  finally{discoveryReading=false;}
}
$('#check-updates').onclick=async()=>{if(discoveryBusy)return;discoveryBusy=true;$('#check-updates').disabled=true;$('#discovery-status').textContent='Starting check…';try{const r=await fetch('/api/discovery/check',{method:'POST'});const d=await r.json();if(!r.ok)throw new Error(d.message);await readDiscovery();}catch(e){discoveryBusy=false;$('#check-updates').disabled=false;$('#discovery-status').textContent=e.message;}};
$('#reload-discovery').onclick=readDiscovery;
// Initial discovery waits for investigation/decision reads, so H-MEM context
// verification cannot starve the authenticated investigation's startup read.
const content = $('#content'), state = $('#state'), refresh = $('#refresh');
let loading = false;
let decisionState=null, decisionContext=null, decisionSaving=false, decisionMessage='', decisionError='';
let decisionDraft={choice:'',rationale:'',next_action:'',request_id:null,expected_head:null,editing:false,started:false};
const decisionPanel=$('#decision-panel');
function parkDecisionPanel(){if(decisionPanel.parentElement!==$('#decision-home'))$('#decision-home').append(decisionPanel);}
function paintDecisionRecord(record,parent){
  const card=el('div','saved-decision',null,parent);pill(`Your ${record.choice} decision · Version ${record.version}`,card);
  paragraph(`${record.created_at_utc} · Recorded by the local user`,card,'meta');
  paragraph(record.rationale,card,'human-text');
  if(record.next_action){label('Your next action / reconsideration condition',card);paragraph(record.next_action,card,'human-text');}
  if(record.needs_review){pill('Needs review · Referenced evidence changed or is unavailable',card,'pending');list(record.integrity_issues,card);}
  const refs=details('Evidence used for this decision',card);
  record.evidence_references.forEach(ref=>{
    const p=el('div','decision-reference',null,refs);
    link(ref.kind.replaceAll('_',' '),`/api/decision-evidence?id=${encodeURIComponent(record.decision_id)}&kind=${encodeURIComponent(ref.kind)}`,p);
    paragraph(`${ref.memory_id} · SHA-256 ${ref.sha256}`,p,'meta');
  });
  paragraph(`Record ${record.decision_id}`,refs,'meta');
}
async function readDecisions(){
  try{
    for(let attempt=0;attempt<10;attempt++){
      const response=await fetch('/api/decisions',{credentials:'same-origin'}),result=await response.json();
      if(response.status===409&&result.code==='loading'&&attempt<9){await new Promise(resolve=>setTimeout(resolve,1000));continue;}
      if(!response.ok)throw new Error(result.message||'Decision history is unavailable.');
      decisionState=result;decisionError='';paintDecisionPanel();break;
    }
  }catch(error){decisionError=error.message||'Decision history is unavailable. Your typed text is kept.';paintDecisionPanel();}
}
function paintDecisionPanel(){
  decisionPanel.replaceChildren();el('h3','','Your decision',decisionPanel);
  paragraph('Your choice is separate from the AI proposal. It does not approve reviews, verify claims, or authorize model calls, experiments or deployment.',decisionPanel,'decision-boundary');
  const notice=el('p','decision-message',decisionError||decisionMessage,decisionPanel);notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
  if(decisionError)notice.classList.add('notice');
  if(!decisionState){
    paragraph('Decision history has not been confirmed. Nothing is shown as undecided or saved until the store responds.',decisionPanel,'muted');
    const retry=el('button','button quiet','Retry history',decisionPanel);retry.onclick=readDecisions;return;
  }
  const history=decisionState.history,head=history.at(-1);
  if(head)paintDecisionRecord(head,decisionPanel);else paragraph('No human decision has been recorded.',decisionPanel,'muted');
  if(decisionDraft.started && decisionDraft.expected_head!==(head?.decision_id??null)){
    paragraph('History changed while you were writing. Read the latest decision before linking your amendment to it.',decisionPanel,'notice');
    const reconcile=el('button','button quiet','I reviewed the latest version · Keep my draft',decisionPanel);
    reconcile.disabled=decisionSaving;
    reconcile.onclick=()=>{decisionDraft.expected_head=head?.decision_id??null;decisionDraft.request_id=null;decisionDraft.editing=true;decisionError='';paintDecisionPanel();};
  }
  if(head&&!decisionDraft.editing){
    const amend=el('button','button quiet','Amend my decision',decisionPanel);amend.id='amend-decision';
    amend.onclick=()=>{decisionDraft={choice:'',rationale:'',next_action:'',request_id:null,expected_head:head.decision_id,editing:true,started:true};decisionMessage='';paintDecisionPanel();};
  }else{
    const form=el('form','decision-form',null,decisionPanel);form.id='decision-form';
    const fields=el('fieldset','decision-choices',null,form);fields.disabled=decisionSaving;el('legend','','Choose one · No default selection',fields);
    ['Adopt','Test','Defer','Reject'].forEach(choice=>{
      const lab=el('label','',null,fields),input=el('input','',null,lab);input.type='radio';input.name='decision-choice';input.value=choice;input.required=true;input.checked=decisionDraft.choice===choice;lab.append(document.createTextNode(choice));
    });
    const rl=el('label','','Your rationale (required)',form);rl.htmlFor='decision-rationale';
    const rationale=el('textarea','',null,form);rationale.id='decision-rationale';rationale.required=true;rationale.maxLength=8000;rationale.rows=3;rationale.value=decisionDraft.rationale;rationale.disabled=decisionSaving;
    const nl=el('label','','Next action or condition for reconsideration (optional)',form);nl.htmlFor='decision-next-action';
    const next=el('textarea','',null,form);next.id='decision-next-action';next.maxLength=4000;next.rows=2;next.value=decisionDraft.next_action;next.disabled=decisionSaving;
    const save=el('button','button',decisionSaving?'Saving and checking persistence…':head?'Save amendment':'Save my decision',form);save.type='submit';save.id='save-decision';
    save.disabled=decisionSaving||!decisionContext||!decisionDraft.choice||!decisionDraft.rationale.trim();
    if(!decisionContext)paragraph('Load and reconcile the live investigation before saving. Your typed text stays here.',form,'muted');
    form.addEventListener('input',()=>{
      if(!decisionDraft.started){decisionDraft.expected_head=head?.decision_id??null;decisionDraft.started=true;}
      decisionDraft.choice=form.querySelector('input:checked')?.value||'';
      decisionDraft.rationale=rationale.value;decisionDraft.next_action=next.value;decisionDraft.request_id=null;
      save.disabled=decisionSaving||!decisionContext||!decisionDraft.choice||!decisionDraft.rationale.trim();
    });
    form.addEventListener('submit',saveDecision);
  }
  const past=details(`Decision history (${history.length} version${history.length===1?'':'s'})`,decisionPanel,'decision-history');
  if(!history.length)paragraph('No records yet.',past,'muted');
  [...history].reverse().forEach(record=>paintDecisionRecord(record,past));
  const retry=el('button','button quiet','Refresh decision history',past);retry.onclick=readDecisions;
}
async function saveDecision(event){
  event.preventDefault();if(decisionSaving||!decisionContext||!decisionDraft.choice||!decisionDraft.rationale.trim())return;
  decisionSaving=true;refresh.disabled=true;decisionMessage='';decisionError='';decisionDraft.request_id ||= crypto.randomUUID();
  const body={explicit_action:'record_human_decision',choice:decisionDraft.choice,rationale:decisionDraft.rationale,
    next_action:decisionDraft.next_action.trim()?decisionDraft.next_action:null,request_id:decisionDraft.request_id,
    expected_head:decisionDraft.expected_head,context:decisionContext};
  paintDecisionPanel();
  try{
    const response=await fetch('/api/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result=await response.json();
    if(!response.ok)throw new Error(result.message||'Save not confirmed. Your typed text is kept for retry.');
    if(!result.ok||!Array.isArray(result.history))throw new Error('Persistence could not be confirmed. Keep your text and retry.');
    decisionState=result;decisionDraft={choice:'',rationale:'',next_action:'',request_id:null,expected_head:null,editing:false,started:false};
    decisionMessage=result.reused?'The saved decision was confirmed. No duplicate version was added.':'Your decision was saved in H-MEM and read back from disk.';
  }catch(error){decisionError=error.message||'Save not confirmed. Your typed text is kept for retry.';}
  finally{decisionSaving=false;refresh.disabled=loading;paintDecisionPanel();}
}
// External artifact content is always inserted as text, never HTML or executable markup.
function el(tag, cls, text, parent) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (parent) parent.append(node);
  return node;
}
function link(text, href, parent) {
  const a = el('a', '', text, parent);
  if (href.startsWith('#')) a.href = href;
  else if(href.startsWith('/api/decision-evidence?')) { a.href=href; a.target='_blank'; a.rel='noopener noreferrer'; }
  else {
    try { const url = new URL(href); if (['https:', 'http:'].includes(url.protocol)) { a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; } } catch (_) { /* Unsafe links stay text. */ }
  }
  return a;
}
function pill(text, parent, cls = '') { return el('span', `tag ${cls}`, text, parent); }
function list(items, parent) { const ul = el('ul', 'list', null, parent); items.forEach(text => el('li', '', text, ul)); return ul; }
function details(title, parent, id = '', cls = '') {
  const d = el('details', `detail ${cls}`, null, parent); if (id) d.id = id;
  el('summary', '', title, d); return el('div', 'detail-body', null, d);
}
function section(id, n, title, tag, cls = '') {
  const s = el('section', 'section', null, content); s.id = id;
  const h = el('div', 'section-header', null, s), titleWrap = el('div', 'section-title', null, h);
  el('span', 'number', n, titleWrap); el('h2', '', title, titleWrap); pill(tag, h, cls); return s;
}
function date(text) { if (!text) return 'Unknown'; const d = new Date(text); return Number.isNaN(d.getTime()) ? text : d.toLocaleDateString('en-GB', {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}); }
function metric(value) { return value === null || value === undefined ? 'Unknown' : new Intl.NumberFormat('en-GB', {maximumFractionDigits:6}).format(Number(value)); }
function json(value, parent) { el('pre', '', typeof value === 'string' ? value : JSON.stringify(value, null, 2), parent); }
function label(text, parent) { el('p', 'label', text, parent); }
function paragraph(text, parent, cls = 'copy') { return el('p', cls, text, parent); }
function recommendationSummary(recommendation) {
  // A shorter excerpt of the saved proposal, not a newly generated recommendation.
  const text=recommendation.recommended_next_step;
  return text.includes(':') ? text.slice(0,text.indexOf(':'))+'.' : text.split(/(?<=\.)\s/)[0];
}
function factValue(value) { return `${JSON.stringify(value)} (${typeof value === 'number' ? 'number' : typeof value})`; }
function comparison(c, parent) {
  const wrap=el('div','comparison-wrap',null,parent);
  const table=el('table','comparison',null,wrap);
  el('caption','','Fixture expectations compared with recorded facts · Saved findings, not a new score',table);
  const header=el('tr','',null,el('thead','',null,table));
  ['Requested fact / fixture expectation','Recorded output','Saved finding'].forEach(text=>{const th=el('th','',text,header);th.scope='col';});
  const body=el('tbody','',null,table);
  c.comparison.rows.forEach(row=>{
    const tr=el('tr','',null,body); tr.dataset.field=row.field;
    const requested=el('th','',null,tr);requested.scope='row';el('strong','',row.field.replaceAll('_',' '),requested);paragraph(factValue(row.expected),requested,'fact-value');
    const output=el('td','',null,tr);
    if(!row.recorded.length)paragraph('Not returned',output,'fact-value');
    row.recorded.forEach(f=>{paragraph(factValue(f.value),output,'fact-value');paragraph(`Input evidence: “${f.evidence}”`,output,'meta');});
    const finding=el('td','',null,tr);row.findings.forEach(text=>paragraph(text,finding,'fact-finding'));
    row.qualifications.forEach(text=>{pill('Saved evaluator qualification',finding,'pending');paragraph(text,finding,'fact-finding');});
  });
  const unknowns=details('Unknown categories: what the record establishes',parent);
  paragraph('The output includes categories beyond this fixture’s required-unknown list. That difference alone does not establish that every extra category is irrelevant, or why it was returned. The saved checks do not exhaustively assess relevance.',unknowns);
  paragraph(`Required by the saved rubric: ${c.comparison.required_unknowns.join(', ') || 'None recorded'}`,unknowns);
  paragraph(`Additional returned categories: ${c.comparison.additional_unknowns.join(', ') || 'None'}`,unknowns);
  paragraph(`Flagged incorrectly unknown by the saved evaluator: ${c.comparison.incorrect_unknowns.join(', ') || 'None'}`,unknowns);
  paragraph(`Saved scoring protocol: ${c.comparison.protocol}`,unknowns,'meta');
}
function openHash() {
  const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (!target) return;
  if (target.tagName === 'DETAILS') target.open = true;
  let ancestor = target.parentElement;
  while (ancestor) { if (ancestor.tagName === 'DETAILS') ancestor.open = true; ancestor = ancestor.parentElement; }
  target.scrollIntoView({block:'start'});
}
window.addEventListener('hashchange', openHash);
function render(d) {
  parkDecisionPanel();
  content.replaceChildren();
  const brief=el('div','card investigation-brief',null,content);brief.id='investigation-brief';
  label('Current investigation',brief);el('h2','brief-question',d.investigation.question,brief);
  const columns=el('div','brief-columns',null,brief);
  const next=el('div','brief-next',null,columns);label('Existing proposed next action',next);
  paragraph(recommendationSummary(d.recommendation),next,'next-summary');
  const briefStatus=el('div','inline-status',null,next);pill('AI-assisted proposal · Pending approval',briefStatus,'pending');
  pill(d.investigation.decision===null?'Original investigation · Decision: not set':String(d.investigation.decision),briefStatus,'neutral');
  const original=details('Read the full original recommendation',next,'original-recommendation');
  paragraph(d.recommendation.recommended_next_step,original);paragraph(d.recommendation.rationale,original,'explanation');
  const earlyLinks=el('div','reason-links',null,next);link('Inspect pilot findings ↗','#pilot',earlyLinks);link('Read qualified publisher claims ↗','#claims',earlyLinks);
  decisionContext=Object.fromEntries(['manifest_id','artifact_hashes','run_id'].map(key=>[key,d.diagnostics[key]]));
  columns.append(decisionPanel);paintDecisionPanel();
  const project = section('project', '01', 'My project', 'Approved project context');
  const grid = el('div', 'grid', null, project), p = el('div', 'card', null, grid);
  label('The project', p); el('h3', 'large', d.profile.name, p); paragraph(d.profile.objective, p);
  paragraph(d.profile.stage, p, 'meta');
  const chips = el('div', 'chips', null, p); d.profile.constraints.forEach(c => el('span', '', c, chips));
  const task = el('div', 'card', null, grid); label('The specific task', task); el('h3', '', 'Preserve what the user actually asks for', task);
  paragraph(d.task.description, task); paragraph(`${metric(d.profile.team_size)} developer · ${d.profile.development_environment}`, task, 'meta');
  const unknowns = el('div', 'unknown-grid', null, task);
  [['Current baseline', d.unknowns.baseline], ['Verified pricing', d.unknowns.verified_prices_and_quotas]].forEach(([name, value]) => { const u = el('div','unknown', value === null ? 'Unknown' : JSON.stringify(value), unknowns); el('strong','',name,u); });

  const update = section('update', '02', 'Investigated update', 'Under investigation', 'neutral');
  const uc = el('div','card',null,update); label('The question',uc); el('h3','large',d.investigation.question,uc);
  paragraph(`${d.investigation.technology} · Release date: ${date(d.investigation.release_date)}`,uc,'meta');
  const criteria = el('div','criteria',null,uc);
  d.investigation.evaluation_criteria.forEach(c => { const col=el('div','',null,criteria); el('h3','',c.name,col); el('p','',c.description,col); });
  const sc = el('div','card',null,update);
  const domains = new Set(d.sources.map(s=>s.publisher_domain));
  label(`${d.sources.length} source pages · ${domains.size} publisher domains`,sc);
  paragraph('Multiple pages from the same publisher are not independent corroboration. Retrieved content remains publisher material.',sc,'muted');
  d.sources.forEach(s=>{
    const row=el('div','source',null,sc); row.id=`source-${s.id}`;
    const text=el('div','',null,row); link(s.title,s.requested_url,text);
    paragraph(`${s.publisher_domain} · Published: ${date(s.publication_date)} · Retrieved: ${date(s.retrieved_at_utc)} (UTC)`,text,'meta');
    const related=d.claims.filter(c=>c.source_id===s.id); pill(`${related.length} publisher claim${related.length===1?'':'s'}`,row,'neutral');
    related.forEach((c,i)=>{ if (i===0) link('Inspect linked claims ↓',`#claim-${c.claim_pointer.split('/').pop()}`,text); });
  });

  const evidence = section('evidence','03','Evidence & decision','Review pending','pending');
  const recommendation=el('div','card recommendation',null,evidence); pill('AI-assisted interpretation · Pending your review',recommendation);
  el('h3','','The documented next action',recommendation); paragraph(recommendationSummary(d.recommendation),recommendation);
  link('Full original recommendation and rationale ↗','#original-recommendation',recommendation);
  paragraph(d.recommendation.rationale,recommendation,'explanation');
  const reasons=el('div','reason-links',null,recommendation); link('Inspect pilot findings ↗','#pilot',reasons); link('Inspect source evidence ↗','#claims',reasons); link('See remaining questions ↗','#questions',reasons);
  const status=el('div','inline-status',null,recommendation); pill(d.review.approval.status.replaceAll('_',' '),status,'pending'); pill(d.investigation.decision===null?'Decision: not set':String(d.investigation.decision),status,'neutral');

  const pilot=el('div','card',null,evidence); pilot.id='pilot'; label('Measured results · Synthetic extraction pilot',pilot);
  el('h3','','A small pilot, with inspectable outcomes',pilot);
  const a=d.aggregate, stats=el('div','stats',null,pilot);
  [[metric(a.attempted_cases),'Cases attempted'],[`${metric(a.schema_valid_cases)} / ${metric(a.attempted_cases)}`,'Schema-valid outputs'],[`${metric(a.quality_pass_cases)} / ${metric(a.attempted_cases)}`,'Passed saved quality checks'],[`${metric(a.request_seconds)} s`,'Summed request time']].forEach(([v,k])=>{const s=el('div','stat',null,stats);el('strong','',v,s);el('small','',k,s);});
  paragraph(`${metric(a.reported_total_tokens)} reported tokens · ${a.actual_model}`,pilot,'meta');
  paragraph('These local checks are diagnostic, not a production accuracy estimate or a comparison with the current application. Valid JSON alone does not establish correct extraction.',pilot,'explanation');
  d.cases.forEach(c=>{
    const b=details(c.label,pilot,`case-${c.fixture_id}`); const summary=b.parentElement.querySelector('summary');
    el('span','case-status',c.validation.quality_pass?'Passed saved checks':'Needs review',summary);
    pill('Synthetic input · Not real user data',b,'neutral'); el('div','text-input',c.input,b);
    comparison(c,b);
    el('h4','','Recorded evaluation finding',b); paragraph(c.finding,b);
    el('h4','','Original model output',b); json(c.output,b);
    el('h4','','Original evaluator findings',b); json(c.validation,b);
    paragraph(`${metric(c.duration_seconds)} s · ${metric(c.token_usage?.total_tokens)} tokens · ${c.actual_model}`,b,'meta');
  });
  const limits=details('How to interpret these results',pilot,'evaluator-limitations'); list(d.recommendation.evaluator_limitations,limits);

  const claims=el('div','card',null,evidence); claims.id='claims'; label('Publisher claims · Background and limitations',claims);
  el('h3','','What the sources do — and do not — support',claims);
  paragraph('Exact quotation matching connects a claim to a saved excerpt. It does not verify the claim as fact, establish independence, or grant human approval.',claims,'explanation');
  d.claims.forEach(c=>{
    const index=c.claim_pointer.split('/').pop(), item=el('article','claim-item',null,claims);
    const wording=el('div','claim-wording',null,item), draft=el('div','',null,wording), review=el('div','review-qualification',null,wording);
    pill('Original draft · Publisher claim',draft,'neutral');paragraph(c.claim,draft,'original-claim');
    pill('Proposed review correction · Pending approval',review,'pending');paragraph(c.review.proposed_wording,review,'proposed-correction');
    paragraph(c.review.correction_reason,review,'meta');
    const b=details('Inspect exact quotation, limitations and review basis',item,`claim-${index}`);
    paragraph(`Original criterion: ${d.investigation.evaluation_criteria.find(x=>x.id===c.relevance_to_criterion)?.name || c.relevance_to_criterion}`,b,'meta');
    el('h4','','Exact supporting quotation',b); el('blockquote','',c.exact_supporting_quote,b);
    const source=d.sources.find(s=>s.id===c.source_id); link(`Open source: ${source.publisher_domain}`,source.requested_url,b);
    el('h4','','Original limitation',b); paragraph(c.limitations,b);
    el('h4','','AI-assisted review · Correction not applied to the draft',b);
    paragraph(c.review.quote_support_assessment,b); list(c.review.limitations,b);
    paragraph(`Review basis: ${c.review.review_basis}`,b,'meta');
  });

  const questions=el('div','card',null,evidence); questions.id='questions'; label('Still unknown',questions); el('h3','','Questions before another test',questions);
  list(d.recommendation.remaining_unknowns,questions); el('h4','','Open investigation questions',questions); list(d.investigation.open_questions,questions);
  const gaps=details(`Earlier evidence review · ${date(d.review.created_at_utc)}`,questions,'review-history');
  paragraph('This review predates the completed pilot. Its original gaps and proposed actions are preserved; they have not been silently updated or approved.',gaps,'notice');
  d.review.unresolved_evidence_gaps.forEach(g=>{el('h4','',g.unknown,gaps);paragraph(g.concrete_next_action,gaps);});
  const diag=details('Data provenance & technical diagnostics',content,'diagnostics','diagnostics');
  paragraph('H-MEM retrieves exact persisted artifacts; Zetaris supplies live table rows and SQL aggregates. Hash checks establish artifact identity, not truth or approval.',diag);
  json(d.diagnostics,diag);
  el('h4','','Separate workload: Nextwise source analysis',diag); paragraph('These source-analysis measurements are excluded from every extraction-pilot figure above.',diag); json(d.analysis_observation,diag);
  content.hidden=false; state.hidden=true; $('#connection').textContent='● Live data · Memory linked'; $('#disconnect').hidden=false;
  const observer=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.hash===`#${e.target.id}`));}});},{rootMargin:'-10% 0px -65% 0px'});
  document.querySelectorAll('.section').forEach(s=>observer.observe(s));
  if(location.hash) requestAnimationFrame(openHash);
}
function showState(code,message) {
  parkDecisionPanel();decisionContext=null;paintDecisionPanel();
  content.hidden=true; content.replaceChildren(); state.hidden=false; state.replaceChildren(); state.className=`state ${code==='loading'?'loading':'error'}`;
  const titles={authentication:'Connect your investigation',loading:'Retrieving your investigation',empty:'No investigation data yet',memory:'Investigation memory unavailable',integrity:'The evidence could not be linked safely',zetaris:'Live data is unavailable',service:'Unable to load this investigation',network:'Cannot reach the local app'};
  el('h2','',titles[code]||'Unable to continue',state); paragraph(message,state);
  if(code==='authentication') {
    paragraph('The masked key is entered only in the PowerShell window running Nextwise. It is never stored in this browser, a URL, or a file.',state,'muted');
    const b=el('button','button','I entered the key · Connect',state);b.onclick=load;
  } else if(code!=='loading') { const b=el('button','button','Try again',state);b.onclick=load; }
  if(code!=='loading') $('#connection').textContent=code==='authentication'?'Not connected':'Connection needs attention';
}
async function load() {
  if(loading||decisionSaving)return; loading=true; refresh.disabled=true;
  while(discoveryReading)await new Promise(resolve=>setTimeout(resolve,100));
  showState('loading','Reading live Zetaris tables, retrieving persisted H-MEM artifacts, and checking investigation identity and evidence links. This may take a moment.');
  try {
    // A previous document's history read can briefly hold the server lock after
    // reload. Retry only that explicit busy response; decision writes never retry here.
    for(let attempt=0;attempt<10;attempt++){
      const response=await fetch('/api/load',{method:'POST',credentials:'same-origin'}),d=await response.json();
      if(response.status===409&&d.code==='loading'){
        if(attempt===9){showState('service','Another local request is still finishing. Wait a moment and try again.');break;}
        await new Promise(resolve=>setTimeout(resolve,1000));continue;
      }
      if(!response.ok)showState(d.code,d.message);else render(d);
      break;
    }
  }
  catch(_){showState('network','Check that the local Nextwise server is still running, then retry. No cached report is displayed.');}
  finally{loading=false;await readDecisions();refresh.disabled=false;readDiscovery();}
}
refresh.onclick=load;
$('#disconnect').onclick=async()=>{if(loading||decisionSaving)return;try{const r=await fetch('/api/disconnect',{method:'POST'});if(!r.ok)return;$('#disconnect').hidden=true;showState('authentication','The server has released the key. Enter a key in the private console to reconnect.');}catch(_){showState('network','The local server is unavailable.');}};
fetch('/api/status').then(r=>r.json()).then(d=>{if(d.authenticated)load();else {showState('authentication','Your local app is ready. Enter the Zetaris API key at the hidden prompt in PowerShell, then connect here.');readDecisions().finally(readDiscovery);}}).catch(()=>{showState('network','Start the local Nextwise server and reload this page.');readDecisions().finally(readDiscovery);});
