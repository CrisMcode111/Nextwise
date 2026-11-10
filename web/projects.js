'use strict';
const q = selector => document.querySelector(selector);
let project = null, transports = {}, busy = false, savedProjects = [];
let createId = crypto.randomUUID();
const decisionDrafts = new Map();
function node(tag, text, parent, className = '') {
  const n = document.createElement(tag); n.textContent = text; n.className = className; parent.append(n); return n;
}
function dateLabel(value) {
  if (!value || Number.isNaN(new Date(value).getTime())) return 'Date not recorded';
  return new Date(value).toLocaleString(undefined, {dateStyle:'medium', timeStyle:'short'});
}
function badge(text, parent, state = 'neutral') { return node('span', text, parent, 'tag ' + state); }
function detail(title, parent) { const d = node('details', '', parent, 'technical-details'); node('summary', title, d); return d; }
function sourceLink(title, url, parent) {
  try { const parsed = new URL(url); if (!['http:', 'https:'].includes(parsed.protocol)) return; }
  catch (_) { return; }
  const a = node('a', title, parent); a.href = url; a.rel = 'noopener noreferrer'; a.target = '_blank'; return a;
}
function status(text, state) { q('#status').textContent = text; q('#status').setAttribute('data-state', state); }
async function api(path, body) {
  const response = await fetch(path, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || 'Operation failed. Reopen saved history before retrying.');
  return result;
}
async function action(work, pending = 'Loading saved records...', completed = 'Saved records loaded.') {
  if (busy) return;
  busy = true; status(pending, 'pending'); q('#workspace-body').inert = true; q('#workspace').setAttribute('aria-busy', 'true');
  try { const result = await work(); status(result === false ? 'Action cancelled. No request was sent.' : completed, result === false ? 'neutral' : 'completed'); }
  catch (error) { status(error.message, 'failed'); }
  finally { busy = false; q('#workspace-body').inert = false; q('#workspace').setAttribute('aria-busy', 'false'); }
}
function paintProjectSelector() {
  q('#projects').replaceChildren(); q('#projects-empty').hidden = savedProjects.length > 0;
  for (const p of savedProjects) {
    const b = node('button', '', q('#projects'), 'project-option'); b.type = 'button';
    b.setAttribute('aria-pressed', String(p.id === project?.project.id));
    node('span', p.name, b, 'project-option-name'); node('span', 'Open saved project', b, 'project-option-hint');
    b.onclick = () => action(() => openProject(p.id));
  }
}
async function listProjects() {
  const result = await api('/api/projects'); transports = result.transports; savedProjects = result.projects;
  paintProjectSelector(); q('#create-panel').open = savedProjects.length === 0;
}
async function openProject(id) { project = await api('/api/projects/' + id); render(); paintProjectSelector(); }
async function mutate(stage, fields) {
  if (stage === 'discover' || stage === 'assess') {
    const disclosure = stage === 'discover'
      ? 'Send these reviewed public search terms to Tavily and fetch up to four public pages? This uses one search attempt and may consume credits.'
      : 'Send this project brief and saved public evidence to Meterless for one assessment? It may use a paid model provider. This uses one assessment attempt.';
    if (!window.confirm(disclosure)) return false;
    fields = {...fields, authorize_external_request:true};
  }
  const result = await api(`/api/projects/${project.project.id}/${stage}`, {
    request_id:crypto.randomUUID(), expected_version:project.version, ...fields});
  project = await api('/api/projects/' + result.project.id); render();
  return true;
}
function renderSource(item) {
  const row = node('article', '', q('#sources'), 'card source-card');
  const top = node('div', '', row, 'card-kicker'); badge('Saved source', top, 'completed');
  const latest = project.assessments.filter(a => a.candidate_id === item.id).at(-1);
  badge(latest ? 'Saved validated assessment' : 'Not yet validated', top, latest ? 'completed' : 'neutral');
  node('h3', item.title, row); sourceLink('Open publisher source', item.url, row);
  node('p', 'Saved ' + dateLabel(item.retrieved_at), row, 'source-date');
  const controls = node('div', '', row, 'card-actions');
  const assess = node('button', 'Assess against my project', controls, 'button quiet'); assess.type = 'button'; assess.disabled = !transports.assessment;
  assess.onclick = () => action(() => mutate('assess', {candidate_id:item.id,
    context_candidate_ids:Object.keys(project.items).filter(id => id !== item.id).sort()}), 'Requesting an authorized assessment...', 'Assessment validated and saved.');
  if (!transports.assessment) node('p', 'Assessment unavailable in this instance. Saved records remain readable.', row, 'availability-note');
  if (latest) {
    const brief = node('button', 'Prepare validated briefing', controls, 'button quiet'); brief.type = 'button';
    brief.onclick = () => action(() => mutate('brief', {assessment_id:latest.id}), 'Preparing briefing from saved assessment...', 'Validated briefing saved.');
  }
  const provenance = detail('Source provenance', row);
  node('pre', JSON.stringify(item, null, 2), provenance);
}
function renderDecision(brief, row) {
  const head = project.decisions.filter(d => d.candidate_id === brief.candidate_id).at(-1);
  const attached = project.decisions.filter(d => d.briefing_id === brief.id).at(-1);
  const panel = node('section', '', row, 'human-decision-panel');
  node('p', 'YOUR DECISION', panel, 'eyebrow');
  if (attached) {
    node('h4', `Human decision Version ${attached.version}: ${attached.choice}`, panel);
    node('p', attached.rationale, panel, 'human-rationale');
    node('p', 'Saved ' + dateLabel(attached.created_at), panel, 'decision-date');
    if (attached.next_action) node('p', attached.next_action, panel, 'human-rationale');
  } else {
    node('h4', 'Awaiting your decision', panel);
    if (head) node('p', `The latest human decision (Version ${head.version}) belongs to another briefing. This briefing is awaiting your decision.`, panel);
    else node('p', 'No human decision has been saved for this briefing.', panel);
  }
  node('p', 'Your choice is recorded separately. Saving it starts no research, spending, model call or implementation.', panel, 'decision-boundary');
  const latest = project.briefings.filter(b => b.candidate_id === brief.candidate_id).at(-1);
  if (!project.briefing_current[brief.id] || latest.id !== brief.id) {
    node('p', 'Historical briefing. Reassess current evidence before deciding.', panel, 'notice'); return;
  }
  const editor = detail(attached ? 'Amend your decision' : 'Record your decision', panel); editor.open = !attached;
  const form = node('form', '', editor, 'project-decision-form');
  const draft = decisionDrafts.get(brief.id) || {choice:'', rationale:''}; decisionDrafts.set(brief.id, draft);
  const id = 'decision-' + brief.id;
  const label = node('label', 'Your choice', form); label.htmlFor = id;
  const select = node('select', '', form); select.id = id; select.setAttribute('aria-label', 'Your decision');
  for (const choice of ['', 'Adopt','Test','Defer','Reject']) { const option = node('option', choice || 'Choose your decision', select); option.value = choice; }
  select.value = draft.choice; select.required = true; select.onchange = () => { draft.choice = select.value; };
  const rationaleLabel = node('label', 'Why is this the right next step?', form); rationaleLabel.htmlFor = id + '-rationale';
  const rationale = node('textarea', '', form); rationale.id = id + '-rationale'; rationale.value = draft.rationale;
  rationale.rows = 4; rationale.required = true; rationale.maxLength = 8000; rationale.setAttribute('aria-label', 'Your decision rationale');
  rationale.oninput = () => { draft.rationale = rationale.value; };
  const save = node('button', attached ? 'Save amended decision' : 'Save my decision', form, 'button'); save.type = 'submit';
  form.onsubmit = event => { event.preventDefault(); action(async () => {
    await mutate('decide', {explicit_action:'record_project_decision', briefing_id:brief.id,
      briefing_sha256:brief.record_sha256, expected_head:head?.id || null, choice:select.value, rationale:rationale.value});
    decisionDrafts.delete(brief.id); render();
  }, 'Saving your decision...', 'Your decision and rationale are saved.'); };
}
// Presentation boundary only: consume the existing validated category/current
// flags. Never classify a source, infer relevance, or create an opportunity.
function isOpportunityBriefing(brief) {
  const record = project.assessments.find(a => a.id === brief.assessment_id);
  const latestBrief = project.briefings.filter(b => b.candidate_id === brief.candidate_id).at(-1);
  const latestAssessment = project.assessments.filter(a => a.candidate_id === brief.candidate_id).at(-1);
  return project.briefing_current[brief.id] === true && latestBrief?.id === brief.id
    && latestAssessment?.id === record?.id && record?.assessment.category === 'potential relevance';
}
function renderOpportunity(brief) {
  const row = node('article', '', q('#opportunities'), 'card selected-opportunity');
  const top = node('div', '', row, 'card-kicker'); badge('Potential relevance', top, 'completed');
  badge('Domain not recorded', top, 'neutral');
  node('h3', brief.title, row);
  const connection = node('section', '', row); node('h4', 'Connection to your project', connection); node('p', brief.why_it_matters, connection);
  const improvement = node('section', '', row); node('h4', 'Potential improvement', improvement); node('p', brief.potential_value, improvement);
  const next = node('section', '', row, 'opportunity-next'); node('h4', 'Suggested next action', next); node('p', brief.next_action, next);
  node('p', 'A plausible application, not a verified benefit. Your decision remains separate.', row, 'availability-note');
  const decision = project.decisions.filter(d => d.briefing_id === brief.id).at(-1);
  if (decision) badge('Human decision: ' + decision.choice, row, 'neutral');
  const full = detail('Evidence, reasoning & your decision', row);
  renderBriefing(brief, full);
}
function renderBriefing(brief, parent = q('#briefings')) {
  const row = node('article', '', parent, 'card project-briefing');
  const assessment = project.assessments.find(a => a.id === brief.assessment_id)?.assessment;
  const current = project.briefing_current[brief.id];
  const top = node('div', '', row, 'card-kicker'); badge(current ? 'Validated evaluation' : 'Historical evaluation', top, 'neutral');
  if (assessment?.category) badge(assessment.category, top, 'neutral');
  const ai = node('section', '', row, 'ai-recommendation');
  node('p', 'SAVED EVALUATION OUTCOME', ai, 'eyebrow'); node('h4', brief.recommended_choice, ai);
  node('p', 'Provisional guidance, separate from your saved human decision.', ai, 'recommendation-boundary');
  node('h3', brief.title, row, 'briefing-source-title');
  node('p', brief.label, row, 'briefing-disclaimer');
  const reasoning = node('section', '', row, 'briefing-reasoning');
  if (assessment?.priority_reason) {
    node('h4', 'Saved assessment reasoning', reasoning); node('p', assessment.priority_reason, reasoning, 'copy');
  }
  node('h4', 'Connection to your project', reasoning); node('p', brief.why_it_matters, reasoning, 'briefing-connection');
  if (brief.potential_value) { node('h4', 'Possible application', row, 'briefing-subheading'); node('p', brief.potential_value, row, 'copy'); }
  else node('p', 'No application hypothesis is established by this assessment.', row, 'hypothesis-note');
  const gaps = node('section', '', row, 'project-gaps'); node('h4', 'What remains uncertain', gaps);
  const list = node('ul', '', gaps);
  for (const text of [...new Set([...brief.risks, ...brief.uncertainty])]) node('li', text, list);
  if (assessment?.investigation_question) {
    node('h4', 'Question to resolve', gaps); node('p', assessment.investigation_question, gaps, 'saved-question');
  }
  const next = node('section', '', row, 'project-next-step'); node('h4', 'Next step to consider', next); node('p', brief.next_action, next);
  const evidence = detail(`Supporting quotations (${brief.supporting_evidence.length})`, row);
  node('p', 'Exact saved publisher quotations. Textual grounding does not establish truth or suitability.', evidence, 'copy');
  if (brief.evidence_references?.url) sourceLink('Primary publisher source', brief.evidence_references.url, evidence);
  for (const quote of brief.supporting_evidence) { node('blockquote', quote.exact_quote, evidence); node('p', 'Passage ' + quote.passage_id, evidence, 'source-date'); }
  if (brief.context_evidence_references?.length) {
    node('h4', 'Additional saved context', evidence);
    node('p', 'These pages supplied context. The supporting quotations above come from the primary source.', evidence, 'copy');
    for (const source of brief.context_evidence_references) { const p = node('p', '', evidence); sourceLink(source.title, source.url, p); }
  }
  const observation = detail('Saved publisher observation & provenance', row);
  node('p', brief.what_changed, observation, 'saved-observation');
  node('pre', JSON.stringify({briefing_id:brief.id, assessment_id:brief.assessment_id, record_sha256:brief.record_sha256,
    created_at:brief.created_at, current, assessment_validation:project.assessments.find(a => a.id === brief.assessment_id)?.validation}, null, 2), observation);
  renderDecision(brief, row);
}
function renderUnbriefedAssessment(record) {
  const value = record.assessment;
  const row = node('article', '', q('#briefings'), 'card unbriefed-evaluation');
  badge(value.category, row, 'neutral');
  node('h3', project.items[record.candidate_id]?.title || 'Saved assessment', row);
  node('p', 'Assessment saved; no briefing is attached to this version.', row, 'copy');
  node('h4', 'Project connection', row); node('p', value.project_need, row, 'copy');
  node('h4', 'Saved reasoning', row); node('p', value.priority_reason, row, 'copy');
  const evidence = detail('Saved quotations & assessment record', row);
  for (const quote of value.evidence) node('blockquote', quote.exact_quote, evidence);
  node('pre', JSON.stringify(record, null, 2), evidence);
}
function renderHistory() {
  const timeline = q('#history'); timeline.replaceChildren();
  const operations = Object.values(project.operations);
  const summary = [(operations.length + 1) + ' saved events'];
  const completed = operations.filter(op => op.status === 'completed').length + 1;
  summary.push(completed + ' completed');
  for (const [state, label] of [['failed', 'failed'], ['started', 'pending']]) {
    const count = operations.filter(op => op.status === state).length;
    if (count) summary.push(count + ' ' + label);
  }
  q('#history-summary').textContent = summary.join(' \u00b7 ');
  const entry = (title, state, when, copy) => {
    const item = node('li', '', timeline, 'timeline-event'); const heading = node('div', '', item, 'timeline-heading');
    node('h3', title, heading); badge(state === 'started' ? 'Pending' : state === 'completed' ? 'Completed' : state === 'failed' ? 'Failed' : state, heading, state === 'started' ? 'pending' : state);
    if (when) node('p', dateLabel(when), item, 'timeline-date');
    if (copy) node('p', copy, item, 'timeline-copy');
  };
  entry('Project created', 'completed', project.project.created_at, project.project.name);
  const names = {discover:'Evidence discovery', assess:'AI assessment', brief:'Validated briefing', decide:'Human decision'};
  for (const [id, op] of Object.entries(project.operations)) {
    const record = [...(project.runs || []), ...project.assessments, ...project.briefings, ...project.decisions].find(r => r.id === id);
    let copy = op.status === 'failed' ? 'This action did not complete. Reload saved history before considering another attempt.' : '';
    if (op.action === 'decide' && record) copy = `${record.choice}: ${record.rationale}`;
    if (op.action === 'assess' && record) copy = `Validated assessment: ${record.assessment.category}.`;
    if (op.action === 'brief' && record) copy = `Provisional recommendation: ${record.recommended_choice}. Human review remains separate.`;
    entry(names[op.action] || op.action, op.status, record?.created_at, copy);
  }
  q('#history-details').textContent = JSON.stringify({operations:project.operations, decisions:project.decisions}, null, 2);
}
function render() {
  q('#workspace-empty').hidden = true; q('#project-content').hidden = false;
  q('#project-name').textContent = project.project.name; q('#project-brief').textContent = project.project.brief;
  q('#project-overview').textContent = project.project.brief.length > 220
    ? project.project.brief.slice(0, 220).replace(/\s+\S*$/, '') + '\u2026' : project.project.brief;
  q('#discover button').disabled = !transports.search;
  q('#transport-note').textContent = transports.search && transports.assessment
    ? 'Available on explicit request: evidence discovery and AI assessment. Nothing runs automatically.'
    : transports.assessment ? 'Assessments are available on explicit request. New discovery is unavailable in this instance.'
      : transports.search ? 'Evidence discovery is available on explicit request. AI assessment is unavailable in this instance.'
        : 'External actions unavailable: search and assessment are disabled. Saved evidence, briefings and human decisions remain available.';
  q('#transport-note').setAttribute('data-state', transports.search || transports.assessment ? 'neutral' : 'unavailable');
  const opportunities = project.briefings.filter(isOpportunityBriefing);
  const previous = project.briefings.filter(b => !isOpportunityBriefing(b));
  const unbriefed = project.assessments.filter(a => !project.briefings.some(b => b.assessment_id === a.id));
  q('#project-counts').replaceChildren();
  for (const [count, singular, plural] of [[opportunities.length,'opportunity','opportunities'],[Object.keys(project.items).length,'saved source','saved sources'],[project.decisions.length,'saved decision','saved decisions']]) {
    const item = node('div', '', q('#project-counts')); node('strong', String(count), item); node('span', count === 1 ? singular : plural, item);
  }
  q('#source-count').textContent = Object.keys(project.items).length + ' saved';
  q('#opportunity-count').textContent = opportunities.length + ' to explore';
  q('#briefing-count').textContent = (previous.length + unbriefed.length) + ' saved';
  q('#opportunities').replaceChildren(); q('#opportunity-empty').hidden = opportunities.length > 0;
  q('#sources').replaceChildren(); q('#briefings').replaceChildren();
  if (!Object.keys(project.items).length) node('p', 'No evidence saved yet. Discovery is available only when enabled and explicitly authorized.', q('#sources'), 'card empty-note');
  for (const item of Object.values(project.items)) renderSource(item);
  if (!previous.length && !unbriefed.length) node('p', 'No previous evaluations to show.', q('#briefings'), 'empty-note');
  for (const brief of opportunities) renderOpportunity(brief);
  for (const brief of previous) renderBriefing(brief);
  for (const record of unbriefed) renderUnbriefedAssessment(record);
  renderHistory();
}
q('#create-project').onsubmit = event => { event.preventDefault(); action(async () => {
  const form = event.target, result = await api('/api/projects', {request_id:createId, name:form.elements.name.value,
    brief:form.elements.brief.value, reviewed_sanitized:form.elements.reviewed.checked});
  createId = crypto.randomUUID(); await listProjects(); await openProject(result.project.id);
}, 'Saving your reviewed project...', 'Project saved. No search or assessment was started.'); };
q('#create-project').oninput = () => { createId = crypto.randomUUID(); };
q('#discover').onsubmit = event => { event.preventDefault(); action(() => mutate('discover', {query:event.target.elements.query.value}), 'Requesting authorized evidence discovery...', 'Evidence discovery completed and saved.'); };
q('#reopen').onclick = () => action(() => openProject(project.project.id));
function openSavedSection(id) {
  const panel = q(id); panel.open = true;
  panel.querySelector('summary').focus();
  panel.scrollIntoView({block:'start', behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
}
q('#review-evidence').onclick = () => openSavedSection('#saved-evidence');
q('#review-evaluations').onclick = () => openSavedSection('#previous-evaluations');
action(async () => { await listProjects(); if (savedProjects.length === 1) await openProject(savedProjects[0].id); });
// Ambient sculpture: no project data, requests, or application-state dependencies.
(() => {
  const canvas = document.querySelector('#intelligence-field');
  if (!canvas || typeof canvas.getContext !== 'function') return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  canvas.parentElement.classList.add('field-ready');
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let width = 0, height = 0, frame = 0, previous = 0, time = 0, visible = true;
  let seed = 74193;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  // A folded, open membrane, rather than nodes joined by proximity or orbital paths.
  const threads = Array.from({length:76}, (_, i) => ({v:i / 75, phase:random()*6.28, weight:.35+random()*.5}));
  const motes = Array.from({length:29}, () => ({x:random(),y:random(),phase:random()*6.28,speed:.025+random()*.035}));
  const bridges = Array.from({length:3}, (_, i) => ({from:.12+random()*.25,to:.61+random()*.28,birth:-i*8,life:15+random()*12}));
  function point(u, v, t) {
    u = .035 + .93*u + .035*Math.sin(v*7.1+1.2)*(1-2*u);
    const envelope = .18+.82*Math.pow(Math.sin(Math.PI*u),.5);
    const fold = Math.sin(v*5.8+u*3.4+t*.075);
    const wave = Math.sin(u*8.2-v*3.7-t*.16)*Math.sin(Math.PI*u);
    return [width*(.06+.87*u+.045*Math.sin(v*6.1+t*.047)*Math.sin(Math.PI*u)),
      height*(.51+(v-.5)*(.16+.65*Math.pow(Math.abs(u-.49)*2, .7))*envelope+
        .21*Math.sin(u*6.3+v*2.7+t*.06)*Math.sin(Math.PI*u)+.06*fold+.025*wave)];
  }
  function draw(t) {
    ctx.clearRect(0,0,width,height);
    const core = [width*.485,height*.515];
    const aura = ctx.createRadialGradient(...core,0,...core,width*.4);
    aura.addColorStop(0,'rgba(224,207,157,.105)'); aura.addColorStop(.3,'rgba(126,172,135,.055)'); aura.addColorStop(1,'rgba(126,172,135,0)');
    ctx.fillStyle=aura;ctx.fillRect(0,0,width,height);
    threads.forEach(({v,phase,weight}, i) => {
      const selected = Math.pow(Math.max(0, Math.sin(t*.17+phase)),18);
      ctx.beginPath();
      for(let j=0;j<=42;j++) {
        const u=j/42, p=point(u,v,t);
        if(j===0)ctx.moveTo(...p);else ctx.lineTo(...p);
      }
      ctx.strokeStyle=i%4===0 ? `rgba(140,186,156,${.09+selected*.13})` : `rgba(222,202,158,${.10+selected*.25})`;
      ctx.lineWidth=weight;ctx.stroke();
    });
    // Rare cross-fold connections grow, persist and dissolve at independent intervals.
    bridges.forEach(b => {
      if(t-b.birth>b.life){b.birth=t;b.life=17+random()*18;b.from=.08+random()*.35;b.to=.6+random()*.3;}
      const age=Math.max(0,(t-b.birth)/b.life), light=Math.pow(Math.sin(Math.PI*Math.min(1,age)),3);
      const a=point(b.from,.15,t), z=point(b.to,.85,t);
      ctx.beginPath();ctx.moveTo(...a);ctx.bezierCurveTo(width*.36,height*.04,width*.66,height*.94,...z);
      ctx.strokeStyle=`rgba(232,214,175,${light*.34})`;ctx.lineWidth=.65;ctx.stroke();
    });
    // A second veil interrupts the main fold, creating depth and asymmetric tension.
    for(let i=0;i<16;i++) {
      const v=i/15;ctx.beginPath();
      ctx.moveTo(width*(.16+v*.16),height*(.20+v*.11));
      ctx.bezierCurveTo(width*(.75-v*.2),height*(.06+v*.18),width*(.19+v*.18),height*(.85-v*.19),width*(.86-v*.13),height*(.68+v*.08));
      ctx.strokeStyle=`rgba(200,185,145,${.045+Math.sin(t*.09+v*2)*.018})`;ctx.lineWidth=.45;ctx.stroke();
    }
    motes.forEach(m => {
      const x=width*(.07+m.x*.86+.015*Math.sin(t*m.speed+m.phase));
      const y=height*(.12+m.y*.75+.022*Math.sin(t*m.speed*.71+m.phase*2));
      ctx.beginPath();ctx.arc(x,y,.45+.45*m.x,0,Math.PI*2);
      ctx.fillStyle=`rgba(231,215,176,${.18+.32*(.5+.5*Math.sin(t*.11+m.phase))})`;ctx.fill();
    });
    const glow=ctx.createRadialGradient(...core,0,...core,22);
    glow.addColorStop(0,'rgba(247,232,195,.8)');glow.addColorStop(.12,'rgba(232,210,161,.32)');glow.addColorStop(1,'rgba(232,210,161,0)');
    ctx.fillStyle=glow;ctx.fillRect(core[0]-22,core[1]-22,44,44);
    ctx.save();ctx.translate(...core);ctx.rotate(-.38);ctx.beginPath();ctx.ellipse(0,0,2.3,4.8,0,0,Math.PI*2);ctx.fillStyle='#f3e6c5';ctx.fill();ctx.restore();
  }
  function tick(now) {
    frame=0;
    if(document.hidden || !visible || motion.matches)return;
    if(now-previous>=1000/30){time+=Math.min((now-previous)/1000,.06);previous=now;draw(time);}
    frame=requestAnimationFrame(tick);
  }
  function sync() {
    cancelAnimationFrame(frame);frame=0;previous=performance.now();
    if(motion.matches)draw(0);
    else if(visible && !document.hidden)frame=requestAnimationFrame(tick);
  }
  function resize() {
    const bounds=canvas.getBoundingClientRect(), ratio=Math.min(window.devicePixelRatio||1,1.5);
    width=bounds.width;height=bounds.height;
    canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    ctx.setTransform(ratio,0,0,ratio,0,0);draw(motion.matches?0:time);sync();
  }
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver(entries => {visible=entries[0].isIntersecting;sync();}).observe(canvas);
  document.addEventListener('visibilitychange',sync);
  motion.addEventListener('change',sync);
  resize();
})();
