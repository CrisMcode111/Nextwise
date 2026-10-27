"""Offline Chrome smoke test of the generated public bundle and real PDF.js worker.

Run explicitly: python -B tests/public_demo_browser.py
All source responses are fixtures; no public/private service is contacted.
"""
import base64
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_nextwise_browser import Browser
from test_public_demo import repository_fixture,business_repository_fixture


def pdf_fixture(text):
    stream=f'BT /F1 12 Tf 40 750 Td ({text}) Tj ET'.encode('ascii')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    raw=b'%PDF-1.4\n';offsets=[0]
    for index,obj in enumerate(objects,1):
        offsets.append(len(raw));raw+=f'{index} 0 obj\n'.encode()+obj+b'\nendobj\n'
    position=len(raw)
    raw+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return raw+f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{position}\n%%EOF'.encode()


def main():
    bundle=ROOT/'.nextwise-vercel-demo'
    spec=importlib.util.spec_from_file_location('public_api_browser_fixture',bundle/'api/index.py')
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    phrases={'instructor':'Instructor extracts structured data from explicit LLM responses using schemas.',
        'pydantic':'Pydantic provides data validation using Python types and structured schemas.',
        'promptfoo':'promptfoo supports evaluation of LLM outputs using test fixtures and assertions.'}
    previews={}
    for source in api.SOURCES:
        item=repository_fixture(source['name'],phrases[source['id']])
        previews[source['id']]=api.search_public.discover(source['id'],searcher=lambda _,item=item:{'items':[item],'incomplete_results':False})
    for key in api.search_public.BUSINESS_NEEDS:
        item=business_repository_fixture(key)
        previews[key]=api.search_public.discover(key,searcher=lambda _,item=item:{'items':[item],'incomplete_results':False})
    requests=[]
    class PublicFixtureServer(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(bundle/'public'),**kwargs)
        def log_message(self,*args):pass
        def end_headers(self):
            self.send_header('Content-Security-Policy',api.CSP)
            super().end_headers()
        def do_GET(self):
            requests.append(self.path);route=urlsplit(self.path)
            if route.path.startswith('/api/'):
                source=parse_qs(route.query).get('need',[''])[0]
                result=api.demo_data() if self.path=='/api/demo' else previews.get(source) if route.path=='/api/discover' else None
                raw=json.dumps(result or {}).encode();self.send_response(200 if result else 404)
                self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw);return
            super().do_GET()
        def do_POST(self):raise AssertionError('No browser content may be uploaded')
    server=ThreadingHTTPServer(('127.0.0.1',0),PublicFixtureServer)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    class OfflineBrowser(Browser):
        def send(self,method,params=None):
            # Serve exact bundled PDF assets through CDP, avoiding flaky large
            # loopback HTTP transfers. The real parser and worker still execute.
            if method=='Fetch.continueRequest' and self.request_log:
                asset=urlsplit(self.request_log[-1][1]).path
                if asset in ('/pdfjs/pdf.mjs','/pdfjs/pdf.worker.mjs'):
                    return super().send('Fetch.fulfillRequest',{'requestId':params['requestId'],
                        'responseCode':200,'responseHeaders':[{'name':'Content-Type','value':'application/javascript'},
                            {'name':'Content-Security-Policy','value':api.CSP}],
                        'body':base64.b64encode((bundle/'public'/asset.lstrip('/')).read_bytes()).decode()})
            return super().send(method,params)
    browser=None;process=None
    with tempfile.TemporaryDirectory(prefix='nextwise-public-chrome-') as profile:
        try:
            process=subprocess.Popen(['C:/Program Files/Google/Chrome/Application/chrome.exe',
                '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--disable-background-networking','--disable-component-update','--disable-sync',
                '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost',
                '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
                '--user-data-dir='+profile,'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            active_port=Path(profile)/'DevToolsActivePort'
            for _ in range(100):
                if active_port.exists():break
                time.sleep(.1)
            port=active_port.read_text().splitlines()[0]
            pages=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=3))
            browser=OfflineBrowser(next(page['webSocketDebuggerUrl'] for page in pages if page['type']=='page'))
            browser.allowed_origin=origin
            for method in ('Page.enable','Runtime.enable','Network.enable'):browser.call(method)
            browser.call('Fetch.enable',{'patterns':[{'urlPattern':'*','requestStage':'Request'}]})
            browser.call('Emulation.setDeviceMetricsOverride',{'width':1280,'height':900,'deviceScaleFactor':1,'mobile':False})
            browser.call('Page.navigate',{'url':origin})
            for _ in range(100):
                if browser.evaluate('typeof demoContext!=="undefined" && demoContext!==null'):break
                time.sleep(.05)
            assert browser.evaluate('document.querySelector("#project-text").value')==''
            assert browser.evaluate('document.querySelectorAll("#tool-candidates article").length')==0
            assert browser.evaluate('''(()=>{
                const spiral=document.querySelector('.discovery-spiral');
                return spiral.getBoundingClientRect().height>0 &&
                    getComputedStyle(document.querySelector('.spiral-star')).animationName==='demo-star-twinkle' &&
                    getComputedStyle(spiral).animationDuration==='100s';
            })()''')
            browser.evaluate('''(()=>{
                const original=window.fetch;window.identityStates=[];
                window.fetch=(url,options)=>{
                    if(String(url).startsWith('/api/discover?'))window.identityStates.push({
                        processing:document.querySelector('#assistant-identity').dataset.processing,
                        animation:getComputedStyle(document.querySelector('.spiral-star')).animationName,
                        duration:getComputedStyle(document.querySelector('.spiral-star')).animationDuration});
                    return original(url,options);
                };
            })()''')
            food='I sell meal plans for busy parents with food preferences. Answering customer questions takes too much time.'
            def enter_food():
                return browser.evaluate('''(async()=>{
                    document.querySelector("#project-text").value='''+json.dumps(food)+''';
                    document.querySelector("#review-project").click();
                    await document.querySelector("#find-ideas").onclick();
                    return document.querySelectorAll("#tool-candidates article").length;
                })()''')
            assert enter_food()==2
            assert browser.evaluate('identityStates.length===2 && identityStates.every(s=>s.processing==="true" && s.animation==="demo-star-twinkle" && s.duration==="2.8s")')
            assert browser.evaluate('document.querySelector("#assistant-identity").dataset.processing')=='false'
            assert browser.evaluate('document.querySelector("#tool-candidates").textContent.includes("meal")')
            assert browser.evaluate('document.querySelectorAll("#project-review input").length')==0
            assert browser.evaluate('getComputedStyle(document.querySelector(".assistant-layout")).gridTemplateColumns.split(" ").length')==2
            assert browser.evaluate('document.querySelector("#search-progress").hidden')
            assert browser.evaluate('!document.querySelector("#demo-details").open')
            assert browser.evaluate('document.querySelector(".discovery-spiral path").getAttribute("d").includes("a34 34")')
            assert browser.evaluate('''(()=>{
                document.querySelector("#tool-candidates button").click();
                return !document.querySelector("#selection-status").hidden &&
                    document.querySelector("#selection-status").textContent.includes("You chose Fixture-meal_planning") &&
                    Object.values(JSON.parse(localStorage.getItem(DEMO_STORAGE))).filter(record=>record.selected).length===1;
            })()''')
            browser.call('Page.navigate',{'url':origin})
            for _ in range(100):
                if browser.evaluate('typeof demoContext!=="undefined" && demoContext!==null'):break
                time.sleep(.05)
            assert browser.evaluate('document.querySelector("#project-text").value')==''
            assert enter_food()==2
            assert browser.evaluate('document.querySelector("#selection-status").textContent.includes("You chose Fixture-meal_planning")')
            assert browser.evaluate('''(async()=>{
                document.querySelector("#find-ideas").click();
                await new Promise(resolve=>setTimeout(resolve,0));
                return document.querySelector("#project-status").textContent;
            })()''').startswith('Applied your selected needs:')
            encoded=base64.b64encode(pdf_fixture('I run a hair salon. I want fewer missed appointments. Answering customer questions takes too much time.')).decode()
            browser.call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
            assert browser.evaluate('getComputedStyle(document.querySelector(".spiral-star")).animationName')=='none'
            assert browser.evaluate('getComputedStyle(document.querySelector(".discovery-spiral")).animationName')=='none'
            assert browser.evaluate('getComputedStyle(document.querySelector(".spiral-traveler")).animationName')=='none'
            result=browser.evaluate('''(async()=>{
                const bytes=Uint8Array.from(atob('''+json.dumps(encoded)+'''),c=>c.charCodeAt(0));
                const transfer=new DataTransfer();transfer.items.add(new File([bytes],"project.pdf",{type:"application/pdf"}));
                document.querySelector("#project-file").files=transfer.files;
                const reading=document.querySelector("#project-file").onchange();
                const readingState=document.querySelector("#assistant-identity").dataset.processing;
                const readingAnimation=getComputedStyle(document.querySelector(".spiral-star")).animationName;
                await reading;
                const text=document.querySelector("#project-text").value;
                await document.querySelector("#find-ideas").onclick();
                return {text,readingState,readingAnimation,status:document.querySelector("#project-status").textContent,
                    count:document.querySelectorAll("#tool-candidates article").length,
                    card:document.querySelector("#tool-candidates").textContent};
            })()''')
            assert result['text'].startswith('I run a hair salon'),result
            assert result['readingState']=='true' and result['readingAnimation']=='none',result
            browser.call('Emulation.setEmulatedMedia',{'features':[]})
            assert result['count']==2 and 'Fixture-appointments' in result['card'],result
            assert 'meal plans' not in result['card'] and 'developer libraries' not in result['card'],result
            assert browser.evaluate('''(()=>{
                const button=[...document.querySelectorAll("#tool-candidates button")].find(b=>b.textContent==="Explain why");button.click();
                return button.getAttribute("aria-expanded")==="true" && !document.querySelector(".suggestion-evidence").hidden;
            })()''')
            assert browser.evaluate('''(()=>{
                const card=[...document.querySelectorAll("#tool-candidates article")].find(c=>c.textContent.includes("Fixture-appointments"));
                card.querySelector("button").click();
                return document.querySelector("#selection-status").textContent.includes("You chose Fixture-appointments");
            })()''')
            assert browser.evaluate('''(()=>{
                const card=[...document.querySelectorAll("#tool-candidates article")].find(c=>c.textContent.includes("Fixture-appointments"));
                card.querySelector("button.quiet").click();
                return document.querySelectorAll("#tool-candidates article").length===1 &&
                    document.querySelector("#selection-status").hidden &&
                    Object.values(JSON.parse(localStorage.getItem(DEMO_STORAGE))).some(record=>record.choice==="Defer");
            })()''')
            assert browser.evaluate('''(async()=>{
                document.querySelector("#project-text").value="I am opening a flower shop.";
                document.querySelector("#review-project").click();await document.querySelector("#find-ideas").onclick();
                return document.querySelectorAll("#tool-candidates article").length;
            })()''')==0
            browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            assert browser.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert browser.evaluate('getComputedStyle(document.querySelector(".assistant-layout")).gridTemplateColumns.split(" ").length')==1
            assert len([request for request in requests if request.startswith('/api/discover?')])==5
            assert not browser.blocked_requests,browser.blocked_requests
            assert browser.errors==0,browser.errors
            assert all('salon' not in request and 'parents' not in request for request in requests)
            assert any(url.endswith('/pdfjs/pdf.worker.mjs') for _,url in browser.request_log),browser.request_log
            print('PASS real Chrome, MOCKED sources: two opportunities for food and salon projects, text/PDF input, selection confirmation/reload persistence, explanations/preferences, request limits, mobile layout and privacy. No live discovery or model reasoning verified.')
            guided_brief='AI Raw Gourmet is an application that generates and adapts recipes and meal plans to user constraints.'
            before_guided=len([request for request in requests if request.startswith('/api/discover?')])
            def enter_guided():
                return browser.evaluate('''(async()=>{
                    document.querySelector("#project-text").value='''+json.dumps(guided_brief)+''';
                    document.querySelector("#review-project").click();
                    await document.querySelector("#find-ideas").onclick();
                    return {titles:[...document.querySelectorAll("#tool-candidates h2")].map(n=>n.textContent),
                        sources:[...document.querySelectorAll("#tool-candidates article")].map(n=>n.querySelector("a").href),
                        notice:document.querySelector("#guided-notice").textContent,
                        hidden:document.querySelector("#search-progress").hidden};
                })()''')
            guided=enter_guided()
            assert guided['titles']==['DishGen','Samsung Food+'],guided
            assert guided['sources']==['https://www.dishgen.com/','https://samsungfood.com/food-plus/'],guided
            assert guided['notice'].startswith('Guided demo — pre-verified opportunities'),guided
            assert guided['hidden'],guided
            assert browser.evaluate('''(()=>{
                document.querySelector("#tool-candidates button").click();
                return document.querySelector("#selection-status").textContent.includes("You chose DishGen") &&
                    document.querySelector("#selection-status h2").textContent.includes("DishGen") &&
                    document.querySelector("#selection-status .selection-action").textContent.startsWith("Next step:") &&
                    JSON.parse(localStorage.getItem(DEMO_STORAGE))["guided-dishgen"].selected===true;
            })()''')
            assert browser.evaluate('''(()=>{
                const card=document.querySelector('#tool-candidates article');
                [...card.querySelectorAll('button')].find(b=>b.textContent==='Explain why').click();
                const evidence=card.querySelector('.suggestion-evidence');
                return !evidence.hidden && !evidence.textContent.includes(document.querySelector('#project-text').value) &&
                    evidence.textContent.includes('Generate and adapt recipes and meal plans to user constraints.') &&
                    evidence.textContent.includes('What we still need to check');
            })()''')
            assert browser.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert browser.evaluate('getComputedStyle(document.querySelector(".selection-confirmation")).borderLeftWidth')=='4px'
            browser.call('Page.navigate',{'url':origin})
            for _ in range(100):
                if browser.evaluate('typeof demoContext!=="undefined" && demoContext!==null'):break
                time.sleep(.05)
            assert enter_guided()['titles']==['DishGen','Samsung Food+']
            assert browser.evaluate('document.querySelector("#selection-status").textContent.includes("You chose DishGen")')
            assert browser.evaluate('document.querySelector(".discovery-spiral").getBoundingClientRect().height>0 && document.querySelector("#assistant-identity").dataset.processing==="false"')
            assert len([request for request in requests if request.startswith('/api/discover?')])==before_guided
            assert not browser.blocked_requests,browser.blocked_requests
            assert browser.errors==0,browser.errors
            browser.call('Emulation.setDeviceMetricsOverride',{'width':1280,'height':1100,'deviceScaleFactor':1,'mobile':False})
            def motion_sample():
                return browser.evaluate('''(()=>{
                    const star=document.querySelector('.spiral-star');const rect=star.getBoundingClientRect();
                    return {x:rect.x,y:rect.y,opacity:getComputedStyle(star).opacity,
                        rotation:getComputedStyle(document.querySelector('.discovery-spiral')).transform,
                        along:getComputedStyle(document.querySelector('.spiral-traveler')).offsetDistance};
                })()''')
            first=motion_sample()
            shots=[]
            for name in ('before','after'):
                if name=='after':time.sleep(3)  # Observe real CSS motion, never a production delay.
                path=Path(tempfile.gettempdir())/f'nextwise-spiral-{name}.png'
                path.write_bytes(base64.b64decode(browser.call('Page.captureScreenshot',{'format':'png'})['data']))
                shots.append(str(path))
            second=motion_sample()
            assert first['rotation']!=second['rotation'],(first,second)
            assert first['along']!=second['along'],(first,second)
            assert abs(float(first['opacity'])-float(second['opacity']))>.03,(first,second)
            assert abs(first['x']-second['x'])+abs(first['y']-second['y'])>3,(first,second)
            assert browser.evaluate('''(()=>{
                const button=document.querySelector('#tool-candidates button');const r=button.getBoundingClientRect();
                return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===button &&
                    getComputedStyle(document.querySelector('#assistant-identity')).pointerEvents==='none' &&
                    getComputedStyle(document.querySelector('#assistant-identity')).position==='absolute';
            })()''')
            browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            assert browser.evaluate('document.documentElement.scrollWidth<=innerWidth')
            print('PASS background motion over 3 seconds: rotation, curve travel, twinkle, click-through layering and mobile overflow. Screenshots: '+', '.join(shots))
            print('PASS real Chrome guided flow: real retained DishGen/Samsung Food+ official evidence, exact two cards, honest guided label, selection/reload persistence, zero discovery calls or artificial waiting. Product output quality and integration remain untested.')
        finally:
            if browser:browser.ws.close()
            if process:
                process.terminate();process.wait(timeout=10)
            server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
