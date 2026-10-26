"""Real Chrome + real HTTP + official H-MEM in isolated, labelled fixture storage.

Never sends a save to port 8765 or the real investigation storage.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

from check_nextwise_browser import Browser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from decision_fixture import app, call, initialize

OUT = ROOT / 'reports/decision_workflow'
PORT = 8767
DEBUG_PORT = 9224


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'storage': 'Isolated OS temporary directory; explicit test fixtures only',
              'browser': 'Installed Chrome, headless, isolated profile, real HTTP', 'checks': []}
    def check(label, value):
        report['checks'].append({'check': label, 'passed': bool(value)})
        (OUT / 'browser_checks.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(('PASS: ' if value else 'FAIL: ')+label, flush=True)
        if not value:
            diagnostic=browser.evaluate('({state:document.querySelector("#state")?.textContent,contentHidden:document.querySelector("#content")?.hidden,decisionError:typeof decisionError!=="undefined"?decisionError:null,loading:typeof loading!=="undefined"?loading:null})')
            print(json.dumps(diagnostic), flush=True)
            print(browser.evaluate('window.__fixture_fetch_errors||[]'), flush=True)
            print(browser.evaluate('''(async()=>{try{const r=await fetch('/api/load',{method:'POST'});const d=await r.json();if(!r.ok)return {status:r.status,code:d.code};try{render(d);return 'render succeeded';}catch(e){return {renderError:e.message};}}catch(e){return {fetchError:e.message};}})()'''), flush=True)
            report['failure_ui']=diagnostic
            (OUT / 'browser_checks.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
            raise AssertionError(label)
    def start(root):
        process = subprocess.Popen([sys.executable, str(ROOT/'tests/decision_fixture.py'), str(root), str(PORT)],
                                   cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{PORT}/', timeout=1).close()
                return process
            except OSError: time.sleep(.2)
        process.terminate(); raise RuntimeError('Isolated fixture server failed to launch')
    def wait(js, timeout=40):
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            if browser.evaluate('typeof decisionState!=="undefined" && ('+js+')'): return True
            time.sleep(.2)
        return False
    browser = process = chrome = None
    with tempfile.TemporaryDirectory(prefix='nextwise-human-decision-') as temporary:
        root = Path(temporary)/'memory'
        initialize(root)
        profile = Path(temporary)/'chrome'
        try:
            process = start(root)
            chrome = subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe', '--headless=new',
                '--disable-gpu', '--no-first-run', '--no-default-browser-check',
                '--disable-background-networking','--disable-component-update','--disable-sync',
                '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost',
                f'--remote-debugging-port={DEBUG_PORT}', '--remote-debugging-address=127.0.0.1',
                '--user-data-dir='+str(profile), 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(40):
                try:
                    pages = json.load(urllib.request.urlopen(f'http://127.0.0.1:{DEBUG_PORT}/json', timeout=1)); break
                except OSError: time.sleep(.3)
            browser = Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
            browser.allowed_origin=f'http://127.0.0.1:{PORT}'
            browser.call('Fetch.enable',{'patterns':[{'urlPattern':'*','requestStage':'Request'}]})
            browser.call('Page.enable'); browser.call('Runtime.enable')
            browser.call('Page.addScriptToEvaluateOnNewDocument', {'source': '''window.__fixture_fetch_errors=[];const originalFetch=window.fetch;window.fetch=async function(...args){try{const response=await originalFetch(...args);const originalJson=response.json.bind(response);response.json=async()=>{try{return await originalJson();}catch(e){window.__fixture_fetch_errors.push('JSON: '+e.message);throw e;}};return response;}catch(e){window.__fixture_fetch_errors.push('fetch: '+e.message);throw e;}};'''})
            browser.call('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
            browser.call('Page.navigate', {'url':f'http://127.0.0.1:{PORT}'})
            check('All three sections load against labelled offline SQL fixtures and official H-MEM',
                  wait('!loading && !discoveryReading && !discoveryBusy && !!decisionState && !content.hidden') and browser.evaluate('content.textContent.includes("ISOLATED TEST FIXTURE") && document.querySelectorAll("section.section").length===3'))
            check('No default choice; save requires both choice and rationale', browser.evaluate('!document.querySelector("input[name=decision-choice]:checked") && document.querySelector("#save-decision").disabled'))
            check('Brief and decision precede the pilot, background and discovery',browser.evaluate('(()=>{const before=(a,b)=>!!(document.querySelector(a).compareDocumentPosition(document.querySelector(b))&Node.DOCUMENT_POSITION_FOLLOWING);return before("#investigation-brief","#evidence")&&before("#pilot","#project-background")&&before("#content","#discovery")&&!!document.querySelector("#investigation-brief #decision-panel");})()'))
            check('No saved decision is invented before history contains a record',browser.evaluate('decisionPanel.textContent.includes("No human decision has been recorded")&&!decisionPanel.textContent.includes("Recorded human decision: Defer")'))
            check('Background, detailed evidence, histories and diagnostics start collapsed',browser.evaluate('["project-background","publisher-claims","remaining-questions","recommendation-review","original-recommendation","diagnostics","decision-history"].every(id=>!document.getElementById(id).open)'))
            for attempt in range(2):
                browser.call('Page.reload', {'ignoreCache':True})
                check(f'Clean reload {attempt+1} receives complete response bodies', wait('!loading && !discoveryReading && !discoveryBusy && !!decisionState && !content.hidden'))
            rationale = 'ISOLATED BROWSER TEST ONLY — "two"\n<img src=x onerror=alert(1)> & café'
            browser.evaluate('document.querySelector("input[value=Defer]").click(); true')
            check('Choice alone cannot save', browser.evaluate('document.querySelector("#save-decision").disabled'))
            browser.evaluate('document.querySelector("#decision-rationale").value='+json.dumps(rationale)+';document.querySelector("#decision-rationale").dispatchEvent(new Event("input",{bubbles:true}));true')
            check('Typing never persists', len(call(root, 'decision_history')['history'])==0)
            browser.evaluate('document.querySelector("#decision-next-action").value="ISOLATED RECONSIDERATION DRAFT";document.querySelector("#decision-next-action").dispatchEvent(new Event("input",{bubbles:true}));load().then(()=>true)')
            check('Investigation refresh preserves exact choice, rationale and next-action drafts',wait('!loading&&!discoveryReading&&!discoveryBusy&&!!decisionContext') and browser.evaluate('({choice:document.querySelector("input[name=decision-choice]:checked")?.value,rationale:document.querySelector("#decision-rationale").value,next:document.querySelector("#decision-next-action").value})')=={'choice':'Defer','rationale':rationale,'next':'ISOLATED RECONSIDERATION DRAFT'} and len(call(root,'decision_history')['history'])==0)
            browser.evaluate('location.hash="#claim-0";true')
            check('Evidence navigation opens nested quotation and its collapsed parent',wait('document.querySelector("#claim-0").open&&document.querySelector("#publisher-claims").open'))
            browser.evaluate('location.hash="#update";true')
            check('Existing background navigation expands its ancestor',wait('document.querySelector("#project-background").open'))
            browser.evaluate('location.hash="#investigation-brief";true')
            # Real server-side failure, not a fabricated HTTP success response.
            lock = root/app.INVESTIGATION/'nextwise.lock'; lock.write_text('ISOLATED BROWSER TEST OWNED LOCK')
            browser.evaluate('document.querySelector("#save-decision").click();true')
            check('Save waits for confirmation and prevents concurrent edits', browser.evaluate('decisionSaving && document.querySelector("#decision-rationale").disabled && document.querySelector("#refresh").disabled'))
            check('Failed save keeps exact typed rationale and offers retry, without success',
                  wait('!decisionSaving && !!decisionError') and browser.evaluate('document.querySelector("#decision-rationale").value')==rationale and not browser.evaluate('!!decisionMessage'))
            lock.unlink()
            # Double submit in one event turn must produce one durable decision.
            browser.evaluate('document.querySelector("#decision-form").requestSubmit();saveDecision({preventDefault(){}});true')
            check('Explicit retry succeeds; double submission creates one record',
                  wait('!decisionSaving && decisionState.history.length===1') and len(call(root, 'decision_history')['history'])==1)
            check('Stored rationale is plain text with exact quotes, newlines and Unicode',
                  browser.evaluate('document.querySelector(".saved-decision .human-text").textContent')==rationale and browser.evaluate('document.querySelectorAll(".saved-decision img,.saved-decision script").length===0'))
            check('Confirmed history supplies recorded Defer Version 1 separately from saved advice',browser.evaluate('decisionPanel.textContent.includes("Recorded human decision: Defer · Version 1")&&document.querySelector("#investigation-brief").textContent.includes("Saved advice · For your review")&&!document.querySelector("#investigation-brief").textContent.includes("Decision: not set")'))
            check('Evidence links retrieve exact referenced artifacts as text/plain', browser.evaluate('''(async()=>{const links=[...document.querySelectorAll('#decision-panel > .saved-decision .decision-reference a')];if(links.length!==8)return false;for(const a of links){if(!a.getAttribute('href'))return false;const r=await fetch(a.href);const d=await r.json();if(!r.ok||!r.headers.get('Content-Type').startsWith('text/plain')||!d.reference.sha256||!d.artifact)return false;}return true;})()'''))
            browser.call('Page.reload', {'ignoreCache':True})
            check('Page reload recovers saved rationale from H-MEM', wait('!loading && !discoveryReading && !discoveryBusy && !!decisionState && decisionState.history.length===1') and browser.evaluate('document.querySelector(".saved-decision .human-text").textContent')==rationale)
            browser.evaluate('document.querySelector("#amend-decision").click();true')
            check('Amendment starts with no selected choice', browser.evaluate('!document.querySelector("input[name=decision-choice]:checked")'))
            browser.evaluate('document.querySelector("input[value=Test]").click();document.querySelector("#decision-rationale").value="ISOLATED AMENDMENT ONLY";document.querySelector("#decision-rationale").dispatchEvent(new Event("input",{bubbles:true}));document.querySelector("#decision-next-action").value="Fixture reconsideration condition";document.querySelector("#decision-next-action").dispatchEvent(new Event("input",{bubbles:true}));document.querySelector("#save-decision").click();true')
            check('Amendment adds version two and keeps original version accessible', wait('!decisionSaving && decisionState.history.length===2') and browser.evaluate('document.querySelector("#decision-history").textContent.includes("Version 1") && document.querySelector("#decision-history").textContent.includes("ISOLATED AMENDMENT ONLY")'))
            check('Decision presentation follows the new persisted head instead of hardcoding Defer',browser.evaluate('decisionPanel.textContent.includes("Recorded human decision: Test · Version 2")'))
            process.terminate(); process.wait(timeout=10); process = start(root)
            browser.call('Page.reload', {'ignoreCache':True})
            check('Full Python and Node process restart recovers both versions and evidence links', wait('!loading && !discoveryReading && !discoveryBusy && !!decisionState && decisionState.history.length===2') and browser.evaluate('decisionState.history[0].rationale')==rationale)
            browser.call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            check('Decision panel fits mobile viewport', browser.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            process.terminate(); process.wait(timeout=10)
            statefile = root/app.INVESTIGATION/'state.json'
            state = json.loads(statefile.read_text(encoding='utf-8'))
            ref = call(root, 'decision_history')['history'][0]['evidence_references'][0]
            state['records'] = [r for r in state['records'] if r['id']!=ref['memory_id']]
            statefile.write_text(json.dumps(state), encoding='utf-8')
            process = start(root); browser.call('Page.reload', {'ignoreCache':True})
            check('Missing evidence visibly flags saved decisions without changing choice or rationale',
                  wait('!loading && !!decisionState && decisionState.history.length===2 && decisionState.history.every(d=>d.needs_review)') and browser.evaluate('decisionPanel.textContent.includes("Needs review") && decisionState.history[0].choice==="Defer"') and browser.evaluate('decisionState.history[0].rationale')==rationale)
            check('Evidence failure blocks new saves while preserving decision history', browser.evaluate('content.hidden && !decisionContext && document.querySelector("#decision-history")!==null'))
            check('No uncaught browser JavaScript errors', browser.errors==0)
            check('No non-fixture network requests are allowed',not browser.blocked_requests and all(url.startswith(browser.allowed_origin+'/') for _,url in browser.request_log))
        finally:
            if browser: browser.ws.close()
            if process and process.poll() is None: process.terminate(); process.wait(timeout=10)
            if chrome and chrome.poll() is None: chrome.terminate(); chrome.wait(timeout=10)
            time.sleep(1)  # Let Chrome release temporary profile handles.


if __name__ == '__main__': main()
