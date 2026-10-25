"""Read-only live browser smoke check. Never submits or fills a decision."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

from check_nextwise_browser import Browser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/decision_workflow'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'checked_at_utc':datetime.now(timezone.utc).isoformat(),
              'mode':'Real live Zetaris and official H-MEM; read only, no decision submission', 'checks':[]}
    def check(label, value):
        report['checks'].append({'check':label,'passed':bool(value)})
        (OUT/'live_browser_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(('PASS: ' if value else 'FAIL: ')+label, flush=True)
        if not value: raise AssertionError(label)
    browser = process = None
    with tempfile.TemporaryDirectory(prefix='nextwise-read-only-browser-') as temporary:
        try:
            process = subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe', '--headless=new',
                '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=9225',
                '--remote-debugging-address=127.0.0.1', '--user-data-dir='+temporary, 'about:blank'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(30):
                try:
                    pages=json.load(urllib.request.urlopen('http://127.0.0.1:9225/json',timeout=1));break
                except OSError:time.sleep(.3)
            browser=Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
            browser.call('Page.enable');browser.call('Runtime.enable');browser.call('Network.enable')
            browser.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
            browser.call('Page.navigate',{'url':'http://127.0.0.1:8765'})
            end=time.monotonic()+90
            while time.monotonic()<end:
                if browser.evaluate('typeof decisionState!=="undefined" && !loading && !!decisionState && !content.hidden'):break
                time.sleep(.5)
            check('Live investigation loads with all three sections and confirmed decision history',browser.evaluate('!content.hidden && document.querySelectorAll("section.section").length===3 && !!decisionState'))
            data=json.loads(browser.call('Network.getResponseBody',{'requestId':browser.api_id})['body'])
            check('Real investigation remains undecided with no preselected choice or typed fixture text', browser.evaluate('decisionState.history.length===0 && !document.querySelector("input[name=decision-choice]:checked") && document.querySelector("#decision-rationale").value==="" && document.querySelector("#save-decision").disabled'))
            check('Human panel appears beside original pending AI proposal',browser.evaluate('!!document.querySelector(".brief-columns > #decision-panel") && document.querySelector(".brief-next").textContent.includes("Pending approval") && document.querySelector(".brief-next").textContent.includes("Original investigation")'))
            check('All six live tables and official H-MEM lineage reconciled',len(data['diagnostics']['table_checks'])==6 and bool(data['diagnostics']['manifest_id']) and len(data['diagnostics']['memory_ids'])==8)
            check('Original decision and review approval remain unchanged',data['investigation']['decision'] is None and 'pending' in data['review']['approval']['status'])
            check('Saved pilot score remains 1 of 4',str(data['aggregate']['quality_pass_cases'])=='1' and str(data['aggregate']['attempted_cases'])=='4')
            check('Existing internal evidence links resolve',browser.evaluate('Array.from(document.querySelectorAll("a[href^=\\"#\\"]")).filter(a=>a.hash.length>1).every(a=>document.getElementById(a.hash.slice(1)))'))
            (OUT/'live_desktop.png').write_bytes(base64.b64decode(browser.call('Page.captureScreenshot',{'format':'png'})['data']))
            browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            check('Live mobile layout has no horizontal overflow',browser.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            (OUT/'live_mobile.png').write_bytes(base64.b64decode(browser.call('Page.captureScreenshot',{'format':'png'})['data']))
            check('No uncaught browser JavaScript errors',browser.errors==0)
        finally:
            if browser:browser.ws.close()
            if process and process.poll() is None:process.terminate();process.wait(timeout=10)
            time.sleep(1)


if __name__=='__main__':main()
