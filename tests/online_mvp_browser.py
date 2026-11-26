"""Packaged online MVP in Chrome with an actual handler and mocked providers."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_online_mvp import build
from check_nextwise_browser import Browser

QUOTE='The synthetic AI scheduling service supports appointment reminders for clinics.'
with tempfile.TemporaryDirectory(prefix='nextwise-online-browser-',ignore_cleanup_errors=True) as temp:
    bundle=Path(temp)/'bundle';build(bundle)
    spec=importlib.util.spec_from_file_location('packaged_online_api',bundle/'api/index.py')
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
    calls=[]
    def provider(url,token,body,timeout):
        if 'tavily.com' in url:
            calls.append('search');return {'results':[{'url':'https://example.com/source','title':'Synthetic source','content':QUOTE}]}
        calls.append('model')
        if body['text']['format']['schema'] is api.online.PLAN:
            value={'understanding':'A clinic wants appointment support.','clarifications':[],
                   'queries':['recent AI appointment tools for clinics']}
        else:
            value={'recommendations':[{'innovation':'Synthetic appointment tool','project_area':'Bookings',
                'improvement':'Review appointment reminders','relevance':'May help the clinic',
                'feasibility':'Unknown','cost':'Unknown','effort':'Unknown','uncertainty':'Not tested',
                'next_action':'Review a sample','source_id':'1','source_quote':QUOTE,
                'novelty':'A synthetic new release','application':'Compare reminders','comparison':'Directly addresses scheduling',
                'classification':'concrete_ai_development'}]}
        return {'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(value)}]}]}
    class Handler(api.handler):
        def do_GET(self):
            path={'/projects':'index.html','/':'index.html','/demo.js':'demo.js','/project.js':'project.js','/style.css':'style.css'}.get(self.path)
            if not path:self.send_error(404);return
            raw=(bundle/'public'/path).read_bytes();self.send_response(200)
            self.send_header('Content-Type','text/html' if path.endswith('.html') else 'text/css' if path.endswith('.css') else 'application/javascript')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',8778),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    with patch.dict(os.environ,{'NEXTWISE_ACCESS_TOKEN':'x'*32,'OPENAI_API_KEY':'test','TAVILY_API_KEY':'test'}),patch.object(api.online,'post_json',side_effect=provider):
        profile=Path(temp)/'chrome'
        chrome=subprocess.Popen(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu',
            '--no-first-run','--remote-debugging-port=9233','--user-data-dir='+str(profile),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try: pages=json.load(urllib.request.urlopen('http://127.0.0.1:9233/json',timeout=1));break
                except OSError:time.sleep(.2)
            browser=Browser(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
            browser.call('Page.enable');browser.call('Runtime.enable');browser.call('Fetch.enable',{'patterns':[{'urlPattern':'*'}]})
            browser.allowed_origin='http://127.0.0.1:8778';browser.call('Page.navigate',{'url':browser.allowed_origin+'/'})
            for _ in range(100):
                if browser.evaluate('!!document.querySelector("#discover") && !!document.querySelector("#discover").onclick'):break
                time.sleep(.1)
            browser.evaluate('''document.querySelector('#project-text').value='A clinic wants help with appointment scheduling.';
                document.querySelector('#access-code').value='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx';document.querySelector('#discover').click();true''')
            for _ in range(100):
                if browser.evaluate('document.querySelectorAll("#recommendations article").length===1'):break
                time.sleep(.1)
            assert browser.evaluate('document.querySelector("#recommendations h2")?.textContent')=='Synthetic appointment tool'
            assert browser.evaluate('document.querySelector("#recommendations a")?.href')=='https://example.com/source'
            assert calls==['model','search','model'] and not browser.blocked_requests
            print('PASS: actual packaged handler and frontend render a provider-backed synthetic opportunity')
        finally:
            chrome.terminate();chrome.wait(timeout=10);server.shutdown();server.server_close()
