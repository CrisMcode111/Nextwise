"""Offline Chrome DOM assertions. File input, mocked fetch, no HTTP server or sockets.

Reads existing public artifacts and the persisted decision as fixture input only.
Never invokes the production H-MEM bridge, starts Nextwise or writes a decision.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_nextwise_app import FixtureClient, app


def accepted_fixture():
    """A real validator-accepted recommendation, from explicitly synthetic local inputs.

    All H-MEM writes stay in a temporary directory. No model or source transport.
    """
    import semantic_discovery as semantic
    import opportunity_workflow as workflow
    from semantic_fixture import context, Transport
    from test_update_discovery import Fixture, NOW, rss
    with tempfile.TemporaryDirectory(prefix='nextwise-accepted-presentation-') as tmp:
        store = app.discovery.Store(tmp)
        source = Fixture()
        store.run(source, now=NOW)
        source.feed = rss([('one','Existing fixture article'),('two','Existing fixture summary'),
            ('new-structured','ISOLATED FIXTURE: structured outputs for user requirements')]).replace(
                b'Publisher summary', b'ISOLATED FIXTURE: A language model supports structured outputs for user requirements through a compatible API.')
        store.run(source, now=NOW)
        ctx = context()
        with patch.object(semantic, 'project_context', return_value=ctx):
            state = semantic.run(store, 'ISOLATED_NO_RUNTIME_TOKEN', ctx, Transport(), lambda msg: None)
            item = next(i for i in state['items'].values() if i['guid']=='new-structured')
            assert item['kind']=='new_article' and item['semantic_assessment']['status']=='validated'
            assert item['semantic_assessment']['category']=='potential relevance'
            saved = workflow.prepare(store, item['id'], item['content_sha256'], item['semantic_assessment']['cache_key'])
            entries = workflow.view(store, saved)
            assert len(entries)==1 and entries[0]['current']
            return {'entry': entries[0], 'items': saved['items']}


def fixtures(*, staged=False):
    artifacts = {kind: json.loads((ROOT / app.exporter.INPUTS[name]).read_text(encoding='utf-8'))
                 for name, kind in app.KINDS.items()}
    mem = {'investigation_id': app.INVESTIGATION, 'artifacts': artifacts,
        'artifact_paths': {kind: app.exporter.INPUTS[name] for name, kind in app.KINDS.items()},
        'artifact_hashes': {kind: hashlib.sha256((ROOT / app.exporter.INPUTS[name]).read_bytes()).hexdigest()
                            for name, kind in app.KINDS.items()},
        'artifact_ids': {kind: 'ISOLATED-' + kind for kind in app.KINDS.values()},
        'manifest_id': 'ISOLATED-PRESENTATION-FIXTURE', 'upstream_commit': 'ISOLATED', 'analysis_observation': {}}
    # The supplied callback prevents the loader's real bridge/default from running.
    data = app.load_investigation(FixtureClient(mem), lambda: mem)
    raw = json.loads((app.memory.DEFAULT_MEMORY_ROOT / app.INVESTIGATION / 'state.json').read_text(encoding='utf-8'))
    history = []
    for record in raw['records']:
        if record.get('source') == 'nextwise:human-decision':
            envelope = json.loads(record['content']); decision = envelope['decision']
            assert app.discovery.sha(json.dumps(decision, sort_keys=True, ensure_ascii=False, separators=(',', ':'))) == envelope['sha256']
            history.append({**decision, 'record_sha256': envelope['sha256'], 'needs_review': False, 'integrity_issues': []})
    history.sort(key=lambda d: d['version'])
    assert history and history[0]['choice'] == 'Defer' and history[0]['version'] == 1
    raw = json.loads((app.memory.DEFAULT_MEMORY_ROOT / 'update-discovery/state.json').read_text(encoding='utf-8'))
    saved = max((json.loads(r['content'])['value'] for r in raw['records']), key=lambda v: v['version'])
    assert not saved.get('opportunity_recommendations'), 'Real saved opportunities changed; update the zero-opportunity fixture honestly.'
    from saved_source_opportunity_fixture import build
    with tempfile.TemporaryDirectory(prefix='nextwise-real-source-browser-fixture-') as tmp:
        # Same persisted API payload produced by the real-source isolated runner
        # test, with a clearly synthetic response. Never production acceptance.
        isolated = build(tmp, staged=staged)
        saved_review = isolated['discovery']
    return {'data': data, 'history': {'ok': True, 'history': history},
        'accepted_fixture': accepted_fixture(),
        'saved_review_fixture': saved_review,
        'staged_fixture': staged,
        'discovery': {'status': {'running': False, 'message': 'ISOLATED saved-fixture view'},
            'scope': app.discovery.config(), 'semantic_review_supported': True, 'discovery': saved, 'opportunities': []}}


BOOT = r'''
window.__fixture=FIXTURE_DATA;window.__calls=[];window.__errors=[];window.__networkAttempts=0;window.__holdLoad=true;
addEventListener('error',()=>__errors.push('script error'));addEventListener('unhandledrejection',()=>__errors.push('unhandled rejection'));
window.fetch=async(path,options={})=>{
 __calls.push({path,method:options.method||'GET',body:options.body});
 const response=(body,status=200)=>({ok:status>=200&&status<300,status,json:async()=>structuredClone(body)});
 if(path==='/api/status')return response({authenticated:true});
 if(path==='/api/load'){if(__holdLoad)return new Promise(resolve=>{window.__releaseLoad=()=>{__holdLoad=false;resolve(response(__fixture.data));};});return response(__fixture.data);}
 if(path==='/api/decisions')return response(__fixture.history);
 if(path==='/api/discovery')return window.__discoveryFail?response({message:'ISOLATED diagnostic detail'},503):response(__fixture.discovery);
 if(path==='/api/decision')return new Promise(resolve=>{window.__rejectSave=()=>resolve(response({message:'ISOLATED save not confirmed'},503));});
 throw Error('Unexpected fixture request');
};
window.XMLHttpRequest=class{constructor(){__networkAttempts++;throw Error('Network forbidden');}};
window.WebSocket=class{constructor(){__networkAttempts++;throw Error('Network forbidden');}};
window.EventSource=class{constructor(){__networkAttempts++;throw Error('Network forbidden');}};
navigator.sendBeacon=()=>{__networkAttempts++;return false;};
'''

ASSERTIONS = r'''
(async()=>{
 const checks=[];const check=(name,passed)=>{checks.push({name,passed:!!passed});if(!passed)throw Error(name);};
 const until=async f=>{for(let i=0;i<80;i++){if(f())return;await new Promise(r=>setTimeout(r,30));}throw Error('Fixture wait timed out');};
 const visibleText=()=>document.body.innerText;
 const before=(a,b)=>!!($(a).compareDocumentPosition($(b))&Node.DOCUMENT_POSITION_FOLLOWING);
 try{
 await until(()=>typeof loading!=='undefined'&&loading&&window.__releaseLoad);
 check('Loading explains saved work without exposing infrastructure', $('#state h2').textContent==='Opening your saved work'&&!$('#load-error-details').open&&!visibleText().includes('Zetaris'));
 __releaseLoad();
 await until(()=>!loading&&!discoveryReading&&decisionState&&!content.hidden&&$('#discovery-overview').textContent.includes('saved items'));
 check('Personal briefing leads and previous investigation starts collapsed',before('#opportunities','#previous-investigations')&&!$('#previous-investigations').open&&!visibleText().includes(__fixture.data.investigation.question));
 check('Welcome names the project and reads its goal as a sentence',$('#briefing-project').textContent.includes(__fixture.data.profile.name)&&$('#briefing-purpose').textContent.includes(contextSentence(__fixture.data.profile.objective)));
 check('Business name, objective, task and technology come from saved data',$('#workspace-business').textContent===__fixture.data.profile.name&&$('#investigation-brief').textContent.includes(contextSentence(__fixture.data.profile.objective))&&$('#investigation-brief').textContent.includes(contextSentence(__fixture.data.task.description))&&$('#investigation-brief').textContent.includes(__fixture.data.investigation.technology));
 check('Existing investigation is not labelled as a new discovery',$('#investigation-brief').textContent.includes('not a newly discovered release'));
 check('Saved advice and uncertainty appear beside the human decision',$('#investigation-brief .next-summary').textContent===recommendationSummary(__fixture.data.recommendation)&&$('#investigation-brief').textContent.includes('1 of 4')&&$('#investigation-brief #decision-panel')&&$('#investigation-brief').textContent.includes('not customer use'));
 check('Genuine Defer Version 1 stays accessible with exact rationale',$('#previous-status').textContent.includes('Defer')&&$('#decision-panel > .saved-decision .human-text').textContent===__fixture.history.history.at(-1).rationale);
 check('Reconsideration uses the saved next action without inventing a date',$('#decision-panel > .saved-decision .reconsideration').textContent===__fixture.history.history.at(-1).next_action);
 check('Evidence, background, histories and diagnostics start collapsed',['evidence-details','project-background','diagnostics','decision-history','discovery'].every(id=>!document.getElementById(id).open));
 check('Initial view keeps raw trial outputs and validator diagnostics secondary',!visibleText().includes('Original model output')&&!visibleText().includes('Validation detail:')&&!visibleText().includes('SHA-256'));
 check('Rejected updates have a visible understandable count',$('#discovery-overview').textContent.includes('could not be assessed')&&$('#discovery-overview').textContent.includes('uncertain'));
 check('Real zero-opportunity state offers no fake recommendation',$('#opportunities-status').textContent.includes("I don't have a new verified opportunity")&&!$('#opportunities .opportunity-decision')&&$('#opportunities').textContent.includes('does not mean sources were checked today'));
 const accepted=structuredClone(__fixture.accepted_fixture),entry=accepted.entry,r=entry.recommendation;
 briefingItems=accepted.items;paintOpportunities([entry]);
 check('Validator-accepted synthetic opportunity is the primary briefing',$('#opportunities-status').textContent.includes('a saved opportunity')&&!!$('#opportunities>article')&&!$('#previous-investigations').open&&$('#opportunities>article h3').textContent===r.title);
 check('Accepted briefing shows grounded connection, hypothesis, recommendation and uncertainty',[r.what_changed,r.why_it_matters,r.potential_value,r.recommendation_reason,r.next_action,...r.risks,...r.uncertainty].every(t=>$('#opportunities>article').textContent.includes(t))&&$('#opportunities').textContent.includes('hypothesis, not a verified benefit'));
 check('Source and saved dates are visible without inventing a new publication',$('#opportunities .briefing-source a').href===r.evidence_references.url&&$('#opportunities .briefing-source').textContent.includes(date(r.evidence_references.publication_date))&&$('#opportunities .briefing-source').textContent.includes(date(r.created_at)));
 check('Accepted briefing offers an explicit undecided human choice',!!$('#opportunities .opportunity-decision')&&$('#opportunities select').value===''&&$('#opportunities').textContent.includes('No human opportunity decision has been recorded')&&decisionState.history.at(-1).choice==='Defer');
 check('Accepted briefing evidence and history remain expandable',[...$('#opportunities').querySelectorAll('details')].every(d=>!d.open)&&$('#opportunities').textContent.includes(r.supporting_evidence[0].exact_quote));
 const note=$('#opportunities textarea');note.value='ISOLATED opportunity draft';note.dispatchEvent(new Event('input'));paintOpportunities([entry]);
 check('Opportunity redraw preserves the draft without recording a decision',$('#opportunities textarea').value==='ISOLATED opportunity draft'&&!__calls.some(c=>c.path==='/api/discovery/decision'));
 const candidate=briefingItems[r.candidate_id];candidate.kind='initial_inventory';paintOpportunities([entry]);
 check('Accepted baseline review is visible without being announced as new',!!$('#opportunities>article')&&$('#opportunities-status').textContent.includes("don't have a new verified opportunity")&&$('#opportunities>article').textContent.includes('Saved-source review')&&!!$('#opportunities .opportunity-decision'));
 candidate.kind='new_article';candidate.semantic_assessment.status='failed';paintOpportunities([entry]);
 check('Rejected assessment offers no accepted recommendation or decision',!$('#opportunities>article')&&!$('#opportunities .opportunity-decision')&&$('#opportunities-status').textContent.includes("don't have a new verified opportunity")&&$('#opportunities').textContent.includes('could not be confirmed'));
 candidate.semantic_assessment.status='validated';const staleEntry={...entry,current:false};paintOpportunities([staleEntry]);
 check('Stale evidence stays secondary and decision submission is disabled',!$('#opportunities>article')&&$('#opportunities button[type=submit]').disabled&&$('#opportunities').textContent.includes('needs checking again'));
 paintDiscovery(__fixture.saved_review_fixture);
 const savedReview=__fixture.saved_review_fixture.opportunities[0].recommendation;
 check('Real snapshot and context with synthetic accepted response render a continuation',$('#opportunities>article h3').textContent===savedReview.title&&$('#opportunities>article').textContent.includes('continuation of your existing investigation, not a new discovery')&&$('#opportunities-status').textContent.includes("don't have a new verified opportunity"));
 check('Continuation explains source, business need, hypothetical value and bounded next step',[savedReview.what_changed,savedReview.why_it_matters,savedReview.potential_value,savedReview.next_action,savedReview.existing_findings_connection].every(t=>$('#opportunities>article').textContent.includes(t))&&$('#opportunities>article').textContent.includes('My recommendation: Defer'));
 check('Continuation keeps genuine decision separate from unapproved advice',!$('#previous-investigations').open&&$('#previous-status').textContent.includes('Defer')&&$('#opportunities>article').textContent.includes('No human opportunity decision has been recorded')&&$('#opportunities select').value==='');
 check('Continuation provenance links and exact passages remain accessible',$('#opportunities .briefing-source a').href===savedReview.evidence_references.url&&$('#opportunities').textContent.includes(savedReview.supporting_evidence[0].exact_quote)&&[...$('#opportunities').querySelectorAll('details')].every(d=>!d.open));
 if(__fixture.staged_fixture)check('Staged accepted result reaches the same UI with its extraction audit and unchosen human control',$('#discovery-results').textContent.includes('Opt-in staged publisher-claim extraction')&&!!__fixture.saved_review_fixture.discovery.items[savedReview.candidate_id].semantic_assessment.staged_plan&&$('#opportunities select').value==='');
 await readDiscovery();
 $('nav a[href="#evidence"]').click();await until(()=>$('#evidence-details').open);
 location.hash='#claim-0';await until(()=>$('#claim-0').open&&$('#publisher-claims').open);
 check('Evidence navigation reveals complete nested quotations',$('#evidence-details').open&&$('#claim-0 blockquote').textContent===__fixture.data.claims[0].exact_supporting_quote);
 $('nav a[href="#update"]').click();await until(()=>$('#project-background').open);
 $('#project-background').open=false;$('nav a[href="#update"]').click();await until(()=>$('#project-background').open);
 check('Repeated navigation reopens background and keeps source links',!!$('#update a[href^="https://"]'));
 $('nav a[href="#decision-panel"]').click();await until(()=>location.hash==='#decision-panel');
 check('Saved decision navigation opens the previous investigation',$('#previous-investigations').open&&visibleText().includes('Recorded human decision: Defer · Version 1'));
 $('#amend-decision').click();$('input[value="Test"]').click();
 $('#decision-rationale').value='ISOLATED draft <img src=x onerror=alert(1)>';$('#decision-rationale').dispatchEvent(new Event('input',{bubbles:true}));
 $('#decision-next-action').value='ISOLATED condition';$('#decision-next-action').dispatchEvent(new Event('input',{bubbles:true}));
 render(__fixture.data);await readDiscovery();
 check('Presentation redraw preserves all user decision drafts',$('input[value="Test"]').checked&&$('#decision-rationale').value.includes('ISOLATED draft')&&$('#decision-next-action').value==='ISOLATED condition');
 $('#decision-form').requestSubmit();await until(()=>decisionSaving&&window.__rejectSave);
 check('Saving disables duplicate submission',$('#save-decision').disabled&&$('#decision-rationale').disabled);
 __rejectSave();await until(()=>!decisionSaving);
 check('Failed save preserves draft and never replaces the recorded decision',$('#decision-rationale').value.includes('ISOLATED draft')&&decisionState.history.at(-1).choice==='Defer'&&!decisionMessage);
 check('User text remains inert',!$('#decision-panel img')&&!$('#decision-panel script'));
 decisionDraft={choice:'',rationale:'',next_action:'',request_id:null,expected_head:null,editing:false,started:false};decisionError='';
 decisionState={ok:true,history:[]};paintDecisionPanel();check('Empty confirmed history invents no decision',decisionPanel.textContent.includes('No human decision has been recorded')&&!decisionPanel.textContent.includes('Recorded human decision:'));
 decisionState=null;paintDecisionPanel();check('Unavailable history is not presented as saved',!decisionPanel.querySelector('.saved-decision')&&decisionPanel.textContent.includes('not been able to confirm'));
 decisionState=structuredClone(__fixture.history);const later={...decisionState.history[0],choice:'Test',version:2,decision_id:'ISOLATED-V2',next_action:null};decisionState.history.push(later);paintDecisionPanel();
 check('Decision follows persisted head while Version 1 remains distinct',decisionPanel.textContent.includes('Recorded human decision: Test · Version 2')&&decisionPanel.textContent.includes('First saved decision: Defer · Version 1')&&$('#decision-history').textContent.includes('Version 1'));
 check('Missing reconsideration condition is explicit',$('#decision-panel > .saved-decision .reconsideration').textContent.includes('No next action or reconsideration condition'));
 decisionState=__fixture.history;
 for(const code of ['authentication','memory','empty','integrity','zetaris','network']){
  showState(code,'ISOLATED INTERNAL technical diagnostic');
  check('Understandable unavailable state: '+code,content.hidden&&!$('#load-error-details').open&&!visibleText().includes('ISOLATED INTERNAL')&&decisionPanel.textContent.includes('Recorded human decision: Defer · Version 1'));
 }
 render(__fixture.data);paintOpportunities([{recommendation:{recommended_choice:'',what_changed:'',why_it_matters:''},decisions:[]}]);
 check('Incomplete opportunity cannot look accepted or offer a decision',$('#opportunities').textContent.includes('No recommendation is ready')&&!$('#opportunities .tag')&&!$('#opportunities .opportunity-decision'));
 await readDiscovery();window.__discoveryFail=true;await readDiscovery();
 check('Unavailable opportunities have an explicit refresh warning',$('#opportunities-status').textContent.includes('could not refresh')&&!content.hidden);
 const noAdvice=structuredClone(__fixture.data);noAdvice.recommendation.recommended_next_step='';render(noAdvice);
 check('Empty saved recommendation is labelled unavailable',$('#investigation-brief').textContent.includes('Recommendation unavailable')&&!$('#investigation-brief').textContent.includes('Saved advice · For your review'));
 render(__fixture.data);document.documentElement.style.scrollBehavior='auto';
 check('Layout fits the '+document.documentElement.clientWidth+'px viewport',document.documentElement.scrollWidth<=document.documentElement.clientWidth);
 check('Navigation, labels and live regions remain accessible',!!$('.skip[href="#main"]')&&!!$('nav[aria-label]')&&$('#state').getAttribute('aria-live')==='polite'&&$('#decision-rationale')===null&&!!$('#discovery>summary'));
 check('No application network requests or unexpected script errors',__networkAttempts===0&&__errors.length===0&&__calls.every(c=>c.path.startsWith('/api/')));
 }catch(error){checks.push({name:'Fixture completion: '+error.message,passed:false});}
 window.__discoveryFail=false;await readDiscovery();history.replaceState(null,'',location.pathname);$('#previous-investigations').open=false;
 await new Promise(resolve=>setTimeout(resolve,100));window.scrollTo({top:0,left:0,behavior:'instant'});
 await new Promise(resolve=>setTimeout(resolve,100));
 const result=document.createElement('pre');result.id='presentation-test-results';result.hidden=true;result.textContent=JSON.stringify(checks);document.body.append(result);
})();
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width',type=int,default=1440)
    parser.add_argument('--screenshot',type=Path)
    parser.add_argument('--staged-fixture', action='store_true', help='Synthetic staged output with genuine saved inputs and temporary H-MEM; no model/network calls.')
    args=parser.parse_args()
    if args.screenshot and not args.screenshot.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise SystemExit('Presentation screenshots must stay in OS temporary storage.')
    original = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    css = (ROOT / 'web/style.css').read_text(encoding='utf-8')
    js = (ROOT / 'web/app.js').read_text(encoding='utf-8')
    document = re.sub(r'<script\b[^>]*src=[^>]*></script>', '', original)
    document = re.sub(r'<link\b[^>]*rel="stylesheet"[^>]*>', '<style>' + css + 'html{scroll-behavior:auto!important}</style>', document)
    boot = BOOT.replace('FIXTURE_DATA', json.dumps(fixtures(staged=args.staged_fixture), ensure_ascii=True).replace(chr(60), chr(92)+'u003c'))
    document = document.replace('</body>', '<script>' + boot + '</script><script>' + js + '</script><script>' + ASSERTIONS + '</script></body>')
    with tempfile.TemporaryDirectory(prefix='nextwise-business-presentation-') as tmp:
        page = Path(tmp) / 'fixture.html'; page.write_text(document, encoding='utf-8')
        command = [r'C:\Program Files\Google\Chrome\Application\chrome.exe', '--headless=new',
            '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
            '--disable-component-update', '--disable-sync', '--host-resolver-rules=MAP * ~NOTFOUND',
            f'--window-size={args.width},1000', '--user-data-dir=' + str(Path(tmp) / 'chrome'),
            '--dump-dom', '--virtual-time-budget=12000']
        if args.screenshot:command.append('--screenshot='+str(args.screenshot))
        result = subprocess.run([*command,page.as_uri()], capture_output=True, timeout=60)
    output = result.stdout.decode('utf-8', errors='replace')
    match = re.search(r'<pre id="presentation-test-results"[^>]*>(.*?)</pre>', output, re.S)
    if not match:
        raise SystemExit('Offline browser did not complete fixture assertions; page contents suppressed.')
    checks = json.loads(html.unescape(match.group(1)))
    for check in checks: print(('PASS ' if check['passed'] else 'FAIL ') + check['name'])
    print(f'{sum(c["passed"] for c in checks)}/{len(checks)} offline browser assertions passed.')
    if not all(c['passed'] for c in checks): raise SystemExit(1)


if __name__ == '__main__': main()
