"""Public, credential-free repository discovery. No visitor text or persistence."""
from datetime import datetime, timezone, timedelta
import json
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

import discovery_public as d
from identity_public import product_key, source_url
from business_public import BUSINESS_NEEDS

# Query templates describe reviewed needs, never an uploaded project's content.
QUERIES={
    'instructor':('structured_extraction','structured llm in:description'),
    'pydantic':('constraint_validation','"data validation" in:description'),
    'promptfoo':('extraction_evaluation','"evaluation" llm in:description'),
}
QUERIES.update({key:(key,rule['query']) for key,rule in BUSINESS_NEEDS.items()})
MAX_RESULTS=5
MAX_BYTES=250_000
TIMEOUT=3
DEADLINE=5


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def search(source_id):
    if source_id not in QUERIES:raise ValueError('Unsupported need')
    query=QUERIES[source_id][1]+' fork:false archived:false is:public'
    url='https://api.github.com/search/repositories?'+urlencode({'q':query,'per_page':MAX_RESULTS,'page':1})
    request=Request(url,headers={'User-Agent':'NextwisePublicDemo/1.0',
        'Accept':'application/vnd.github+json','Accept-Encoding':'identity','X-GitHub-Api-Version':'2022-11-28'})
    try:
        started=time.monotonic()
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=TIMEOUT) as response:
            if response.status!=200 or 'json' not in response.headers.get('Content-Type','').lower():raise ValueError()
            if int(response.headers.get('Content-Length','0'))>MAX_BYTES:raise ValueError()
            raw=bytearray()
            while True:
                if time.monotonic()-started>DEADLINE:raise ValueError()
                chunk=response.read1(min(65536,MAX_BYTES+1-len(raw)))
                if not chunk:break
                raw.extend(chunk)
                if len(raw)>MAX_BYTES:raise ValueError()
        result=json.loads(raw)
        if not isinstance(result,dict) or not isinstance(result.get('items'),list) or type(result.get('incomplete_results')) is not bool:raise ValueError()
        return {'items':result['items'][:MAX_RESULTS],'incomplete_results':result['incomplete_results']}
    except HTTPError as error:
        error.close();raise ValueError('Public repository search unavailable; no retry made.') from None
    except Exception:
        raise ValueError('Public repository search unavailable; no retry made.') from None


def candidate(item,need_id,now):
    if not isinstance(item,dict):return None
    if any(item.get(key) is not False for key in ('private','fork','archived','disabled')):return None
    full_name=item.get('full_name','')
    if not isinstance(full_name,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}',full_name):return None
    owner,name=full_name.split('/')
    if name in ('.','..') or item.get('name')!=name or not isinstance(item.get('owner'),dict) or item['owner'].get('login')!=owner:return None
    url='https://github.com/'+full_name
    # Validate source identity from GitHub's own repository record, not a supplied homepage.
    if item.get('html_url')!=url or item.get('url')!='https://api.github.com/repos/'+full_name:return None
    if re.search(r'\b(?:awesome|list|collection|course|tutorial|news|paper|book)\b',name,re.I):return None
    description=item.get('description')
    if not isinstance(description,str):return None
    description=re.sub(r'\s+',' ',description).strip()
    if not 40<=len(description)<=700 or re.search(r'\b(?:not|never|unsupported|roundup|collection|tutorial)\b',description,re.I):return None
    business=BUSINESS_NEEDS.get(need_id)
    pattern=business['capability_pattern'] if business else d.PROJECT_NEEDS[need_id][1]
    if not re.search(pattern,description,re.I):return None
    if need_id!='constraint_validation' and not re.search(r'\b(?:ai|llms?|agents?|language models?)\b',description,re.I):return None
    homepage=None;usability=0
    if business:
        # A repository alone is not a usable service for a nontechnical founder.
        # Require a product-site claim and user-facing interface; reject developer components.
        if re.search(r'\b(?:sdk|libraries|library|framework|package|api[- ]only|command[- ]line|cli)\b',description,re.I):return None
        if not re.search(r'\b(?:app|application|assistant|platform|service|agent|dashboard|no[- ]code)\b',description,re.I):return None
        hosted=bool(re.search(r'\b(?:cloud|no[- ]code|online|browser[- ]based|hosted service)\b',description,re.I))
        if re.search(r'\b(?:self[- ]hosted|docker|install|deploy)\b',description,re.I) and not hosted:return None
        try:
            homepage=source_url(item.get('homepage'))
            host=urlsplit(homepage).hostname
            if '.' not in host or host=='github.com' or host.startswith(('docs.','api.')) or host.endswith(('.readthedocs.io','.lan','.home')):return None
            if re.match(r'^/(?:docs?|documentation|api)(?:/|$)',urlsplit(homepage).path,re.I):return None
        except (ValueError,TypeError,AttributeError):return None
        usability=2 if hosted else 1
    try:
        created=datetime.fromisoformat(item['created_at'].replace('Z','+00:00'))
        pushed=datetime.fromisoformat(item['pushed_at'].replace('Z','+00:00'))
        if not created<=pushed<=now+timedelta(days=1):return None
    except (KeyError,ValueError,TypeError,AttributeError):return None
    identity=product_key(url)
    return {'title':name,'url':url,'publisher':owner+' on GitHub','kind':'discovered_repository',
        'need_id':need_id,'demo_source_id':'repo-'+d.sha(identity.encode())[:16],
        'publication_date':None,'retrieved_at':now.isoformat(),'description':description,
        'label':d.TOOL_LABEL,'reasons':[business['why'] if business else d.PROJECT_NEEDS[need_id][2]],'supporting_phrases':[description],
        'product_url':homepage,'usability_score':usability,
        'business_summary':business['what'] if business else None,
        'raw_sha256':d.sha(json.dumps(item,sort_keys=True).encode()),
        'evidence_url':item['url'],'evidence_type':'repository_owner_description',
        'limitations':([business['caution'],'The owner advertises a user-facing product and links a website. Website availability, hosted access, setup effort and pricing were not independently checked.'] if business else [])+[
            'Evidence is the repository owner’s description returned by GitHub search. README, code, publisher identity and performance were not independently checked.',
            'Relevance is a local capability match to a confirmed project need, not AI analysis or proof of business value.',
            'Integration, maintenance, security, license, pricing and accuracy remain unverified. No repository code, tool or model was run.']}


def discover(source_id,searcher=None,now=None):
    if source_id not in QUERIES:raise ValueError('Unsupported need')
    need_id=QUERIES[source_id][0];now=now or datetime.now(timezone.utc)
    record={'url':'https://github.com/search?'+urlencode({'q':QUERIES[source_id][1],'type':'repositories'}),
        'publisher':'GitHub public repository search','kind':'repository_search','eligible_items':0,'error':None}
    candidates=[];seen=set()
    try:
        result=(searcher or search)(source_id)
        for item in result['items'][:MAX_RESULTS]:
            tool=candidate(item,need_id,now)
            if not tool or tool['demo_source_id'] in seen:continue
            seen.add(tool['demo_source_id']);candidates.append(tool)
        candidates=sorted(candidates,key=lambda tool:tool['usability_score'],reverse=True)[:3]
        record['eligible_items']=len(candidates)
        if result['incomplete_results']:record['error']='GitHub returned incomplete search coverage; no retry made.'
    except Exception:
        record['error']='Public repository search unavailable or rate limited. No retry, paid search or catalog substitution was made.'
    return {'mode':'public_demo','source_id':source_id,'checked_at':now.isoformat(),
        'candidates':candidates,'sources':[record],
        'status':'partial_failure' if record['error'] else 'success',
        'notice':'Live public repository search beyond the fixed catalog. Owner descriptions support capability claims only; candidates are unvalidated.'}
