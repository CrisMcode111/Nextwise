"""Protected online MVP handler. External providers are never called at import."""
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import sys
from datetime import date,timedelta
from urllib.parse import urlsplit,parse_qs

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import online
import github_ingestion


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def respond(self,status,value):
        raw=json.dumps(value,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        for key,val in {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
                        'X-Content-Type-Options':'nosniff','Content-Length':str(len(raw))}.items(): self.send_header(key,val)
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        self.respond(200,{'mode':'online','configured':all(os.environ.get(k) for k in
            ('NEXTWISE_ACCESS_TOKEN','OPENAI_API_KEY','TAVILY_API_KEY'))})
    def do_POST(self):
        expected=os.environ.get('NEXTWISE_ACCESS_TOKEN','')
        supplied=self.headers.get('X-Nextwise-Access','')
        if len(expected)<32 or not hmac.compare_digest(expected,supplied):
            self.respond(403,{'message':'Access is unavailable or the access code is invalid.'}); return
        if self.headers.get('Sec-Fetch-Site')=='cross-site':
            self.respond(403,{'message':'Open this application directly.'}); return
        parsed=urlsplit(self.path)
        route=parse_qs(parsed.query).get('route',['github' if parsed.path=='/api/github' else 'discover'])
        if route==['github']:
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4096 or self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError()
                data=json.loads(self.rfile.read(length).decode('utf-8'))
                if not isinstance(data,dict) or set(data)!={'url'}: raise ValueError()
                self.respond(200,github_ingestion.extract(data['url']))
            except Exception:
                self.respond(400,{'message':'The public repository could not be read. Check its URL or paste a description.'})
            return
        if route!=['discover']:
            self.respond(404,{'message':'Unknown action.'}); return
        openai_key=os.environ.get('OPENAI_API_KEY',''); tavily_key=os.environ.get('TAVILY_API_KEY','')
        if not openai_key or not tavily_key:
            self.respond(503,{'message':'Online discovery has not been configured by the owner.'}); return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=20000 or self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError()
            data=json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(data,dict) or not {'project'}<=set(data) or set(data)-{'project','history'}: raise ValueError()
            def model(prompt,schema,timeout): return online.openai(prompt,schema,openai_key,timeout)
            search_count=0
            def search(query,timeout):
                nonlocal search_count
                search_count+=1
                options={'query':query,'search_depth':'basic','max_results':5,'auto_parameters':False,
                         'include_answer':False,'include_raw_content':False,'include_published_date':True}
                # Reserve one query for established but material technologies.
                if search_count<=2: options['start_date']=(date.today()-timedelta(days=90)).isoformat()
                return online.post_json('https://api.tavily.com/search',tavily_key,
                    options,timeout)
            self.respond(200,online.discover(data['project'],history=data.get('history'),model=model,search=search))
        except Exception:
            self.respond(503,{'message':'Discovery could not complete. No recommendations were substituted; try again only when ready.'})
