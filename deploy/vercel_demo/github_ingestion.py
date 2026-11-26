"""Public GitHub repository ingestion through the fixed GitHub API host."""
import base64
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


def repository(url):
    try:
        u=urlsplit(url)
        parts=u.path.strip('/').split('/')
        if (u.scheme!='https' or u.hostname!='github.com' or u.username or u.password or u.port not in (None,443)
                or u.query or u.fragment or len(parts)!=2 or not re.fullmatch(r'[A-Za-z0-9-]{1,39}',parts[0])
                or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',parts[1]) or parts[1] in ('.','..')):
            raise ValueError()
        name=parts[1].removesuffix('.git')
        if name in ('','.','..'): raise ValueError()
        return parts[0],name
    except (ValueError,TypeError):
        raise ValueError('Enter a public GitHub repository URL.') from None


def get_json(path):
    request=Request('https://api.github.com'+path,headers={'User-Agent':'NextwisePublicMVP/1.0',
        'Accept':'application/vnd.github+json','Accept-Encoding':'identity'})
    with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=6) as response:
        data=response.read(1_000_001)
        if len(data)>1_000_000: raise ValueError('Repository response too large.')
        return json.loads(data)


def extract(url,fetch=get_json):
    owner,name=repository(url)
    if not name: raise ValueError('Enter a public GitHub repository URL.')
    path='/repos/'+owner+'/'+name
    info=fetch(path)
    if not isinstance(info,dict) or info.get('private') is not False:
        raise ValueError('Repository is unavailable or not public.')
    description=info.get('description') or ''
    if not isinstance(description,str): raise ValueError('Invalid repository metadata.')
    try:
        readme=fetch(path+'/readme')
        if readme.get('encoding')!='base64' or not isinstance(readme.get('content'),str): raise ValueError()
        decoded=base64.b64decode(readme['content'],validate=False)
        if len(decoded)>250000: raise ValueError()
        text=decoded.decode('utf-8',errors='replace')[:10000]
    except Exception:
        text='README unavailable; add project details manually.'
    return {'text':('Public repository: '+owner+'/'+name+'\nDescription: '+description[:1000]+ '\nREADME excerpt:\n'+text)[:12000],
            'notice':'Public repository content is untrusted; review and edit before discovery.'}
