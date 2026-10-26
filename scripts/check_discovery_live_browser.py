"""Read-only real-app browser verification; never submits a decision/proposal or fetches sources."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
from check_nextwise_browser import Browser

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/update_discovery/semantic_assessment'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    checks=[];browser=chrome=None
    def check(label,ok):
        checks.append({'check':label,'passed':bool(ok)})
        (OUT/'live_browser_checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
        print(('PASS ' if ok else 'FAIL ')+label,flush=True)
        if not ok:
            print(browser.evaluate('({connection:document.querySelector("#connection")?.textContent,contentHidden:document.querySelector("#content")?.hidden,state:document.querySelector("#state")?.textContent,discoveryStatus:document.querySelector("#discovery-status")?.textContent,hasDecisionState:typeof decisionState!=="undefined"&&!!decisionState})'),flush=True)
            raise AssertionError(label)
    def wait(js):
        for _ in range(180):
            if browser.evaluate('typeof loading!=="undefined" && ('+js+')'):return True
            time.sleep(.5)
        return False
    with tempfile.TemporaryDirectory(prefix='nextwise-live-relevance-',ignore_cleanup_errors=True) as tmp:
        try:
            chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=9227','--remote-debugging-address=127.0.0.1','--user-data-dir='+tmp,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:pages=json.load(urllib.request.urlopen('http://127.0.0.1:9227/json',timeout=1));break
                except OSError:time.sleep(.2)
            browser=Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
            browser.call('Page.enable');browser.call('Runtime.enable');browser.call('Network.enable')
            browser.call('Page.navigate',{'url':'http://127.0.0.1:8765/'})
            check('Authenticated live investigation and discovery load together',wait('!loading && !content.hidden && !!decisionState && !!document.querySelector("#discovery-results summary")'))
            check('Connection displays live data and memory linked',browser.evaluate('document.querySelector("#connection").textContent.includes("Live data") && document.querySelector("#connection").textContent.includes("Memory linked")'))
            data=json.loads(browser.call('Network.getResponseBody',{'requestId':browser.api_id})['body'])
            check('All six live tables reconcile with eight original H-MEM artifacts',len(data['diagnostics']['table_checks'])==6 and len(data['diagnostics']['memory_ids'])==8)
            check('Original pilot score and pending review unchanged',str(data['aggregate']['quality_pass_cases'])=='1' and str(data['aggregate']['attempted_cases'])=='4' and 'pending' in data['review']['approval']['status'])
            check('Genuine Defer Version 1 reopens without review warnings',browser.evaluate('decisionState.history.some(d=>d.version===1 && d.choice==="Defer" && !d.needs_review) && document.querySelector("#decision-panel").textContent.includes("Version 1")'))
            saved=browser.evaluate("fetch('/api/discovery').then(r=>r.json()).then(d=>d.discovery)")
            check('Every candidate has an explicit semantic outcome, not a rule-based substitute',all(i.get('semantic_assessment',{}).get('policy_version')=='nemotron-grounded-discovery-v1' and i['semantic_assessment']['status'] in ('validated','failed') for i in saved['items'].values()))
            ambiguous=[i for i in saved['items'].values() if any({'extraction','deployment'} <= {t for m in h['assessment'].get('matches',[]) for t in m.get('terms',[])} for h in i.get('relevance_history',[]))]
            check('Ambiguous candidate remains uncertain after its failed assessment, with no invented hypothesis',bool(ambiguous) and all(i['semantic_assessment']['category']=='uncertain relevance' and i['semantic_assessment']['assessment'] is None for i in ambiguous))
            check('Earlier assessments remain available separately from source revisions',all(len(i['relevance_history'])>=2 and i['relevance_history'][0]['policy_version']=='legacy-keywords-v1' for i in saved['items'].values()))
            check('Agent questions, hypotheses, limitations, provenance and visible failures are shown',browser.evaluate('["Project need","Supporting passage and provenance","Limitations","Proposed investigation question","Proposed next step","Model request or response failed"].every(t=>document.querySelector("#discovery-results").textContent.includes(t))'))
            import semantic_discovery as semantic
            validated=[i['semantic_assessment'] for i in saved['items'].values() if i['semantic_assessment']['status']=='validated']
            for record in validated:semantic.validate(record['assessment'],{'source':record['provenance']})
            check(f'{len(validated)} live assessments pass exact-source/quotation validation',bool(validated))
            check('Agent proposals are persisted before any human selection and approval remains separate',len([p for p in saved['proposals'] if p.get('origin')=='agent'])==len(validated) and all(p['human_approval'] is None for p in saved['proposals'] if p.get('origin')=='agent'))
            check('Optional notes replace the mandatory rationale field',browser.evaluate('Array.from(document.querySelectorAll("#discovery-results textarea")).every(n=>!n.required) && document.querySelector("#discovery-results").textContent.includes("Optional user note") && !document.querySelector("#discovery-results").textContent.includes("Why investigate this candidate?")'))
            check('All existing-investigation sources are linked to findings without duplicate proposals',sum(i['semantic_assessment']['provenance']['existing_investigation'] for i in saved['items'].values())==3 and browser.evaluate('document.querySelector("#discovery-results").textContent.includes("No duplicate investigation is proposed")'))
            check('Actual three-request authorization is recorded with returned-model usage',len(saved.get('semantic_requests',[]))==3 and all('nemotron' in r['model']['returned_model'] and r['model']['usage'].get('total_tokens',0)>0 for r in saved['semantic_requests']))
            browser.call('Page.reload',{'ignoreCache':True})
            check('Reload recovers live investigation, discovery and genuine decision',wait('!loading && !content.hidden && !!decisionState && decisionState.history.some(d=>d.version===1&&d.choice==="Defer") && !!document.querySelector("#discovery-results summary")'))
            reopened=browser.evaluate("fetch('/api/discovery').then(r=>r.json()).then(d=>d.discovery)")
            check('Reopen preserves proposals, source events and assessment checkpoints exactly',saved==reopened)
            browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            check('Combined live view fits mobile viewport',browser.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            check('No uncaught browser JavaScript errors',browser.errors==0)
        finally:
            if browser:
                try:browser.call('Browser.close')
                except Exception:pass
                browser.ws.close()
            if chrome and chrome.poll() is None:
                try:chrome.wait(timeout=5)
                except subprocess.TimeoutExpired:chrome.terminate();chrome.wait(timeout=10)

if __name__=='__main__':main()
