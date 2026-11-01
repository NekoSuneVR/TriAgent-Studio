"""GitHub App installation access for private repositories without user PATs.

Use GitHub App permissions: Contents read/write, Pull requests read/write,
Actions read, Metadata read, and optional security-alert read. Install the App
only on explicitly selected repositories. Private key remains server-side.
"""
import os,time,urllib.request,urllib.error,json,re,base64
from functools import lru_cache

def _get_token():
    pat=os.getenv('GITHUB_MONITOR_TOKEN','')
    app_id=os.getenv('GITHUB_APP_ID','')
    install=os.getenv('GITHUB_APP_INSTALLATION_ID','')
    key=os.getenv('GITHUB_APP_PRIVATE_KEY','').replace('\\n','\n')
    if not all((app_id,install,key)):
        if pat:return pat
        raise RuntimeError('Configure GitHub App credentials or GITHUB_MONITOR_TOKEN')
    import jwt
    now=int(time.time())
    assertion=jwt.encode({'iat':now-60,'exp':now+480,'iss':app_id},key,algorithm='RS256')
    req=urllib.request.Request(
        'https://api.github.com/app/installations/'+install+'/access_tokens',
        data=b'{}',method='POST',headers={'Authorization':'Bearer '+assertion,
        'Accept':'application/vnd.github+json','User-Agent':'TriAgent-Studio'})
    with urllib.request.urlopen(req,timeout=25) as response:
        return json.load(response)['token']

def api(path,method='GET',body=None):
    if not path.startswith('/') or '://' in path:raise ValueError('Invalid GitHub API path')
    payload=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request('https://api.github.com'+path,method=method,data=payload,
        headers={'Authorization':'Bearer '+_get_token(),
        'Accept':'application/vnd.github+json','Content-Type':'application/json',
        'X-GitHub-Api-Version':'2022-11-28','User-Agent':'TriAgent-Studio'})
    with urllib.request.urlopen(req,timeout=35) as response:
        raw=response.read()
        return json.loads(raw) if raw else {}

def allowed_repo(repo):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
        raise ValueError('Invalid repository')
    allowed={x.strip().lower() for x in os.getenv('GITHUB_ALLOWED_REPOS','').split(',') if x.strip()}
    if repo.lower() not in allowed:raise PermissionError('Repository not in GITHUB_ALLOWED_REPOS')
    return repo
