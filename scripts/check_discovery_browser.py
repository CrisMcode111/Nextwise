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
            chrome=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',f'--remote-debugging-port={DEBUG}','--remote-debugging-address=127.0.0.1','--user-data-dir='+str(Path(tmp)/'chrome'),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:pages=json.load(urllib.request.urlopen(f'http://127.0.0.1:{DEBUG}/json',timeout=1));break
                except OSError:time.sleep(.2)
            browser=Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
            browser.call('Page.enable');browser.call('Runtime.enable')
            browser.call('Page.navigate',{'url':f'http://127.0.0.1:{PORT}/'})
            check('Existing investigation renders with discovery controls',wait('typeof loading!=="undefined" && !loading && !content.hidden && !document.querySelector("#check-updates").disabled && !!document.querySelector("#discovery-scope summary")'))
            before=browser.evaluate('content.textContent')
            browser.evaluate('document.querySelector("#check-updates").click();true')
            check('Progress disables overlap and preserves investigation',browser.evaluate('discoveryBusy && document.querySelector("#check-updates").disabled && !content.hidden && content.textContent')==before)
            check('Second server-side check is rejected while running',browser.evaluate("fetch('/api/discovery/check',{method:'POST'}).then(r=>r.status)")==409)
            check('Initial inventory and low relevance shown',wait('!discoveryBusy && document.querySelector("#discovery-results").textContent.includes("Initial inventory") && document.querySelector("#discovery-results").textContent.includes("low relevance")'))
            reason='ISOLATED PROPOSAL <img src=x onerror=alert(1)>'
            browser.evaluate('document.querySelector("#discovery-results textarea").value='+json.dumps(reason)+';document.querySelector("#discovery-results form").requestSubmit();true')
            check('Explicit selection persists separate proposal as plain text',wait('document.querySelector("#discovery-results").textContent.includes("'+reason+'")') and browser.evaluate('document.querySelectorAll("#discovery-results img").length===0 && !content.hidden'))
            browser.evaluate('document.querySelector("#check-updates").click();true')
            check('Unchanged check announces no new content',wait('!discoveryBusy && document.querySelector("#discovery-results").textContent.includes("No new or changed readable content")'))
            check('Malformed selection rejected',browser.evaluate("fetch('/api/discovery/select',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.status)")==400)
            server.terminate();server.wait(timeout=10);server=start(root)
            browser.call('Page.reload',{'ignoreCache':True})
            check('Full process restart reopens proposal, baseline and existing investigation',wait('!loading && !content.hidden && document.querySelector("#discovery-results").textContent.includes("ISOLATED PROPOSAL")'))
            browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            check('Mobile discovery fits viewport',browser.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            check('No uncaught JavaScript errors',browser.errors==0)
        finally:
            if browser:browser.ws.close()
            for p in (server,chrome):
                if p and p.poll() is None:p.terminate();p.wait(timeout=10)
            time.sleep(1)

if __name__=='__main__':main()
