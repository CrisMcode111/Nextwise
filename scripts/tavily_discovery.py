"""Bounded Tavily Search + independent public-page evidence. Stdlib; no persistence."""
from datetime import datetime, timezone
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

import update_discovery as d

ENDPOINT = 'https://api.tavily.com/search'
MAX_SEARCHES = 2
RESULTS_PER_SEARCH = 5
MAX_SOURCE_PAGES = 4
MAX_SEARCH_BYTES = 1_000_000
SEARCH_TIMEOUT = 8
SEARCH_DEADLINE = 15


class SearchUnavailable(Exception):
    """Fixed, safe failure: never contains a key, response body or URL query."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def search(query, key):
    payload = {'query':query, 'topic':'general', 'search_depth':'basic',
        'max_results':RESULTS_PER_SEARCH, 'auto_parameters':False,
        'include_answer':False, 'include_raw_content':False, 'include_images':False,
        'include_usage':True}
    request = Request(ENDPOINT, data=json.dumps(payload).encode('utf-8'), method='POST',
        headers={'Authorization':'Bearer '+key, 'Content-Type':'application/json', 'Accept-Encoding':'identity'})
    try:
        opener = build_opener(ProxyHandler({}), NoRedirect())
        started = time.monotonic()
        with opener.open(request, timeout=SEARCH_TIMEOUT) as response:
            raw = bytearray()
            while True:
                if time.monotonic()-started > SEARCH_DEADLINE: raise SearchUnavailable()
                chunk = response.read1(min(65536, MAX_SEARCH_BYTES+1-len(raw)))
                if not chunk: break
                raw.extend(chunk)
                if len(raw) > MAX_SEARCH_BYTES: raise SearchUnavailable()
        text = raw.decode('utf-8')
        if key in text: raise SearchUnavailable()
        result = json.loads(text)
        if not isinstance(result, dict) or not isinstance(result.get('results'), list): raise SearchUnavailable()
        usage = result.get('usage', {}).get('credits')
        if usage is not None and (type(usage) is not int or usage != 1): raise SearchUnavailable()
        return result['results'][:RESULTS_PER_SEARCH]
    except HTTPError as error:
        error.close()
        raise SearchUnavailable() from None
    except Exception:
        raise SearchUnavailable() from None
    finally:
        request.remove_header('Authorization')


def source_url(url):
    if not isinstance(url, str) or len(url) > 2048: raise ValueError('Invalid public source')
    parsed = urlsplit(url)
    if not parsed.hostname or ':' in parsed.hostname: raise ValueError('Source must have a plain public HTTPS hostname')
    value = d.canonical(url)
    if urlsplit(value).query: raise ValueError('Source query parameters are not accepted')
    host = urlsplit(value).hostname
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('Local source blocked')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return value
    if not address.is_global or address.is_multicast: raise ValueError('Non-public source blocked')
    return value


def public_page(url):
    """Pin the validated public IP for TLS; never re-resolve or follow redirects.

    Dynamic pages cannot use the fixed-allowlist fetcher without opening SSRF.
    Verify all DNS answers, then connect to one numeric address with the original
    hostname for TLS certificate verification and the Host header. No API key.
    """
    connection = None
    try:
        url = source_url(url)
        parsed = urlsplit(url)
        answers = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        addresses = [answer[4][0] for answer in answers]
        if not addresses or any(not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast for ip in addresses):
            raise ValueError('Non-public DNS answer')
        class PinnedConnection(http.client.HTTPSConnection):
            def connect(self):
                self.sock = socket.create_connection((addresses[0],443), timeout=self.timeout)
                try: self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=parsed.hostname)
                except Exception:
                    self.sock.close()
                    raise
        started = time.monotonic()
        connection = PinnedConnection(parsed.hostname, timeout=d.TIMEOUT)
        connection.request('GET', parsed.path or '/', headers={'User-Agent':d.collector.USER_AGENT, 'Accept-Encoding':'identity'})
        response = connection.getresponse()
        if response.status != 200: raise ValueError('Source unavailable or redirected')
        if 'html' not in response.getheader('Content-Type', '').lower(): raise ValueError('HTML required')
        if int(response.getheader('Content-Length', '0')) > d.MAX_BYTES: raise ValueError('Source too large')
        raw = bytearray()
        while True:
            if time.monotonic()-started > d.DEADLINE: raise ValueError('Source deadline exceeded')
            chunk = response.read1(min(65536,d.MAX_BYTES+1-len(raw)))
            if not chunk: break
            raw.extend(chunk)
            if len(raw) > d.MAX_BYTES: raise ValueError('Source too large')
        return {'raw':bytes(raw), 'error':None}
    except Exception:
        return {'raw':b'', 'error':'Public source unavailable, unsafe, redirected or unreadable; no retry made.'}
    finally:
        if connection: connection.close()


def plans(project):
    result = []
    needs = d.project_needs(project)
    if needs:
        result.append({'query':'LLM structured output user requirements extraction schema validation evaluation tools official documentation',
                       'needs':needs})
    if 'recipes' in project['objective'].lower() and 'constraints' in project['objective'].lower():
        result.append({'query':'AI recipe meal planning tools dietary preferences constraints official product documentation',
            'needs':[{'id':'recipe_personalization', 'description':'Generate or adapt recipes and meal plans to explicit user constraints.'}]})
    return result[:MAX_SEARCHES]


def product_key(url):
    parsed = urlsplit(source_url(url))
    host = re.sub(r'^(?:www\.|docs\.)', '', parsed.hostname)
    if host in ('github.com','huggingface.co'):
        parts = parsed.path.strip('/').split('/')
        if len(parts) < 2: raise ValueError('A product/repository path is required')
        return host+'/'+('/'.join(parts[:2])).casefold()
    return host


def blocked_records(existing, history):
    heads = {}
    for record in history:
        subject = record.get('candidate_id') or record.get('investigation_id')
        if not subject: raise ValueError('Decision snapshot has no subject identity.')
        if subject not in heads or record.get('version',0) > heads[subject].get('version',0): heads[subject]=record
    return list(existing)+[record for record in heads.values() if record.get('choice') in ('Reject','Defer')]


def excluded(name, url, records):
    for record in records:
        refs = record.get('evidence_references', {})
        old_url = record.get('url') or (refs.get('url') if isinstance(refs,dict) else None)
        if old_url:
            try:
                if product_key(old_url) == product_key(url): return True
            except (ValueError, AttributeError): pass
        title = record.get('title','')+' '+record.get('technology','')
        if name and re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',title,re.I): return True
    return False


def page_candidate(url, raw, needs, now):
    extractor = d.collector.extract_page(raw.decode('utf-8', errors='replace'))
    title = extractor.title() or ''
    if re.search(r'\b(?:best|top \d+|roundup|alternatives|comparison|review|news)\b',title,re.I): return None
    names = [meta.get('content','') for meta in extractor.meta if meta.get('property','').lower()=='og:site_name']
    if urlsplit(url).hostname in ('github.com','huggingface.co'):
        names.insert(0,urlsplit(url).path.strip('/').split('/')[1])
    names += re.split(r'\s+[|—–-]\s+|:\s+', title)
    name = next((part.strip() for part in names if 2 <= len(part.strip()) <= 60
        and len(part.split()) <= 5 and not re.search(r'\b(?:docs?|documentation|reference|home|structured|validation|evaluation|guide|welcome|github|hugging face|readthedocs)\b',part,re.I)), None)
    if not name: return None
    phrases = [re.sub(r'\s+',' ',line).strip() for line in extractor.text().splitlines()]
    for need in needs:
        if need['id']=='recipe_personalization':
            pattern = r'\b(?:recipes?|meal plans?|meal planning)\b.{0,120}\b(?:dietary|preferences|constraints|allergies)\b|\b(?:dietary|preferences|constraints|allergies)\b.{0,120}\b(?:recipes?|meal plans?|meal planning)\b'
            reason = 'Could be evaluated for recipe or meal-plan personalization under explicit user constraints; dietary suitability and safety are unverified.'
        else:
            _,pattern,reason = d.PROJECT_NEEDS[need['id']]
        evidence = next((phrase for phrase in phrases if 40 <= len(phrase) <= 700 and re.search(pattern,phrase,re.I)
            and not re.search(r'\b(?:not|never|unsupported)\b',phrase,re.I)),None)
        if evidence:
            return {'title':name,'url':url,'publisher':urlsplit(url).hostname,'kind':'discovered_product',
                'publication_date':None,'retrieved_at':now.isoformat(),'description':evidence,'label':d.TOOL_LABEL,
                'need_id':need['id'],'reasons':[reason],'supporting_phrases':[evidence],'raw_sha256':d.sha(raw),
                'limitations':['Found through web search and checked against this page; publisher ownership and official status are not independently established.',
                    'Project integration, extraction accuracy, dietary safety, pricing and terms remain unverified. No tool or model was run.']}
    return None


def discover(existing, *, fetcher=None, now=None, project=None, progress=lambda message:None,
             decision_history=(), searcher=None, page_fetcher=None):
    now = now or datetime.now(timezone.utc)
    project = d.context() if project is None else project
    queries = plans(project)
    blocked = blocked_records(existing,decision_history)
    key = os.environ.get('TAVILY_API_KEY','').strip()
    accounting = {'provider':'Tavily','requests_attempted':0,'expected_credits_per_request':1,
                  'maximum_credits':min(MAX_SEARCHES,len(queries)) if key else 0,'retry_count':0,
                  'status':'not_configured' if not key else 'ready'}
    pool, candidates, sources = [], [], []
    searcher = searcher or search
    page_fetcher = page_fetcher or public_page
    try:
        if key:
            for plan in queries:
                progress('Searching the web for project-relevant tools')
                accounting['requests_attempted'] += 1  # Reserve before transport; no retry even on timeout.
                try:
                    results = searcher(plan['query'],key)
                    for index,item in enumerate(results[:RESULTS_PER_SEARCH]):
                        if not isinstance(item,dict): continue
                        try:
                            url = source_url(item.get('url'))
                            product_key(url)
                        except (ValueError, TypeError, AttributeError): continue
                        pool.append((index,url,plan['needs']))
                except Exception:
                    accounting['status']='failed_or_unconfirmed'
                    break  # Auth/quota/network/format failures stop further spending.
            else: accounting['status']='completed'
    finally:
        key = None
    all_needs = list({need['id']:need for plan in queries for need in plan['needs']}.values())
    seen, attempts = set(), 0
    for _,url,needs in sorted(pool,key=lambda item:item[0]):
        identity = product_key(url)
        if identity in seen or excluded('',url,blocked): continue
        if attempts == MAX_SOURCE_PAGES or len(candidates)==3: break
        seen.add(identity); attempts += 1
        record = {'url':url,'publisher':urlsplit(url).hostname,'kind':'discovered_product','eligible_items':0,'error':None}
        try:
            progress('Checking a discovered public source')
            response = page_fetcher(url)
            if response.get('error'): raise ValueError()
            candidate = page_candidate(url,response['raw'],all_needs,now)
            if candidate and not excluded(candidate['title'],url,blocked+candidates):
                candidates.append(candidate);record['eligible_items']=1
        except Exception:
            record['error']='Public source unavailable or insufficient; no candidate inferred and no retry made.'
        sources.append(record)
    # Catalog fills empty slots without Tavily Extract or another search.
    if len(candidates)<3:
        fallback = d.catalog_tool_preview(list(existing)+candidates, fetcher=fetcher, now=now,
            project=project, decision_history=decision_history, progress=progress)
        for candidate in fallback['candidates']:
            if not excluded(candidate['title'],candidate['url'],blocked+candidates):
                candidates.append(candidate)
                if len(candidates)==3: break
        sources += fallback['sources']
    accounting['source_pages_attempted']=attempts
    accounting['credits_if_attempts_billed']=accounting['requests_attempted']
    needs = {need['id']:need for plan in queries for need in plan['needs']}
    return {'checked_at':now.isoformat(),'candidates':candidates[:3],'sources':sources,'search':accounting,
        'status':'partial_failure' if accounting['status']=='failed_or_unconfirmed' or any(s['error'] for s in sources) else 'success',
        'scope':{'mode':'project','strategy':'tavily_with_catalog_fallback','needs':list(needs.values()),
                 'max_searches':MAX_SEARCHES,'results_per_search':RESULTS_PER_SEARCH,'max_source_pages':MAX_SOURCE_PAGES},
        'notice':'Public web search when configured, with the existing catalog as fallback. Source passages support capabilities, not project benefits. Candidates are unvalidated; results are not saved.'}
