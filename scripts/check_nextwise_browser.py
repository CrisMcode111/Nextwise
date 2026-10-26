"""Real Chrome browser checks via CDP. Test-only dependency: existing websocket-client."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import websocket

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/nextwise_demo/final'


class Browser:
    def __init__(self,ws):
        self.ws=websocket.create_connection(ws,timeout=150,suppress_origin=True)
        self.counter=0;self.fixture=None;self.api_id=None;self.errors=0
        self.allowed_origin=None;self.blocked_requests=[];self.request_log=[]

    def send(self,method,params=None):
        self.counter+=1
        self.ws.send(json.dumps({'id':self.counter,'method':method,'params':params or {}}))
        return self.counter

    def call(self,method,params=None):
        identity=self.send(method,params)
        while True:
            msg=json.loads(self.ws.recv())
            if msg.get('method')=='Fetch.requestPaused':
                request=msg['params']['request'];rid=msg['params']['requestId']
                if self.allowed_origin:
                    self.request_log.append((request['method'],request['url']))
                if self.allowed_origin and not request['url'].startswith(self.allowed_origin+'/'):
                    self.blocked_requests.append(request['url']);self.send('Fetch.failRequest',{'requestId':rid,'errorReason':'BlockedByClient'})
                elif self.fixture is not None:
                    self.send('Fetch.fulfillRequest',{'requestId':rid,
                        'responseCode':self.fixture['status'],
                        'responseHeaders':[{'name':'Content-Type','value':'application/json'}],
                        'body':base64.b64encode(json.dumps(self.fixture['body']).encode()).decode()})
                else:self.send('Fetch.continueRequest',{'requestId':rid})
            if msg.get('method')=='Network.responseReceived' and msg['params']['response']['url'].endswith('/api/load'):
                self.api_id=msg['params']['requestId']
            if msg.get('method')=='Runtime.exceptionThrown':self.errors+=1
            if msg.get('id')==identity:
                if 'error' in msg:raise RuntimeError('CDP command failed: '+method)
                return msg.get('result',{})

    def evaluate(self,js):
        result=self.call('Runtime.evaluate',{'expression':js,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in result:raise RuntimeError('Browser assertion/evaluation failed')
        return result['result'].get('value')

    def screenshot(self,name):
        data=self.call('Page.captureScreenshot',{'format':'png'})['data']
        (OUT/name).write_bytes(base64.b64decode(data))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    browser_profile=Path(tempfile.mkdtemp(prefix='nextwise-browser-'))
    chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
    process=subprocess.Popen([str(chrome),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                              '--remote-debugging-port=9223','--remote-debugging-address=127.0.0.1',
                              '--user-data-dir='+str(browser_profile),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'browser':'Installed Chrome, isolated temporary profile, headless CDP','checks':[]}
    def check(label,ok):
        report['checks'].append({'check':label,'passed':bool(ok)})
        (OUT/'browser_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        if not ok:
            report['failure_ui']=browser.evaluate('({state:document.querySelector("#state").textContent,contentHidden:document.querySelector("#content").hidden})')
            raise AssertionError(label)
        print('PASS: '+label,flush=True)
    browser=None
    try:
        for _ in range(30):
            try:
                pages=json.load(urllib.request.urlopen('http://127.0.0.1:9223/json',timeout=2));break
            except OSError:time.sleep(1)
        browser=Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
        browser.call('Page.enable');browser.call('Runtime.enable');browser.call('Network.enable')
        browser.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        browser.call('Page.navigate',{'url':'http://127.0.0.1:8765'})
        time.sleep(2)
        check('Local page title',browser.evaluate('document.title')=='Nextwise — From update to next step')
        if browser.evaluate('!document.querySelector("#content").hidden') is not True:
            browser.screenshot('initial_state.png')
        for attempt in range(120):
            ready=browser.evaluate('fetch("/api/status").then(r=>r.json()).then(d=>d.authenticated)')
            if ready:break
            if attempt%12==0:print('Waiting for private console key entry; no key enters the browser.',flush=True)
            time.sleep(3)
        check('Private console authentication available',ready)
        browser.evaluate('load(); true')
        saw_loading=False
        for _ in range(120):
            saw_loading |= bool(browser.evaluate('document.querySelector("#state").classList.contains("loading") && document.querySelector("#refresh").disabled'))
            if browser.evaluate('!document.querySelector("#content").hidden'):break
            time.sleep(2)
        check('Live investigation rendered',browser.evaluate('!document.querySelector("#content").hidden'))
        check('Clear loading state and disabled refresh',saw_loading)
        response=browser.call('Network.getResponseBody',{'requestId':browser.api_id})
        data=json.loads(response['body'])
        report['live_data']={'aggregate':data['aggregate'],'memory':data['diagnostics'],'case_count':len(data['cases']),
                             'claim_count':len(data['claims'])}
        check('Pilot evidence precedes collapsed project background',browser.evaluate('Array.from(document.querySelectorAll("section.section")).map(s=>s.id)')==['evidence','project','update'])
        check('Investigation question appears before project section',browser.evaluate('document.querySelector("#investigation-brief .brief-question").textContent')==data['investigation']['question'] and browser.evaluate('document.querySelector("#investigation-brief").compareDocumentPosition(document.querySelector("#project")) & Node.DOCUMENT_POSITION_FOLLOWING')==4)
        check('Concise next action is an excerpt of the saved proposal',browser.evaluate('document.querySelector(".next-summary").textContent')==data['recommendation']['recommended_next_step'].split(':')[0]+'.')
        check('Full original recommendation is available unchanged and initially collapsed',browser.evaluate('!document.querySelector("#original-recommendation").open && document.querySelector("#original-recommendation .copy").textContent')==data['recommendation']['recommended_next_step'])
        check('Recommendation review is separate from the human decision',browser.evaluate('document.querySelector("#investigation-brief").textContent.includes("Saved advice · For your review") && !document.querySelector("#investigation-brief").textContent.includes("Decision: not set")'))
        check('Distribution and licensing qualifications visible beside draft before expansion',browser.evaluate('Array.from(document.querySelectorAll(".claim-item")).filter(e=>!e.querySelector("details").open).map(e=>e.querySelector(".proposed-correction").textContent)')==[c['review']['proposed_wording'] for c in data['claims']])
        check('Displayed figures reconcile with live SQL',browser.evaluate('Array.from(document.querySelectorAll(".stat strong")).map(e=>e.textContent)')==[
            str(data['aggregate']['attempted_cases']),f"{data['aggregate']['schema_valid_cases']} / {data['aggregate']['attempted_cases']}",
            f"{data['aggregate']['quality_pass_cases']} / {data['aggregate']['attempted_cases']}",str(float(data['aggregate']['request_seconds']))+' s'])
        check('Every internal evidence link resolves',browser.evaluate('Array.from(document.querySelectorAll("a[href^=\\"#\\"]")).filter(a=>a.hash.length>1).every(a=>document.getElementById(a.hash.slice(1)))'))
        check('Source links resolve to saved URLs',browser.evaluate('Array.from(document.querySelectorAll(".source a[target] ")).map(a=>a.href)')==[s['requested_url'] for s in data['sources']])
        browser.screenshot('desktop.png')
        browser.evaluate('location.hash="#claim-0"; true');time.sleep(.5)
        check('Quotation link opens exact source quotation',browser.evaluate('document.getElementById("claim-0").open && document.querySelector("#claim-0 blockquote").textContent')==data['claims'][0]['exact_supporting_quote'])
        browser.screenshot('quotation.png')
        first=data['cases'][0]
        browser.evaluate('location.hash='+json.dumps('#case-'+first['fixture_id'])+'; true');time.sleep(.5)
        check('Pilot case opens original synthetic input and model output',browser.evaluate('({input:document.querySelector("#case-'+first['fixture_id']+' .text-input").textContent, output:document.querySelector("#case-'+first['fixture_id']+' pre").textContent})')=={'input':first['input'],'output':first['output']})
        check('Every pilot case has a fixture-derived comparison before raw JSON',browser.evaluate('Array.from(document.querySelectorAll("#pilot > .detail[id^=case-]")).map(e=>({rows:e.querySelectorAll(".comparison tbody tr").length,before:!!(e.querySelector(".comparison").compareDocumentPosition(e.querySelector("pre")) & Node.DOCUMENT_POSITION_FOLLOWING)}))')==[{'rows':len(c['comparison']['rows']),'before':True} for c in data['cases']])
        explicit=next(c for c in data['cases'] if c['fixture_id']=='synthetic-explicit')
        row_text=browser.evaluate('Object.fromEntries(Array.from(document.querySelectorAll("#case-synthetic-explicit .comparison tbody tr")).map(e=>[e.dataset.field,e.textContent]))')
        check('Explicit meal omission distinguished from preserved quantity meaning', 'Not returned' in row_text['meal'] and '"two" (string)' in row_text['people_count'] and '2 (number)' in row_text['people_count'] and any(q in row_text['people_count'] for q in next(r for r in explicit['comparison']['rows'] if r['field']=='people_count')['qualifications']))
        check('Explicit no-nuts output and conflicting time unknown are inspectable','"no nuts"' in row_text['excluded_food_category_as_stated'] and '20 (number)' in row_text['ready_within_minutes'] and 'Also listed as unknown: time_limit' in row_text['ready_within_minutes'])
        check('Extra unknown categories do not assert irrelevance or cause',browser.evaluate('document.querySelector("#case-synthetic-explicit").textContent.includes("does not establish that every extra category is irrelevant, or why it was returned")'))
        check('Original evaluator findings and quality flags remain unchanged',browser.evaluate('Array.from(document.querySelectorAll("#pilot > .detail[id^=case-]")).map(e=>JSON.parse(e.querySelectorAll("pre")[1].textContent))')==[c['validation'] for c in data['cases']])
        browser.screenshot('pilot_case.png')
        check('H-MEM persisted artifact retrieval demonstrated',bool(data['diagnostics']['memory_ids'].get('evaluation_results')) and bool(data['diagnostics']['manifest_id']))
        check('External HTML is rendered as inert text',browser.evaluate('(()=>{let e=el("p","","<img src=x onerror=alert(1)>");let ok=e.children.length===0 && e.textContent.includes("<img");return ok;})()'))
        browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        browser.evaluate('location.hash=""; window.scrollTo(0,0);true');time.sleep(.3)
        check('Mobile viewport has no horizontal overflow',browser.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        browser.screenshot('mobile.png')
        browser.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        for code,status in [('authentication',401),('memory',503),('empty',404),('integrity',409),('zetaris',503)]:
            browser.fixture={'status':status,'body':{'code':code,'message':'Browser test fixture: '+code}}
            browser.call('Fetch.enable',{'patterns':[{'urlPattern':'*/api/load','requestStage':'Request'}]})
            browser.evaluate('load()')
            check('Browser failure state: '+code,browser.evaluate('document.querySelector("#content").hidden && !document.querySelector("#state").hidden && document.querySelector("#state").textContent.includes("Browser test fixture")'))
        browser.screenshot('service_error.png')
        browser.fixture=None;browser.call('Fetch.disable')
        print('Reloading the real page after disabling CDP failure interception.',flush=True)
        # Tear down the explicitly intercepted test document before the real
        # recovery check; do not reuse its synthetic fetch responses or DOM.
        browser.call('Page.reload',{'ignoreCache':True})
        time.sleep(1)
        for _ in range(120):
            if browser.evaluate('!document.querySelector("#content").hidden'):break
            time.sleep(2)
        check('Fresh live recovery after browser failure fixtures',browser.evaluate('!document.querySelector("#content").hidden'))
        check('No uncaught browser JavaScript exceptions',browser.errors==0)
        report['status']='PASS'
    except Exception as error:
        report.update(status='FAIL',failure=type(error).__name__+': '+str(error))
        print(report['failure'],flush=True)
    finally:
        (OUT/'browser_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        if browser:browser.ws.close()
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill()
    print('Browser report: '+str(OUT/'browser_checks.json'),flush=True)
    return 0 if report.get('status')=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
