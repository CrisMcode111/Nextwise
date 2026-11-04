'use strict';
const q = selector => document.querySelector(selector);
let project = null, transports = {}, busy = false;
let createId = crypto.randomUUID();
function node(tag, text, parent) {
  const n = document.createElement(tag); n.textContent = text; parent.append(n); return n;
}
async function api(path, body) {
  const response = await fetch(path, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {});
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || 'Operation failed. Reopen saved history before retrying.');
  return result;
}
async function action(work) {
  if (busy) return; busy = true; q('#status').textContent = 'Working…';
  try { await work(); q('#status').textContent = 'Saved records confirmed.'; }
  catch (error) { q('#status').textContent = error.message; }
  finally { busy = false; }
}
async function listProjects() {
  const result = await api('/api/projects'); transports = result.transports;
  q('#projects').replaceChildren();
  for (const p of result.projects) {
    const b = node('button', p.name, q('#projects')); b.className = 'button quiet';
    b.onclick = () => action(() => openProject(p.id));
  }
}
async function openProject(id) { project = await api('/api/projects/' + id); render(); }
async function mutate(stage, fields) {
  if (stage === 'discover' || stage === 'assess') {
    const disclosure = stage === 'discover'
      ? 'Send these reviewed public search terms to Tavily and fetch up to four public pages? This uses one search attempt and may consume credits.'
      : 'Send this project brief and saved public evidence to Meterless for one assessment? It may use a paid model provider. This uses one assessment attempt.';
    if (!window.confirm(disclosure)) return;
    fields = {...fields, authorize_external_request:true};
  }
  const result = await api(`/api/projects/${project.project.id}/${stage}`, {
    request_id:crypto.randomUUID(), expected_version:project.version, ...fields});
  project = await api('/api/projects/' + result.project.id); render();
}
function render() {
  q('#workspace').hidden = false;
  q('#project-name').textContent = project.project.name;
  q('#project-brief').textContent = project.project.brief;
  q('#discover button').disabled = !transports.search;
  q('#transport-note').textContent = transports.search && transports.assessment
    ? 'Evidence and assessments are requested only by your explicit actions.'
    : 'Search or assessment is not enabled in this instance. Saved evidence and human decisions remain available.';
  q('#sources').replaceChildren(); q('#briefings').replaceChildren();
  for (const item of Object.values(project.items)) {
    const row = node('article', '', q('#sources')); row.className = 'card';
    node('h3', item.title, row); const link = node('a', 'Publisher source', row); link.href = item.url; link.rel = 'noreferrer';
    node('p', 'Saved ' + item.retrieved_at + '. Publisher statements are evidence of a claim, not proof of suitability.', row);
    const assess = node('button', 'Assess against my project', row); assess.disabled = !transports.assessment;
    assess.onclick = () => action(() => mutate('assess', {candidate_id:item.id}));
    const latest = project.assessments.filter(a => a.candidate_id === item.id).at(-1);
    if (latest) {
      const brief = node('button', 'Prepare validated briefing', row);
      brief.onclick = () => action(() => mutate('brief', {assessment_id:latest.id}));
    }
  }
  for (const brief of project.briefings) {
    const row = node('article', '', q('#briefings')); row.className = 'card';
    node('h3', brief.title, row); node('p', brief.label, row);
    for (const field of ['what_changed','why_it_matters','potential_value','next_action']) if (brief[field]) node('p', brief[field], row);
    node('p', 'Provisional recommendation: ' + brief.recommended_choice, row);
    for (const text of [...brief.risks,...brief.uncertainty]) node('p', text, row);
    for (const evidence of brief.supporting_evidence) node('blockquote', evidence.exact_quote, row);
    const head = project.decisions.filter(d => d.candidate_id === brief.candidate_id).at(-1);
    const attached = project.decisions.filter(d => d.briefing_id === brief.id).at(-1);
    if (attached) node('p', `Human decision Version ${attached.version}: ${attached.choice}. ${attached.rationale}`, row);
    else if (head) node('p', `The latest human decision (Version ${head.version}) belongs to another briefing. This briefing is awaiting your decision.`, row);
    const latest = project.briefings.filter(b => b.candidate_id === brief.candidate_id).at(-1);
    if (!project.briefing_current[brief.id] || latest.id !== brief.id) { node('p', 'Historical briefing. Reassess current evidence before deciding.', row); continue; }
    const form = node('form', '', row), select = node('select', '', form);
    select.setAttribute('aria-label', 'Your decision');
    for (const choice of ['', 'Adopt','Test','Defer','Reject']) { const option = node('option', choice || 'Choose your decision', select); option.value = choice; }
    select.required = true;
    const rationale = node('textarea', '', form); rationale.required = true; rationale.maxLength = 8000; rationale.setAttribute('aria-label', 'Your decision rationale');
    const save = node('button', 'Save my decision', form); save.type = 'submit';
    form.onsubmit = event => { event.preventDefault(); action(() => mutate('decide', {explicit_action:'record_project_decision', briefing_id:brief.id,
      briefing_sha256:brief.record_sha256, expected_head:head?.id || null, choice:select.value, rationale:rationale.value})); };
  }
  q('#history').textContent = JSON.stringify({operations:project.operations, decisions:project.decisions}, null, 2);
}
q('#create-project').onsubmit = event => { event.preventDefault(); action(async () => {
  const form = event.target, result = await api('/api/projects', {request_id:createId, name:form.elements.name.value,
    brief:form.elements.brief.value, reviewed_sanitized:form.elements.reviewed.checked});
  createId = crypto.randomUUID(); await listProjects(); await openProject(result.project.id);
}); };
q('#create-project').oninput = () => { createId = crypto.randomUUID(); };
q('#discover').onsubmit = event => { event.preventDefault(); action(() => mutate('discover', {query:event.target.elements.query.value})); };
q('#reopen').onclick = () => action(() => openProject(project.project.id));
action(listProjects);
