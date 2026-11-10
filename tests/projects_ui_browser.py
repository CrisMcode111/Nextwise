"""Offline Projects UI checks using installed Chrome and synthetic fixtures.

CDP fulfills every page, asset and API GET in memory, blocks all other requests,
and never contacts the running backend or providers. Mutation scenarios use
browser-local fetch stubs. Preview artifacts are written under reports/projects_ui.
Run: python -B tests/projects_ui_browser.py
Requires installed Chrome and the existing test-only websocket-client package.
"""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_nextwise_browser import Browser

ORIGIN = 'http://127.0.0.1:8765'
PROJECT = 'project-synthetic-ui-fixture'
OUT = ROOT / 'reports/projects_ui'


def project_fixture():
    """Synthetic UI-shaped records; validation is covered by workflow tests."""
    when = '2026-01-01T12:00:00Z'
    quote = 'The example tool answers questions using published policies.'
    evidence = [{'passage_id':'synthetic-passage', 'exact_quote':quote}]
    assessment = {'category':'uncertain relevance', 'application_hypothesis':None,
        'priority_reason':'A concrete fit for this synthetic project has not been established.',
        'investigation_question':'Does the capability address the project objective?',
        'project_need':'Answer public policy questions.', 'evidence':evidence}
    brief = {'id':'synthetic-briefing', 'candidate_id':'source-1',
        'assessment_id':'synthetic-assessment', 'record_sha256':'a'*64,
        'created_at':when, 'title':'Synthetic policy assistant', 'recommended_choice':'Defer',
        'label':'Synthetic test fixture; provisional guidance.',
        'why_it_matters':'The project needs accurate answers about its own policies.',
        'potential_value':None, 'risks':['Project compatibility is unknown.'],
        'uncertainty':['Accuracy has not been verified.'],
        'next_action':'Review the project requirements before considering a trial.',
        'supporting_evidence':evidence, 'what_changed':quote,
        'evidence_references':{'url':'https://example.invalid/source-1'},
        'context_evidence_references':[]}
    decision = {'id':'synthetic-decision', 'candidate_id':'source-1',
        'briefing_id':brief['id'], 'version':1, 'choice':'Defer', 'created_at':when,
        'rationale':'Synthetic original rationale: verify compatibility before reconsidering.'}
    operations = {record_id:{'action':action, 'status':'completed'} for record_id, action in
        [('synthetic-discovery','discover'),('synthetic-assessment','assess'),
         ('synthetic-briefing','brief'),('synthetic-decision','decide')]}
    operations.update({f'synthetic-failed-{i}':{'action':'assess','status':'failed'} for i in range(3)})
    return {'project':{'id':PROJECT,'name':'Synthetic policy project','created_at':when,
        'brief':'A synthetic project needs accurate answers based on its own public policies.'},
        'version':15, 'items':{f'source-{i}':{'id':f'source-{i}',
            'title':f'Synthetic saved source {i}', 'url':f'https://example.invalid/source-{i}',
            'retrieved_at':when} for i in range(1,4)},
        'assessments':[{'id':'synthetic-assessment','candidate_id':'source-1',
            'assessment':assessment,'created_at':when,'validation':{'valid':True}}],
        'briefings':[brief], 'briefing_current':{brief['id']:True},
        'decisions':[decision], 'operations':operations, 'runs':[]}


class ReadOnlyBrowser(Browser):
    def call(self, method, params=None):
        identity = self.send(method, params)
        while True:
            message = json.loads(self.ws.recv())
            if message.get('method') == 'Fetch.requestPaused':
                request = message['params']['request']
                rid = message['params']['requestId']
                self.request_log.append((request['method'], request['url']))
                response = self.responses.get(request['url'])
                if request['method'] != 'GET' or response is None:
                    self.blocked_requests.append(request['url'])
                    self.send('Fetch.failRequest', {'requestId':rid,'errorReason':'BlockedByClient'})
                else:
                    kind, body = response
                    self.send('Fetch.fulfillRequest', {'requestId':rid,'responseCode':200,
                        'responseHeaders':[{'name':'Content-Type','value':kind}],
                        'body':base64.b64encode(body).decode()})
            if message.get('method') == 'Runtime.exceptionThrown':
                self.errors += 1
            if message.get('id') == identity:
                if 'error' in message:
                    raise RuntimeError('CDP failed: ' + method)
                return message.get('result', {})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    saved = project_fixture()
    before = json.dumps(saved, sort_keys=True)
    responses = {ORIGIN+route:(kind, (ROOT/path).read_bytes()) for route, kind, path in
        [('/projects','text/html; charset=utf-8','web/projects.html'),
         ('/style.css','text/css; charset=utf-8','web/style.css'),
         ('/projects.js','text/javascript; charset=utf-8','web/projects.js')]}
    responses[ORIGIN+'/api/projects'] = ('application/json', json.dumps({
        'projects':[saved['project']], 'transports':{'search':False,'assessment':False}}).encode())
    responses[ORIGIN+'/api/projects/'+PROJECT] = ('application/json', json.dumps(saved).encode())
    responses[ORIGIN+'/favicon.ico'] = ('image/x-icon', b'')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    checks = []
    browser = None
    with tempfile.TemporaryDirectory(prefix='nextwise-projects-chrome-', ignore_cleanup_errors=True) as tmp:
        process = subprocess.Popen([
            'C:/Program Files/Google/Chrome/Application/chrome.exe', '--headless=new',
            '--disable-gpu', '--no-first-run', '--no-default-browser-check',
            '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
            '--user-data-dir=' + tmp, 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            port_file = Path(tmp) / 'DevToolsActivePort'
            deadline = time.monotonic() + 20
            while not port_file.exists() and time.monotonic() < deadline:
                time.sleep(.2)
            port = port_file.read_text().splitlines()[0]
            pages = json.load(opener.open('http://127.0.0.1:' + port + '/json', timeout=5))
            browser = ReadOnlyBrowser(next(p['webSocketDebuggerUrl'] for p in pages if p['type'] == 'page'))
            browser.responses = responses
            browser.call('Page.enable'); browser.call('Runtime.enable')
            browser.call('Fetch.enable', {'patterns': [{'urlPattern': '*', 'requestStage': 'Request'}]})
            browser.call('Emulation.setDeviceMetricsOverride', {'width':1440, 'height':1100, 'deviceScaleFactor':1, 'mobile':False})
            browser.call('Page.navigate', {'url':ORIGIN + '/projects'})
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if browser.evaluate('typeof project !== "undefined" && project !== null && !busy'):
                    break
                time.sleep(.2)

            def check(label, expression):
                assert browser.evaluate(expression) is True, label
                checks.append(label)
                print('PASS: ' + label, flush=True)

            check('Synthetic saved project opens without a write', 'project.project.id === ' + json.dumps(PROJECT))
            check('Desktop branded header remains visible above the hero', "(()=>{const header=document.querySelector('body>.topbar'),brand=header.querySelector('.brand'),logo=header.querySelector('.mark'),badge=header.querySelector('.beta'),hero=document.querySelector('.signature-hero'),r=header.getBoundingClientRect(),b=brand.getBoundingClientRect();return getComputedStyle(header).display!=='none' && getComputedStyle(header).visibility==='visible' && r.height>0 && r.bottom<=hero.getBoundingClientRect().top && b.left>=0 && b.right<=innerWidth && logo.getBoundingClientRect().width>0 && logo.textContent==='n\u2197' && getComputedStyle(logo).fontStyle==='italic' && getComputedStyle(logo).fontFamily.includes('Georgia') && brand.textContent.includes('nextwise') && badge.textContent==='LOCAL WORKSPACE' && badge.getBoundingClientRect().right<=innerWidth;})()")
            check('Field occupies a dedicated desktop hero panel', "(()=>{const copy=document.querySelector('.signature-copy').getBoundingClientRect(),figure=document.querySelector('.signature-figure').getBoundingClientRect();return copy.right<figure.left && document.querySelector('#opportunity-empty canvas')===null;})()")
            check('Field has no spiral, diagram or visible explanatory labels', "document.querySelectorAll('.signature-figure canvas').length===1 && document.querySelectorAll('.signature-figure svg,.signature-figure figcaption,#fibonacci-curve').length===0")
            check('Canvas resolution is bounded', "(()=>{const c=document.querySelector('#intelligence-field');return c.width<=c.clientWidth*1.5+1 && c.height<=c.clientHeight*1.5+1;})()")
            before_motion = browser.evaluate("document.querySelector('#intelligence-field').toDataURL()")
            time.sleep(.8)
            assert before_motion != browser.evaluate("document.querySelector('#intelligence-field').toDataURL()")
            checks.append('Ambient field evolves while idle')
            check('Idle artwork is not presented as AI activity', "!busy && document.querySelector('.signature-hero [role=progressbar]')===null && document.querySelector('#intelligence-field').getAttribute('aria-label').includes('not live AI activity')")
            check('No uncertain evaluation is promoted to an opportunity', "document.querySelectorAll('#opportunities article').length===0 && !document.querySelector('#opportunity-empty').hidden && document.querySelector('#opportunity-count').textContent==='0 to explore' && !document.body.innerText.includes('Human decision Version 1: Defer') && document.body.innerText.includes('No selected opportunities yet.')")
            check('Original evaluation and decision remain in the collapsed archive', "!document.querySelector('#previous-evaluations').open && document.querySelectorAll('#briefings .project-briefing').length===1 && document.querySelector('#briefings .human-rationale').textContent === " + json.dumps(saved['decisions'][0]['rationale']))
            check('Saved evaluation outcome is separate from human Defer', "document.querySelector('#briefings .ai-recommendation h4').textContent === 'Defer' && document.querySelector('#briefings .human-decision-panel h4').textContent.includes('Human decision Version 1: Defer')")
            check('Dashboard overview uses saved project text and actual counts', "document.querySelector('#project-overview').textContent.startsWith(project.project.brief.slice(0,100)) && [...document.querySelectorAll('#project-counts strong')].map(n=>n.textContent).join(',')==='0,3,1'")
            check('Empty-state navigation opens saved context without a request', r'''(()=>{const before=performance.getEntriesByType('resource').length; document.querySelector('#review-evaluations').click(); const visible=document.querySelector('#previous-evaluations').open && document.querySelector('.human-rationale').getClientRects().length>0; document.querySelector('#previous-evaluations').open=false; document.querySelector('#review-evidence').click(); const evidence=document.querySelector('#saved-evidence').open; document.querySelector('#saved-evidence').open=false; window.scrollTo(0,0); return visible && evidence && performance.getEntriesByType('resource').length===before;})()''')
            check('Actual relevance, null hypothesis and evidence', "document.querySelector('.project-briefing').textContent.includes('uncertain relevance') && document.querySelector('.hypothesis-note') !== null && document.querySelectorAll('.source-card').length === 3 && [...document.querySelectorAll('blockquote')].map(n=>n.textContent).every((quote,i)=>quote === project.briefings[0].supporting_evidence[i].exact_quote)")
            check('Timeline exposes failed and completed recorded actions', "document.querySelectorAll('.timeline-event').length === Object.keys(project.operations).length + 1 && document.querySelector('#history').textContent.includes('Failed') && document.querySelector('#history').textContent.includes('Completed') && !document.querySelector('#history').textContent.includes('fingerprint')")
            check('History starts collapsed with accurate saved-event counts', "!document.querySelector('#project-history').open && document.querySelector('#history-summary').textContent.startsWith((Object.keys(project.operations).length+1)+' saved events') && document.querySelector('#history-summary').textContent.includes(Object.values(project.operations).filter(o=>o.status==='failed').length+' failed')")
            check('Expanded history preserves timeline and full technical records', r'''(()=>{const history=document.querySelector('#project-history'); history.querySelector('summary').click(); const technical=document.querySelector('#history-details').parentElement; technical.open=true; const ok=history.open && document.querySelector('#history').getClientRects().length>0 && document.querySelector('#history-details').textContent===JSON.stringify({operations:project.operations,decisions:project.decisions},null,2); technical.open=false; history.querySelector('summary').click(); return ok && !history.open;})()''')
            check('Briefing prioritizes recommendation, saved reasoning, uncertainty and next step', r'''(()=>{const card=document.querySelector('.project-briefing'), a=project.assessments[0].assessment, sections=['.ai-recommendation','.briefing-reasoning','.project-gaps','.project-next-step'].map(s=>card.querySelector(s)); return sections.every(Boolean) && sections.slice(0,-1).every((n,i)=>Boolean(n.compareDocumentPosition(sections[i+1]) & Node.DOCUMENT_POSITION_FOLLOWING)) && card.querySelector('.briefing-reasoning .copy').textContent===a.priority_reason && card.querySelector('.briefing-connection').textContent===project.briefings[0].why_it_matters && card.querySelector('.saved-question').textContent===a.investigation_question && card.querySelector('.project-next-step p').textContent===project.briefings[0].next_action;})()''')
            check('Provider actions unavailable; amendment has no preselected choice', "[...document.querySelectorAll('.source-card button')].filter(n=>n.textContent==='Assess against my project').every(n=>n.disabled) && document.querySelector('#discover button').disabled && document.querySelector('.project-decision-form select').value === ''")
            check('Evidence and evaluation details are secondary disclosures', "!document.querySelector('#saved-evidence').open && !document.querySelector('#previous-evaluations').open && document.querySelector('#sources').closest('details').id==='saved-evidence' && document.querySelector('#briefings').closest('details').id==='previous-evaluations'")
            check('Desktop layout and no horizontal overflow', "getComputedStyle(document.querySelector('.projects-layout')).gridTemplateColumns.split(' ').length === 2 && document.documentElement.scrollWidth <= innerWidth")
            check('Quotations and technical history are expandable', "document.querySelector('#history-details').parentElement.tagName === 'DETAILS' && document.querySelector('blockquote').parentElement.tagName === 'DETAILS' && !document.querySelector('blockquote').parentElement.open")
            size = browser.call('Page.getLayoutMetrics')['cssContentSize']
            data = browser.call('Page.captureScreenshot', {'format':'png', 'captureBeyondViewport':True,
                'clip':{'x':0, 'y':0, 'width':1440, 'height':size['height'], 'scale':1}})['data']
            (OUT / 'desktop.png').write_bytes(base64.b64decode(data))
            hero = browser.evaluate("(()=>{const r=document.querySelector('.signature-hero').getBoundingClientRect();return {x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height,scale:1};})()")
            data = browser.call('Page.captureScreenshot', {'format':'png', 'captureBeyondViewport':True, 'clip':hero})['data']
            (OUT / 'signature.png').write_bytes(base64.b64decode(data))
            time.sleep(2)
            data = browser.call('Page.captureScreenshot', {'format':'png', 'captureBeyondViewport':True, 'clip':hero})['data']
            (OUT / 'signature-later.png').write_bytes(base64.b64decode(data))
            browser.call('Emulation.setDeviceMetricsOverride', {'width':390, 'height':844, 'deviceScaleFactor':1, 'mobile':True})
            check('Mobile branded header remains visible above the hero', "(()=>{const header=document.querySelector('body>.topbar'),brand=header.querySelector('.brand'),logo=header.querySelector('.mark'),badge=header.querySelector('.beta'),hero=document.querySelector('.signature-hero'),r=header.getBoundingClientRect(),b=brand.getBoundingClientRect();return getComputedStyle(header).display!=='none' && getComputedStyle(header).visibility==='visible' && r.height>0 && r.bottom<=hero.getBoundingClientRect().top && b.left>=0 && b.right<=innerWidth && logo.getBoundingClientRect().width>0 && logo.textContent==='n\u2197' && getComputedStyle(logo).fontStyle==='italic' && getComputedStyle(logo).fontFamily.includes('Georgia') && brand.textContent.includes('nextwise') && badge.textContent==='LOCAL WORKSPACE' && badge.getBoundingClientRect().right<=innerWidth;})()")
            check('Mobile layout fits viewport', "document.documentElement.scrollWidth <= innerWidth && getComputedStyle(document.querySelector('.projects-layout')).gridTemplateColumns.split(' ').length === 1")
            check('Mobile empty-state text fits inside its card', "(()=>{const card=document.querySelector('#opportunity-empty').getBoundingClientRect(),copy=document.querySelector('.opportunity-empty-copy').getBoundingClientRect();return copy.left>=card.left && copy.right<=card.right-15;})()")
            check('Mobile signature stacks separately from the hero text', "(()=>{const copy=document.querySelector('.signature-copy').getBoundingClientRect(),figure=document.querySelector('.signature-figure').getBoundingClientRect(),svg=document.querySelector('#intelligence-field').getBoundingClientRect();return copy.bottom<figure.top && svg.width<=figure.width && figure.right<=innerWidth;})()")
            size = browser.call('Page.getLayoutMetrics')['cssContentSize']
            data = browser.call('Page.captureScreenshot', {'format':'png', 'captureBeyondViewport':True,
                'clip':{'x':0, 'y':0, 'width':390, 'height':size['height'], 'scale':1}})['data']
            (OUT / 'mobile.png').write_bytes(base64.b64decode(data))
            browser.call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion', 'value':'reduce'}]})
            browser.evaluate("status('Fixture pending action', 'pending');")
            check('Reduced motion disables pending animation', "getComputedStyle(document.querySelector('#status'),'::before').animationName === 'none'")
            time.sleep(.2)
            still = browser.evaluate("document.querySelector('#intelligence-field').toDataURL()")
            time.sleep(.4)
            assert still == browser.evaluate("document.querySelector('#intelligence-field').toDataURL()")
            checks.append('Reduced motion keeps the field static')
            # All mutations below are synthetic, in-memory responses. The network
            # interceptor above independently refuses any accidentally unstubbed POST.
            browser.evaluate(r'''window.__saved = structuredClone(project); window.__calls = []; window.__confirmations = []; window.__approved = false;
window.confirm = text => { __confirmations.push(text); return __approved; };
window.fetch = async (path, options = {}) => { __calls.push({path, options}); return {ok:true, json:async()=> options.method === 'POST' ? {project:{id:__saved.project.id}} : structuredClone(__saved)}; };
transports = {search:true,assessment:true}; render();''')
            check('Enabled provider buttons still require explicit confirmation', "(async()=>{ await mutate('assess',{candidate_id:Object.keys(project.items)[0]}); await mutate('discover',{query:'synthetic public query'}); return __calls.length===0 && __confirmations.length===2; })()")
            check('One approved assessment POST retains authorization and version', r'''(async()=>{ __approved=true; await mutate('assess',{candidate_id:Object.keys(project.items)[0]}); const posts=__calls.filter(c=>c.options.method==='POST'); const b=JSON.parse(posts[0].options.body); return posts.length===1 && b.authorize_external_request===true && b.expected_version===__saved.version && /^[a-f0-9-]{36}$/.test(b.request_id); })()''')
            check('Decision form preserves lineage and expected head', r'''(async()=>{__calls=[]; const f=document.querySelector('.project-decision-form'); f.querySelector('select').value='Defer'; f.querySelector('textarea').value='Synthetic browser test only'; f.onsubmit({preventDefault(){}}); while(busy) await new Promise(r=>setTimeout(r,10)); const posts=__calls.filter(c=>c.options.method==='POST'); const b=JSON.parse(posts[0].options.body), original=__saved.briefings[0]; return posts.length===1 && b.explicit_action==='record_project_decision' && b.briefing_sha256===original.record_sha256 && b.briefing_id===original.id && b.expected_head===__saved.decisions[0].id && b.expected_version===__saved.version && b.rationale==='Synthetic browser test only';})()''')
            check('Failed action is visible without an automatic retry', r'''(async()=>{__calls=[]; window.fetch=async(path,options)=>{__calls.push(path);return {ok:false,json:async()=>({message:'Synthetic failure. Reload saved history.'})};}; await action(()=>mutate('brief',{assessment_id:__saved.assessments[0].id})); return __calls.length===1 && document.querySelector('#status').dataset.state==='failed' && !document.querySelector('#workspace-body').inert;})()''')
            check('Pending action locks workspace and prevents double submission', r'''(async()=>{let release; let calls=0; const pending=action(()=>{calls++;return new Promise(r=>{release=r;});}); const locked=document.querySelector('#workspace-body').inert && document.querySelector('#status').dataset.state==='pending'; await action(()=>{calls++;}); release(); await pending; return locked && calls===1 && !document.querySelector('#workspace-body').inert;})()''')
            check('Capability notice handles search-only and assessment-only instances', "project=structuredClone(__saved); transports={search:true,assessment:false}; render(); const searchOnly=document.querySelector('#transport-note').textContent.includes('AI assessment is unavailable') && !document.querySelector('#discover button').disabled; transports={search:false,assessment:true}; render(); searchOnly && document.querySelector('#transport-note').textContent.includes('New discovery is unavailable') && document.querySelector('#discover button').disabled")
            check('Untrusted source text is rendered as text, not markup', "project=structuredClone(__saved); Object.values(project.items)[0].title='<img src=x onerror=alert(1)>'; render(); document.querySelector('.source-card h3').textContent==='<img src=x onerror=alert(1)>' && document.querySelector('.source-card img')===null")
            check('Stale briefing disables human decision form', "project=structuredClone(__saved); project.briefing_current[project.briefings[0].id]=false; render(); document.querySelector('.project-decision-form')===null && document.querySelector('.human-decision-panel').textContent.includes('Historical briefing')")
            check('Low and uncertain relevance stay out of the opportunity area', "['low relevance','uncertain relevance'].every(category=>{project=structuredClone(__saved);project.assessments[0].assessment.category=category;render();return document.querySelectorAll('#opportunities article').length===0 && document.querySelectorAll('#briefings .project-briefing').length===1;})")
            check('Future qualifying card maps saved fields without inferring a domain', r'''(()=>{project=structuredClone(__saved); const a=project.assessments[0].assessment, b=project.briefings[0]; a.category='potential relevance'; b.title='SYNTHETIC UI FIXTURE: qualifying capability'; b.why_it_matters='SYNTHETIC UI FIXTURE: a project needs structured outputs.'; b.potential_value='Hypothesis: If this synthetic capability fits the synthetic project, it could help organize output; the benefit is unverified.'; b.next_action='Review the synthetic fixture requirements.'; render(); const card=document.querySelector('#opportunities .selected-opportunity'); return card!==null && document.querySelector('#opportunity-empty').hidden && card.textContent.includes('Domain not recorded') && [...card.querySelectorAll(':scope>section p')].map(n=>n.textContent).join('|')===[b.why_it_matters,b.potential_value,b.next_action].join('|') && card.querySelector('.project-briefing').closest('details')!==null && document.querySelectorAll('#briefings .project-briefing').length===0;})()''')
            check('Stale and superseded potential evaluations are not opportunities', r'''(()=>{project.briefing_current[project.briefings[0].id]=false;render();const stale=document.querySelectorAll('#opportunities article').length===0;project.briefing_current[project.briefings[0].id]=true;const newer=structuredClone(project.assessments[0]);newer.id='synthetic-newer-assessment';newer.assessment.category='low relevance';project.assessments.push(newer);render();return stale && document.querySelectorAll('#opportunities article').length===0;})()''')
            check('Unbriefed assessments remain accessible without becoming opportunities', "project=structuredClone(__saved);project.briefings=[];project.decisions=[];render();document.querySelectorAll('.unbriefed-evaluation').length===1 && document.querySelectorAll('#opportunities article').length===0 && document.querySelector('#briefings').textContent.includes('no briefing is attached')")
            check('Empty saved project has honest empty states', "project=structuredClone(__saved); project.items={}; project.briefings=[]; project.assessments=[]; project.decisions=[]; project.operations={}; render(); document.querySelector('#sources').textContent.includes('No evidence saved yet') && document.querySelector('#briefings').textContent.includes('No previous evaluations') && !document.querySelector('#opportunity-empty').hidden")
            check('History summary accounts for pending reservations without inventing outcomes', "project=structuredClone(__saved); project.operations['synthetic-pending']={action:'assess',status:'started'}; renderHistory(); document.querySelector('#history-summary').textContent.includes('1 pending') && document.querySelector('#history').textContent.includes('Pending')")
            require_no_posts = all(method == 'GET' for method, _ in browser.request_log)
            assert require_no_posts and not browser.blocked_requests and browser.errors == 0
            assert json.dumps(saved, sort_keys=True) == before, 'Synthetic fixture was mutated'
            checks.append('All requests fulfilled offline; no provider calls, writes or browser exceptions')
            (OUT / 'checks.json').write_text(json.dumps({'passed':checks, 'requests':browser.request_log}, indent=2), encoding='utf-8')
        finally:
            if browser:
                try:
                    browser.call('Browser.close')
                except Exception:
                    pass
                browser.ws.close()
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)
    print(str(len(checks)) + ' focused browser checks passed.')


if __name__ == '__main__':
    main()
