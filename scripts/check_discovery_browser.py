"""Real Chrome and HTTP, isolated fixture discovery, including full process restart."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from check_nextwise_browser import Browser

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/update_discovery'
PORT=8768
DEBUG=9226

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    checks=[]
    def check(label,ok):
        checks.append({'check':label,'passed':bool(ok)})
        (OUT/'browser_checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
        print(('PASS ' if ok else 'FAIL ')+label,flush=True)
        if not ok:
            print(browser.evaluate('({status:document.querySelector("#discovery-status")?.textContent,busy:discoveryBusy,disabled:document.querySelector("#check-updates")?.disabled})'),flush=True)
            print(browser.evaluate("fetch('/api/discovery').then(r=>r.json()).then(d=>({status:d.status,runs:d.discovery?.runs.map(r=>({status:r.status,events:r.events,errors:r.sources.map(s=>s.error)}))}))"),flush=True)
            raise AssertionError(label)
    def start(root):
        p=subprocess.Popen([sys.executable,str(ROOT/'tests/discovery_fixture.py'),str(root),str(PORT)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,cwd=ROOT)
        for _ in range(100):
            try:urllib.request.urlopen(f'http://127.0.0.1:{PORT}/',timeout=1).close();return p
            except OSError:time.sleep(.2)
        p.terminate();raise RuntimeError('Fixture startup failed')
    def wait(js):
        for _ in range(150):
            if browser.evaluate('typeof loading!=="undefined" && ('+js+')'):return True
            time.sleep(.2)
        return False
    browser=server=chrome=None
    with tempfile.TemporaryDirectory(prefix='nextwise-discovery-browser-') as tmp:
        root=Path(tmp)/'memory'
        try:
            server=start(root)
            chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--disable-background-networking','--disable-component-update','--disable-sync',
                '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost',
                f'--remote-debugging-port={DEBUG}','--remote-debugging-address=127.0.0.1','--user-data-dir='+str(Path(tmp)/'chrome'),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:pages=json.load(urllib.request.urlopen(f'http://127.0.0.1:{DEBUG}/json',timeout=1));break
                except OSError:time.sleep(.2)
            browser=Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
            browser.allowed_origin=f'http://127.0.0.1:{PORT}'
            browser.call('Fetch.enable',{'patterns':[{'urlPattern':'*','requestStage':'Request'}]})
            browser.call('Page.enable');browser.call('Runtime.enable')
            browser.call('Page.navigate',{'url':f'http://127.0.0.1:{PORT}/'})
            check('Existing investigation renders with discovery controls',wait('typeof loading!=="undefined" && !loading && !content.hidden && !document.querySelector("#check-updates").disabled && !!document.querySelector("#discovery-scope summary")'))
            browser.evaluate('document.querySelector("nav a[href=\\"#update\\"]").click();true')
            check('Background navigation opens its collapsed ancestor',wait('document.querySelector("#project-background").open'))
            browser.evaluate('document.querySelector("#project-background > summary").click();document.querySelector("nav a[href=\\"#update\\"]").click();true')
            check('Repeated same-hash navigation reopens a manually closed disclosure',wait('document.querySelector("#project-background").open'))
            browser.evaluate('document.querySelector("nav a[href=\\"#investigation-brief\\"]").click();true')
            before=browser.evaluate('content.textContent')
            browser.evaluate('document.querySelector("#check-updates").click();true')
            check('Progress disables overlap and preserves investigation',browser.evaluate('discoveryBusy && document.querySelector("#check-updates").disabled && !content.hidden && content.textContent')==before)
            check('Second server-side check is rejected while running',browser.evaluate("fetch('/api/discovery/check',{method:'POST'}).then(r=>r.status)")==409)
            check('Initial inventory and semantic uncertainty shown',wait('!discoveryBusy && document.querySelector("#discovery-results").textContent.includes("Initial inventory") && document.querySelector("#discovery-results").textContent.includes("uncertain relevance")'))
            check('Agent proposals are prepared before human selection',browser.evaluate("fetch('/api/discovery').then(r=>r.json()).then(d=>d.discovery.proposals.filter(p=>p.origin==='agent').length===5 && !d.discovery.proposal_selections?.length)"))
            check('Candidates, unapproved proposals and discovery diagnostics start collapsed',browser.evaluate('["discovery-inventory","discovery-proposals","discovery-diagnostics"].every(id=>!document.getElementById(id).open)&&document.querySelector("#discovery-results").textContent.includes("5 uncertain")&&document.querySelector("#discovery-proposals > summary").textContent.includes("not approved")'))
            browser.evaluate('fetch("/api/discovery").then(r=>r.json()).then(d=>{window.__savedDiscoveryView=d;const view=JSON.parse(JSON.stringify(d)),item=Object.values(view.discovery.items)[0];item.semantic_assessment={...item.semantic_assessment,status:"failed",error:"ISOLATED semantic failure",validation_failure:{code:"assessment_schema",field:"assessment",missing_fields:["source_observation"]}};paintDiscovery(view);return true;})')
            check('Failure counts stay visible while detailed failures are collapsed',browser.evaluate('document.querySelector("#discovery-results > .notice").textContent.includes("1 failed assessments")&&!document.querySelector("#discovery-inventory").open&&document.querySelector("#discovery-results").textContent.includes("ISOLATED semantic failure")'))
            browser.evaluate('document.querySelector("#discovery-inventory > summary").click();document.querySelector("#discovery-inventory .detail-body > details > summary").click();true')
            check('Expanding failed candidate reveals its exact error, missing field and disabled action',browser.evaluate('(()=>{const row=document.querySelector("#discovery-inventory .detail-body > details");return row.open&&row.textContent.includes("ISOLATED semantic failure")&&row.textContent.includes("source_observation")&&row.querySelector("button[type=submit]").disabled;})()'))
            browser.evaluate('paintDiscovery(window.__savedDiscoveryView);true')
            request_count=len(browser.request_log)
            browser.evaluate('document.querySelector("#discovery-proposals > summary").click();document.querySelector("#discovery-diagnostics > summary").click();true')
            check('Disclosure toggles make no requests',len(browser.request_log)==request_count)
            check('Candidate source metadata and assessment/revision histories remain collapsed',browser.evaluate('Array.from(document.querySelectorAll("#discovery-inventory .detail-body > details:first-child > .detail-body > details")).every(n=>!n.open)'))
            check('User note is optional and agent supplies question/next step',browser.evaluate('!document.querySelector("#discovery-results textarea").required && document.querySelector("#discovery-results").textContent.includes("Proposed investigation question") && document.querySelector("#discovery-results").textContent.includes("Proposed next step")'))
            browser.evaluate('document.querySelector("#discovery-results form").requestSubmit();true')
            check('Selection succeeds with no rationale or note',wait('document.querySelector("#discovery-results").textContent.includes("Selected for review")') and browser.evaluate("fetch('/api/discovery').then(r=>r.json()).then(d=>d.discovery.proposal_selections[0].user_note===null && d.discovery.proposal_selections[0].approval===null)"))
            reason='ISOLATED PROPOSAL <img src=x onerror=alert(1)>'
            browser.evaluate('(()=>{const row=document.querySelectorAll("#discovery-inventory > .detail-body > details")[1];row.querySelector("summary").click();const note=row.querySelector("textarea");note.value='+json.dumps(reason)+';note.dispatchEvent(new Event("input",{bubbles:true}));return true;})()')
            browser.evaluate('readDiscovery().then(()=>true)')
            check('Reopening discovery preserves the exact optional-note draft and expanded candidate',browser.evaluate('document.querySelectorAll("#discovery-results textarea")[1].value')==reason and browser.evaluate('document.querySelector("#discovery-inventory").open&&document.querySelectorAll("#discovery-inventory > .detail-body > details")[1].open'))
            browser.evaluate('document.querySelectorAll("#discovery-results form")[1].requestSubmit();true')
            check('Explicit selection persists separate proposal as plain text',wait('document.querySelector("#discovery-results").textContent.includes("'+reason+'")') and browser.evaluate('document.querySelectorAll("#discovery-results img").length===0 && !content.hidden'))
            browser.evaluate('document.querySelector("#check-updates").click();true')
            check('Unchanged check announces no new content',wait('!discoveryBusy && document.querySelector("#discovery-results").textContent.includes("No new or changed readable content")'))
            check('Malformed selection rejected',browser.evaluate("fetch('/api/discovery/select',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.status)")==400)
            browser.evaluate('Array.from(document.querySelectorAll("#discovery-inventory button")).find(b=>b.textContent==="Prepare opportunity briefing").click();true')
            check('Validated fixture assessment prepares a persisted opportunity briefing',wait('!opportunityBusy && document.querySelector("#opportunities").textContent.includes("Agent recommendation: Defer")'))
            check('Opportunity is prominent, scoped and has collapsed evidence/history',browser.evaluate('document.querySelector("#opportunities").compareDocumentPosition(document.querySelector("#content")) & Node.DOCUMENT_POSITION_FOLLOWING && document.querySelector("#opportunities").textContent.includes("No practical benefit is established") && Array.from(document.querySelectorAll("#opportunities details")).every(d=>!d.open)'))
            browser.evaluate('(()=>{const form=document.querySelector(".opportunity-decision"),t=form.querySelector("textarea");t.value="ISOLATED OPPORTUNITY DECISION <img src=x onerror=alert(1)>";t.dispatchEvent(new Event("input"));return true;})()')
            browser.evaluate('readDiscovery().then(()=>true)')
            check('Opportunity draft survives discovery redraw without choosing a default',browser.evaluate('document.querySelector(".opportunity-decision textarea").value.includes("ISOLATED OPPORTUNITY") && document.querySelector(".opportunity-decision select").value===""'))
            browser.evaluate('document.querySelector(".opportunity-decision").requestSubmit();true')
            check('Missing human choice is rejected and draft stays intact',wait('!opportunityBusy && document.querySelector(".opportunity-decision").textContent.includes("no longer valid")') and browser.evaluate('document.querySelector(".opportunity-decision textarea").value.includes("ISOLATED OPPORTUNITY")'))
            browser.evaluate('(()=>{const s=document.querySelector(".opportunity-decision select");s.value="Reject";s.dispatchEvent(new Event("change"));document.querySelector(".opportunity-decision").requestSubmit();return true;})()')
            check('Explicit human choice differs from recommendation and is confirmed persisted',wait('!opportunityBusy && document.querySelector("#opportunities").textContent.includes("Recorded human opportunity decision: Reject")'))
            check('Decision text renders safely, provenance and original investigation remain accessible',browser.evaluate('document.querySelector("#opportunities").textContent.includes("ISOLATED OPPORTUNITY DECISION <img") && !document.querySelector("#opportunities img") && !content.hidden && !!document.querySelector("#opportunities details")'))
            browser.evaluate('fetch("/api/discovery").then(r=>r.json()).then(d=>{const view=JSON.parse(JSON.stringify(d.opportunities));view[0].recommendation.id="ISOLATED-DISPLAY-ONLY-NEWER-BRIEFING";paintOpportunities(view);return true;})')
            check('Earlier human decision is not presented as approval of a newer briefing',browser.evaluate('document.querySelector("#opportunities").textContent.includes("That decision belongs to an earlier briefing") && document.querySelector("#opportunities").textContent.includes("pending your review")'))
            browser.evaluate('readDiscovery().then(()=>true)')
            server.terminate();server.wait(timeout=10);server=start(root)
            browser.call('Page.reload',{'ignoreCache':True})
            check('Full process restart reopens proposal, baseline and existing investigation',wait('!loading && !content.hidden && document.querySelector("#discovery-results").textContent.includes("ISOLATED PROPOSAL")'))
            check('Full process restart reopens opportunity recommendation and human decision',wait('document.querySelector("#opportunities").textContent.includes("Recorded human opportunity decision: Reject") && document.querySelector("#opportunities").textContent.includes("Agent recommendation: Defer")'))
            browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            check('Mobile discovery fits viewport',browser.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            check('No uncaught JavaScript errors',browser.errors==0)
            check('Only the isolated fixture origin was requested',not browser.blocked_requests and all(url.startswith(browser.allowed_origin+'/') for _,url in browser.request_log))
        finally:
            if browser:browser.ws.close()
            for p in (server,chrome):
                if p and p.poll() is None:p.terminate();p.wait(timeout=10)
            time.sleep(1)

if __name__=='__main__':main()
