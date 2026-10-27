"""Bounded, user-triggered public discovery. Never runs models or collector main()."""
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import difflib
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError
import uuid
import xml.etree.ElementTree as ET

import collect_sources as collector
import investigation_memory as memory

ROOT = Path(__file__).resolve().parents[1]
FEED = 'https://blogs.nvidia.com/feed/'
MAX_BYTES = 2_000_000
TIMEOUT = 8
DEADLINE = 20
MAX_REDIRECTS = 3
ITEM_CAP = 10
LOOKBACK_DAYS = 14
RELEVANCE_POLICY = 'context-phrases-v2'


def config():
    investigation = json.loads((ROOT/'data/investigation.json').read_text(encoding='utf-8'))
    return {'approval': 'User-approved fixed pages and NVIDIA feed for manual discovery',
            'pages': investigation['initial_source_urls'], 'feed': FEED,
            'item_cap': ITEM_CAP, 'lookback_days': LOOKBACK_DAYS,
            'max_response_bytes': MAX_BYTES, 'socket_timeout_seconds': TIMEOUT,
            'source_deadline_seconds': DEADLINE, 'max_redirects': MAX_REDIRECTS,
            'destinations': 'Exact approved HTTPS URLs only; redirects checked before following; articles are not fetched.'}


def canonical(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Only approved public HTTPS URLs are allowed')
    query = urlencode(sorted((k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k not in ('fbclid','gclid')))
    return urlunsplit(('https', p.hostname.lower(), p.path.rstrip('/') or '/', query, ''))


def article_url(url):
    value = canonical(url)
    p = urlsplit(value)
    if p.hostname != 'blogs.nvidia.com' or not p.path.startswith('/blog/'):
        raise ValueError('Feed item destination is outside approved NVIDIA blog articles')
    return value


def fetch(url, *, approved_urls=None):
    approved = {canonical(u) for u in (config()['pages']+[FEED] if approved_urls is None else approved_urls)}
    class Redirects(HTTPRedirectHandler):
        count = 0
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.count += 1
            if time.monotonic()-start > DEADLINE:
                raise ValueError('Source deadline exceeded during redirects')
            if self.count > MAX_REDIRECTS or canonical(newurl) not in approved:
                raise ValueError('Redirect blocked: destination or redirect limit is outside approval')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    raw = b''
    result = {'requested_url':url, 'final_url':None, 'http_status':None, 'raw':raw, 'error':None}
    try:
        if canonical(url) not in approved:
            raise ValueError('Destination is not approved')
        start = time.monotonic()
        request = Request(url, headers={'User-Agent':collector.USER_AGENT, 'Accept-Encoding':'identity'})
        with build_opener(Redirects()).open(request, timeout=TIMEOUT) as response:
            result.update(final_url=response.geturl(), http_status=response.status)
            if int(response.headers.get('Content-Length','0')) > MAX_BYTES:
                raise ValueError('Response exceeds 2 MB limit')
            while True:
                if time.monotonic()-start > DEADLINE:
                    raise ValueError('Source deadline exceeded')
                chunk = response.read1(min(65536, MAX_BYTES+1-len(raw)))
                if not chunk: break
                raw += chunk
                if len(raw) > MAX_BYTES:
                    raw = raw[:MAX_BYTES]
                    raise ValueError('Response exceeds 2 MB limit; snapshot is truncated')
    except HTTPError as exc:
        result.update(http_status=exc.code, error=f'HTTP {exc.code}')
        try: raw = exc.read(MAX_BYTES) if exc.fp else b''
        except Exception: raw = b''
        finally: exc.close()
    except Exception as exc:
        # Do not reflect transport diagnostics, proxy details, or credentials.
        result['error'] = str(exc) if isinstance(exc, ValueError) else 'Public-source connection failed or timed out'
    result['raw'] = raw
    return result


def sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value,str) else value).hexdigest()


def readable(html):
    e = collector.extract_page(html)
    return e, re.sub(r'\s+', ' ', e.text()).strip()


def context():
    profile = json.loads((ROOT/'data/project_profile.json').read_text(encoding='utf-8'))
    task = json.loads((ROOT/'data/use_case.json').read_text(encoding='utf-8'))['investigated_task']['description']
    return {'objective':profile['objective'], 'task':task, 'constraints':profile['constraints']}


def relevance(text, project):
    """Conservative positive phrase evidence within one sentence, never bag-of-words.

    Connections describe questions worth checking, not established applicability.
    Generic words, product names and distant co-occurrences cannot qualify.
    """
    model = r'\b(?:llms?|large language models?|language models?|text generation models?)\b'
    extraction = r'\bextract(?:s|ing|ion)?\s+(?:(?:explicit|stated|user|customer)\s+){0,3}(?:requirements|preferences|constraints)\b'
    output = r'\b(?:structured[- ]outputs?|json[- ]schema|schema[- ]constrained (?:json|outputs?)|function calling|tool calling)\b'
    integration = r'\b(?:openai[- ]compatible api|(?:api|sdk) (?:compatibility|integration)|hosted (?:api|endpoint)|inference (?:costs?|pricing|latency)|(?:memory|ram) requirements)\b'
    recipe = r'\b(?:generat(?:e|es|ing)|adapt(?:s|ing)?|personaliz(?:e|es|ing))\b.{0,65}\b(?:recipes?|meal plans?)\b'
    matches = []
    for sentence in re.split(r'[.!?\n]+\s*',text):
        # Long page navigation or unrelated clauses must not bridge capability/context.
        if len(sentence)>700 or re.search(r'\b(?:not|never|no support|unsupported|without support)\b',sentence,re.I): continue
        def nearby(a,b):
            return any(max(x.end(),y.end())-min(x.start(),y.start())<=240
                       for x in re.finditer(a,sentence,re.I) for y in re.finditer(b,sentence,re.I))
        rules = []
        if 'requirements' in project['task'].lower() and (nearby(extraction,output) or nearby(model,output)):
            rules.append(('structured_requirement_capability','Possible task connection: structured user-requirement extraction; task accuracy remains unverified.',[extraction,model,output]))
        if project.get('constraints') and nearby(model,integration):
            rules.append(('model_integration_need','Possible integration question: language-model API compatibility, cost or resource requirements; project compatibility remains unknown.',[model,integration]))
        if 'recipes' in project['objective'].lower() and re.search(recipe,sentence,re.I) and re.search(r'\b(?:dietary|user constraints|preferences|allergies)\b',sentence,re.I):
            rules.append(('constrained_recipe_capability','Possible objective connection: recipe/meal-plan generation under user constraints; suitability remains unverified.',[recipe]))
        for rule,connection,patterns in rules:
            if any(m['rule']==rule for m in matches): continue
            terms=list(dict.fromkeys(m.group() for p in patterns for m in re.finditer(p,sentence,re.I)))
            matches.append({'rule':rule,'connection':connection,'terms':terms,'supporting_phrase':sentence.strip()})
    hints = bool(re.search(r'\b(?:extraction|structured|requirements|deployment|integration|inference|model|llm|recipe|meal|cost|pricing|latency|memory)\b',text,re.I))
    return {'policy_version':RELEVANCE_POLICY,
            'label':'Provisional context/phrase rule matches; no Nemotron reasoning or verified suitability',
            'category':'potential relevance' if matches else ('uncertain relevance' if hints else 'low relevance'),
            'matches':matches,
            'explanation':('Supporting phrases suggest a capability or integration question to investigate; they do not establish project fit.' if matches else
                'Insufficient context: isolated or ambiguous terms do not establish a connection to the approved task or integration needs.' if hints else
                'No supporting capability or integration phrase found. Low relevance is provisional, not a verified exclusion.'),
            'project_context':project}


def assessment_history(item):
    if item.get('relevance_history'): return list(item['relevance_history'])
    if not item.get('relevance'): return []
    return [{'policy_version':item['relevance'].get('policy_version','legacy-keywords-v1'),
             'assessed_at':None, 'source_revision_sha256':item['content_sha256'], 'assessment':item['relevance']}]


def assess_item(item, project, assessed_at):
    current = item.get('relevance',{})
    if (current.get('policy_version')==RELEVANCE_POLICY and current.get('project_context')==project
            and item.get('relevance_history', [{}])[-1].get('source_revision_sha256')==item['content_sha256']): return False
    history=assessment_history(item)
    item['relevance']=relevance(item['title']+'. '+item['text'],project)
    item['relevance_history']=history+[{'policy_version':RELEVANCE_POLICY,'assessed_at':assessed_at,
        'source_revision_sha256':item['content_sha256'],'assessment':item['relevance']}]
    return True


def feed_items(raw, now):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise ValueError('DTD/entities are not accepted')
    root = ET.fromstring(raw)
    if root.tag != 'rss' or root.find('channel') is None: raise ValueError('Expected an RSS channel')
    entries = root.findall('./channel/item')
    valid, rejected = [], []
    for entry in entries:
        try:
            url = article_url(entry.findtext('link') or '')
            published = parsedate_to_datetime(entry.findtext('pubDate') or '').astimezone(timezone.utc)
            if not now-timedelta(days=LOOKBACK_DAYS) <= published <= now: continue
            title = (entry.findtext('title') or '').strip()
            _, text = readable(entry.findtext('description') or '')
            valid.append({'url':url, 'guid':(entry.findtext('guid') or '').strip(), 'title':title,
                          'text':text, 'publication_date':published.isoformat()})
        except Exception:
            rejected.append('Item excluded: missing/invalid date or unapproved article URL')
    # Collapse aliases before applying the cap; keep newest publisher date first.
    valid.sort(key=lambda x:x['publication_date'], reverse=True)
    unique, guids, urls = [], set(), set()
    for item in valid:
        if item['url'] in urls or (item['guid'] and item['guid'] in guids): continue
        unique.append(item); urls.add(item['url'])
        if item['guid']: guids.add(item['guid'])
    return unique[:ITEM_CAP], {'rss_items':len(entries), 'eligible_unique_items':len(unique), 'excluded_items':rejected}


# Transient tool preview. These functions never call Store, H-MEM or a model.
TOOL_LABEL = 'Discovery candidate — not yet validated'
TOOL_FEEDS_PATH = ROOT/'data/discovery_feeds.json'
TOOL_PUBLISHERS = {'blogs.nvidia.com': 'NVIDIA', 'openai.com': 'OpenAI', 'huggingface.co': 'Hugging Face'}
ATOM = '{http://www.w3.org/2005/Atom}'


def tool_feeds():
    """Local configuration is limited to the three reviewed publisher origins."""
    feeds = json.loads(TOOL_FEEDS_PATH.read_text(encoding='utf-8'))['feeds']
    if not isinstance(feeds, list) or not 1 <= len(feeds) <= 4:
        raise ValueError('Configure one to four approved feeds.')
    urls = set()
    for feed in feeds:
        if not isinstance(feed, dict) or not isinstance(feed.get('url'), str) or not urlsplit(feed['url']).hostname:
            raise ValueError('Feed requires an absolute approved HTTPS URL.')
        url = canonical(feed['url'])
        host = urlsplit(url).hostname
        if host not in TOOL_PUBLISHERS or feed.get('publisher') != TOOL_PUBLISHERS[host] or url in urls:
            raise ValueError('Feed publisher, origin or identity is outside the reviewed scope.')
        urls.add(url)
    return feeds


def tool_identity(title):
    """Conservative title alias, in addition to canonical URL identity."""
    value = re.sub(r'^(?:introducing|announcing|meet|new|launching)\s*[:—-]?\s*', '', title, flags=re.I)
    return re.sub(r'[^\w]+', ' ', value.casefold()).strip()


def tool_feed_items(raw, feed, now):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD/entities are not accepted')
    root = ET.fromstring(raw)
    atom = root.tag == ATOM+'feed'
    if atom:
        entries = root.findall(ATOM+'entry')
    elif root.tag == 'rss' and root.find('channel') is not None:
        entries = root.findall('./channel/item')
    else:
        raise ValueError('Expected RSS or Atom')
    valid = []
    for entry in entries:
        try:
            prefix = ATOM if atom else ''
            def field(name):
                node = entry.find(prefix+name)
                return ''.join(node.itertext()).strip() if node is not None else ''
            if atom:
                url = next(n.get('href', '') for n in entry.findall(ATOM+'link') if n.get('rel', 'alternate') == 'alternate')
                # updated is not publication evidence.
                published = datetime.fromisoformat(field('published').replace('Z', '+00:00'))
                summary = field('summary') or field('content')
            else:
                url = field('link')
                published = parsedate_to_datetime(field('pubDate'))
                summary = field('description')
            if published.tzinfo is None: continue
            published = published.astimezone(timezone.utc)
            if not now-timedelta(days=LOOKBACK_DAYS) <= published <= now: continue
            if not urlsplit(url).hostname: continue
            url = canonical(url)
            if urlsplit(url).hostname != urlsplit(feed['url']).hostname or urlsplit(url).path in ('', '/'):
                continue
            _, title = readable(field('title'))
            _, text = readable(summary)
            if not title or len(title) > 300 or len(text) < 30: continue
            valid.append({'title':title, 'url':url, 'publisher':feed['publisher'],
                          'publication_date':published.isoformat(), 'description':text[:600],
                          'source_feed':feed['url']})
        except (ValueError, TypeError, StopIteration, OverflowError):
            continue
    return sorted(valid, key=lambda item:item['publication_date'], reverse=True)[:ITEM_CAP]


def tool_preview(existing_items, *, fetcher=None, feeds=None, now=None, project=None, progress=lambda message:None):
    """Bounded source-only preview; existing_items is an already loaded snapshot.

    NEW means absent from the snapshot, not a verified first-ever product launch.
    No persistence, article retrieval, model requests or automatic retries.
    """
    feeds = tool_feeds() if feeds is None else feeds
    now = now or datetime.now(timezone.utc)
    project = context() if project is None else project
    approved = [f['url'] for f in feeds]
    fetcher = fetcher or (lambda url: fetch(url, approved_urls=approved))
    urls, titles = set(), set()
    for item in existing_items:
        try: urls.add(canonical(item['url']))
        except (ValueError, KeyError): pass
        if item.get('title'): titles.add(tool_identity(item['title']))
    for url in config()['pages']:
        urls.add(canonical(url))
    sources, eligible = [], []
    for feed in feeds:
        progress('Checking tool announcement feed: '+feed['publisher'])
        record = {'url':feed['url'], 'publisher':feed['publisher'], 'error':None, 'eligible_items':0}
        try:
            result = fetcher(feed['url'])
            if result.get('error'): raise ValueError('Feed unavailable; coverage is incomplete.')
            items = tool_feed_items(result['raw'], feed, now)
            record['eligible_items'] = len(items)
            record['raw_sha256'] = sha(result['raw'])
            for item in items:
                title = item['title']
                # An announcement signal and an actual AI product type are both required.
                if not re.search(r'\b(?:introducing|announcing|launch(?:es|ing|ed)?|releas(?:e|es|ed|ing)|unveil(?:s|ed)?|new|now available)\b', title, re.I): continue
                if re.search(r'\b(?:news|funding|partnership|acquisition|report|survey|tutorial|guide|conference|policy|case study|how to)\b', title, re.I): continue
                if not re.search(r'\b(?:ai|llm|language model|model|assistant|agent|sdk|api|app|tool|platform)\b', title+' '+item['description'], re.I): continue
                assessment = relevance(title+'. '+item['description'], project)
                if not assessment['matches']: continue
                eligible.append({**item, 'label':TOOL_LABEL,
                                 'reasons':[m['connection'] for m in assessment['matches']],
                                 'supporting_phrases':[m['supporting_phrase'] for m in assessment['matches']]})
        except Exception:
            record['error'] = 'Feed unavailable or invalid; coverage is incomplete. No retry was made.'
        sources.append(record)
    candidates = []
    # A known URL can also identify a cross-publisher title alias in this check.
    titles.update(tool_identity(item['title']) for item in eligible if item['url'] in urls)
    eligible.sort(key=lambda x:(x['publication_date'], x['url']), reverse=True)
    for item in sorted(eligible, key=lambda x:-len(x['reasons'])):
        identity = tool_identity(item['title'])
        if item['url'] in urls or identity in titles: continue
        urls.add(item['url']); titles.add(identity)
        candidates.append(item)
        if len(candidates) == 3: break
    return {'checked_at':now.isoformat(), 'candidates':candidates, 'sources':sources,
            'status':'partial_failure' if any(s['error'] for s in sources) else 'success',
            'scope':{'feeds':feeds, 'lookback_days':LOOKBACK_DAYS, 'items_per_feed':ITEM_CAP},
            'notice':'Source excerpts only; linked articles and suitability are unverified. New to the loaded candidate snapshot; not proof of a new product. Results are not saved.'}


class Store:
    def __init__(self, root=memory.DEFAULT_MEMORY_ROOT):
        self.root = Path(root)
        self.directory = self.root/'update-discovery'

    def bridge(self, operation, **fields):
        result = memory.call_bridge({'operation':operation, 'investigation_id':'update-discovery',
                                     'memory_root':str(self.root), **fields})
        if not result.get('ok'): raise RuntimeError('Discovery H-MEM storage unavailable; last confirmed data retained. Inspect locks/runtime and retry.')
        return result['discovery']

    def read(self): return self.bridge('discovery_read')

    def save(self, state):
        state['version'] += 1
        return self.bridge('discovery_save', discovery=state)

    @contextmanager
    def exclusive(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        lock = self.directory/'discovery-run.lock'
        try: handle = lock.open('x')
        except FileExistsError: raise RuntimeError('Discovery or selection already running; retry when it finishes. Inspect a stale lock only with the app stopped.') from None
        try:
            handle.write(str(__import__('os').getpid())); handle.close()
            yield
        finally: lock.unlink()

    def run(self, fetcher=fetch, progress=lambda message:None, now=None):
        with self.exclusive():
            return self._run(fetcher, progress, now or datetime.now(timezone.utc))

    def reassess(self):
        """Refresh semantic cache visibility only. GET never calls a model."""
        with self.exclusive():
            state=self.read()
            if self.semantic_refresh(state):return self.save(state)
            return state

    def semantic_refresh(self,state):
        import semantic_discovery as semantic
        try:project=semantic.project_context(self.root)
        except (ValueError,RuntimeError):
            error='Approved project memory or genuine Defer Version 1 could not be verified. Semantic assessment and selection are unavailable; reopen after the investigation load finishes.'
            changed=state.get('semantic_context_error')!=error
            state['semantic_context_error']=error
            return changed
        changed=state.pop('semantic_context_error',None) is not None
        return semantic.refresh(self,state,project) or changed

    def _run(self, fetcher, progress, now):
        state = self.read()
        run = {'id':str(uuid.uuid4()), 'retrieved_at':now.isoformat(), 'sources':[], 'events':[],
               'approval':config(), 'project_context':context()}
        folder = self.directory/'runs'/run['id']; folder.mkdir(parents=True)
        for url in config()['pages']+[FEED]:
            progress(f'Checking approved source {len(run["sources"])+1}/4: {url}')
            result = fetcher(url)
            raw = result.pop('raw')
            sid = collector.stable_source_id(url)
            path = folder/(sid+'.raw'); path.write_bytes(raw)
            record = {**result, 'requested_url':url, 'retrieved_at':now.isoformat(), 'raw_sha256':sha(raw),
                      'snapshot_path':str(path.relative_to(self.directory)), 'publication_date':None}
            run['sources'].append(record)
            try:
                if record['error']: continue
                initial = url not in state['baselines']
                if url == FEED:
                    items, info = feed_items(raw,now); record.update(info)
                else:
                    extractor, text = readable(raw.decode('utf-8',errors='replace'))
                    if len(text) < collector.MIN_TEXT_CHARS: raise ValueError('Insufficient readable content; prior baseline retained')
                    record['publication_date'] = collector.publication_date_from(extractor)
                    items = [{'url':canonical(url), 'guid':'', 'title':extractor.title() or url, 'text':text,
                              'publication_date':record['publication_date']}]
                for item in items:
                    old = next((v for v in state['items'].values() if v['source']==url and (v['url']==item['url'] or
                                (item['guid'] and item['guid'] in v.get('guids',[])))), None)
                    key = old['id'] if old else sha(url+'|'+item['url'])[:24]
                    digest = sha(item['title']+' '+item['text'])
                    kind = ('initial_inventory' if initial else 'new_article') if url == FEED else 'page_baseline'
                    if old and digest == old['content_sha256']:
                        if item['guid'] and item['guid'] not in old['guids']: old['guids'].append(item['guid'])
                        continue
                    if old: kind = 'article_summary_changed' if url == FEED else 'monitored_page_changed'
                    revision = {**item, 'content_sha256':digest, 'raw_sha256':record['raw_sha256'],
                                'retrieved_at':now.isoformat(), 'snapshot_path':record['snapshot_path'],
                                'previous_sha256':old['content_sha256'] if old else None,
                                'difference': '\n'.join(difflib.unified_diff((old['title']+' '+old['text']).split(),
                                      (item['title']+' '+item['text']).split(), lineterm='')) if old else 'First observation; no previous version.'}
                    current = {**revision, 'id':key, 'kind':kind, 'source':url,
                               'first_seen':old['first_seen'] if old else now.isoformat(),
                               'guids':list(dict.fromkeys((old['guids'] if old else [])+([item['guid']] if item['guid'] else []))),
                               'revisions':(old['revisions'] if old else [])+[revision],
                               'relevance_history':assessment_history(old) if old else [],
                               **({'semantic_assessment':old['semantic_assessment'],
                                   'semantic_history':list(old.get('semantic_history',[]))} if old and old.get('semantic_assessment') else {})}
                    # Historical rules remain inspectable but never supply current project reasoning.
                    if old and old.get('relevance'):current['relevance']=old['relevance']
                    state['items'][key] = current
                    run['events'].append({'item_id':key,'kind':kind, 'revision_sha256':digest})
                state['baselines'][url] = {'run_id':run['id'], 'raw_sha256':record['raw_sha256'], 'retrieved_at':now.isoformat()}
            except Exception as exc:
                record['error'] = str(exc) if isinstance(exc, ValueError) else 'Source could not be parsed; prior baseline retained'
        run['status'] = 'partial_failure' if any(s['error'] for s in run['sources']) else 'success'
        state['runs'].append(run)
        self.semantic_refresh(state)
        (folder/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding='utf-8')
        return self.save(state)

    def select(self, item_id, reason=None, revision_sha256=None, assessment_cache_key=None):
        if reason is None:reason=''
        if not isinstance(reason,str) or len(reason)>2000:raise ValueError('Optional user note must be at most 2000 characters.')
        with self.exclusive():
            state = self.read()
            item = state['items'].get(item_id)
            if not item: raise ValueError('Candidate is no longer available; refresh discovery.')
            if revision_sha256 is not None and revision_sha256 != item['content_sha256']:
                raise ValueError('Candidate changed since it was displayed. Reopen discovery and review its latest revision before selecting.')
            import semantic_discovery as semantic
            project=semantic.project_context(self.root)
            prepared=semantic.prepare(self,item,project)
            assessment=item.get('semantic_assessment',{})
            cached=semantic.assessment_for_prepared(state,prepared)
            if (assessment.get('status')!='validated' or assessment!=cached
                    or (assessment_cache_key and assessment_cache_key!=assessment.get('cache_key'))):
                raise ValueError('The current agent proposal is unavailable or changed. Reopen discovery and review its assessment before selecting.')
            proposal=next((p for p in state['proposals'] if p.get('origin')=='agent' and p.get('assessment_cache_key')==assessment['cache_key']),None)
            if not proposal:raise ValueError('No persisted agent proposal is available to review.')
            selections=state.setdefault('proposal_selections',[])
            if not any(s['proposal_id']==proposal['id'] for s in selections):
                selections.append({'proposal_id':proposal['id'],'selected_at':datetime.now(timezone.utc).isoformat(),
                    'user_note':reason.strip() or None,'action':'selected_for_investigation_review','approval':None,
                    'assessment_cache_key':assessment['cache_key']})
                return self.save(state)
            return state


if __name__ == '__main__':
    result = Store().run(progress=print)
    print(json.dumps(result['runs'][-1],indent=2))
