'use strict';
const $ = s => document.querySelector(s);
const content = $('#content'), state = $('#state'), refresh = $('#refresh');
let loading = false;
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
  content.replaceChildren();
  const brief=el('div','card investigation-brief',null,content);brief.id='investigation-brief';
  label('Current investigation',brief);el('h2','brief-question',d.investigation.question,brief);
  const next=el('div','brief-next',null,brief);label('Existing proposed next action',next);
  paragraph(recommendationSummary(d.recommendation),next,'next-summary');
  const briefStatus=el('div','inline-status',null,next);pill('AI-assisted proposal · Pending approval',briefStatus,'pending');
  pill(d.investigation.decision===null?'Decision: not set':String(d.investigation.decision),briefStatus,'neutral');
  const original=details('Read the full original recommendation',next,'original-recommendation');
  paragraph(d.recommendation.recommended_next_step,original);paragraph(d.recommendation.rationale,original,'explanation');
  const earlyLinks=el('div','reason-links',null,next);link('Inspect pilot findings ↗','#pilot',earlyLinks);link('Read qualified publisher claims ↗','#claims',earlyLinks);
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
  if(loading)return; loading=true; refresh.disabled=true;
  showState('loading','Reading live Zetaris tables, retrieving persisted H-MEM artifacts, and checking investigation identity and evidence links. This may take a moment.');
  try { const response=await fetch('/api/load',{method:'POST',credentials:'same-origin'});const d=await response.json(); if(!response.ok)showState(d.code,d.message);else render(d); }
  catch(_){showState('network','Check that the local Nextwise server is still running, then retry. No cached report is displayed.');}
  finally{loading=false;refresh.disabled=false;}
}
refresh.onclick=load;
$('#disconnect').onclick=async()=>{if(loading)return;try{const r=await fetch('/api/disconnect',{method:'POST'});if(!r.ok)return;$('#disconnect').hidden=true;showState('authentication','The server has released the key. Enter a key in the private console to reconnect.');}catch(_){showState('network','The local server is unavailable.');}};
fetch('/api/status').then(r=>r.json()).then(d=>{if(d.authenticated)load();else showState('authentication','Your local app is ready. Enter the Zetaris API key at the hidden prompt in PowerShell, then connect here.');}).catch(()=>showState('network','Start the local Nextwise server and reload this page.'));
