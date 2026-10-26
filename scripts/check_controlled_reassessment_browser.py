"""Read-only real-browser checks of a persisted controlled reassessment and original investigation."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

from check_nextwise_browser import Browser
import reassess_discovery_once as once
import semantic_discovery as semantic

OUT=once.OUT


def main():
    checks=[];browser=chrome=None
    OUT.mkdir(parents=True,exist_ok=True)
    def check(name,ok):
        checks.append({'check':name,'passed':bool(ok)})
        (OUT/'live_browser_checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not ok:raise AssertionError(name)
    def wait_loaded():
        for _ in range(120):
            if browser.evaluate('typeof loading!=="undefined" && !loading && !content.hidden && !!decisionState && !!document.querySelector("#discovery-results summary")'):return True
            time.sleep(.5)
        return False
    with tempfile.TemporaryDirectory(prefix='nextwise-controlled-browser-',ignore_cleanup_errors=True) as tmp:
        try:
            chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless=new',
                '--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=9227',
                '--remote-debugging-address=127.0.0.1','--user-data-dir='+tmp,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:
                    pages=json.load(urllib.request.urlopen('http://127.0.0.1:9227/json',timeout=1));break
                except OSError:time.sleep(.2)
            browser=Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
            browser.call('Page.enable');browser.call('Runtime.enable');browser.call('Network.enable')
            browser.call('Page.navigate',{'url':'http://127.0.0.1:8765/'})
            check('Authenticated investigation, genuine decision and discovery load together',wait_loaded())
            check('Connection confirms live data and linked H-MEM',browser.evaluate('document.querySelector("#connection").textContent.includes("Live data") && document.querySelector("#connection").textContent.includes("Memory linked")'))
            data=json.loads(browser.call('Network.getResponseBody',{'requestId':browser.api_id})['body'])
            check('Six Zetaris tables reconcile with eight original memory artifacts',len(data['diagnostics']['table_checks'])==6 and len(data['diagnostics']['memory_ids'])==8)
            check('Original pilot score and pending evidence review preserved',str(data['aggregate']['quality_pass_cases'])=='1' and str(data['aggregate']['attempted_cases'])=='4' and 'pending' in data['review']['approval']['status'])
            check('Genuine Defer Version 1 has no integrity warnings',browser.evaluate('decisionState.history.some(d=>d.choice==="Defer"&&d.version===1&&!d.needs_review)'))
            saved=browser.evaluate("fetch('/api/discovery').then(r=>r.json()).then(d=>d.discovery)")
            check('Original allowance remains three and separate allowance is one',semantic.request_accounting(saved)['requests_used']==3 and semantic.request_accounting(saved,once.AUTHORIZATION)['requests_used']==1)
            for cid in once.CANDIDATES:
                item=saved['items'][cid];record=item['semantic_assessment']
                check(cid+': active persisted assessment belongs to this authorization',record.get('authorization')==once.AUTHORIZATION)
                check(cid+': original failed assessment remains in history and cache',any(h.get('status')=='failed' and h.get('request_id')!=record['request_id'] for h in item['semantic_history']) and saved['semantic_cache'][record['base_cache_key']]['status']=='failed')
                title=json.dumps(item['title'])
                row='Array.from(document.querySelectorAll("#discovery-results details")).find(n=>n.querySelector(":scope > summary")?.textContent.startsWith('+title+'))'
                if record['status']!='validated':
                    missing=record.get('validation_failure',{}).get('missing_fields',[])
                    check(cid+': displays precise rejection, missing fields and uncertainty',browser.evaluate('('+row+').textContent.includes('+json.dumps(record['error'])+') && ('+row+').textContent.includes("uncertain relevance") && '+json.dumps(missing)+'.every(f=>('+row+').textContent.includes("Missing required fields: "+f))'))
                    check(cid+': failed evidence coverage remains visible and selection disabled',browser.evaluate('('+row+').textContent.includes('+json.dumps(record['provenance']['coverage']['description'])+') && ('+row+').querySelector("button[type=submit]").disabled'))
                    continue
                semantic.validate(record['assessment'],{'source':record['provenance']})
                check(cid+': exact evidence and source IDs validate',True)
                for field in ('project_need','source_observation','priority_reason','next_step'):
                    check(cid+': renders '+field,browser.evaluate('('+row+').textContent.includes('+json.dumps(record['assessment'][field])+')'))
                check(cid+': supporting quotes and coverage are rendered',browser.evaluate('('+row+').textContent.includes('+json.dumps(record['provenance']['coverage']['description'])+') && '+json.dumps([e['exact_quote'] for e in record['assessment']['evidence']])+'.every(q=>('+row+').textContent.includes(q))'))
                proposals=[p for p in saved['proposals'] if p.get('assessment_cache_key')==record['cache_key']]
                if record['assessment']['category']=='low relevance':
                    check(cid+': low relevance creates no unnecessary proposal',not proposals and browser.evaluate('('+row+').querySelector("button[type=submit]").disabled'))
                elif record['provenance']['existing_investigation']:
                    check(cid+': one unapproved continuation links existing investigation',len(proposals)==1 and proposals[0]['proposal_kind']=='existing_investigation_followup' and proposals[0]['existing_investigation_id']==semantic.INVESTIGATION and proposals[0]['human_approval'] is None)
                    check(cid+': continuation review action is available',browser.evaluate('!('+row+').querySelector("button[type=submit]").disabled'))
            browser.call('Page.reload',{'ignoreCache':True})
            check('Reload reopens combined view',wait_loaded())
            reopened=browser.evaluate("fetch('/api/discovery').then(r=>r.json()).then(d=>d.discovery)")
            check('Reload preserves active outcomes, proposals, baselines and source events',saved==reopened)
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
