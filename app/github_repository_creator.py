"""Create GitHub repositories with an installed GitHub App scoped to a known owner.

GitHub App installation tokens cannot always create repositories. The create
operation needs an explicitly configured user or organisation token with the
appropriate permission; no implicit escalation or credential sharing.
"""
import os,re
from pydantic import BaseModel,Field
from fastapi import HTTPException
from .github_access import api

class RepoCreateRequest(BaseModel):
    owner:str=Field(min_length=1,max_length=100)
    name:str=Field(pattern=r'^[A-Za-z0-9_.-]{1,100}$')
    private:bool=True
    description:str=Field(default='',max_length=500)
    confirmation:str

def create_repository(data:RepoCreateRequest):
    allowed={x.strip().lower() for x in os.getenv('GITHUB_CREATE_OWNERS','').split(',') if x.strip()}
    if data.owner.lower() not in allowed:raise HTTPException(403,'Owner not permitted for creation')
    if data.confirmation!='CREATE '+data.owner+'/'+data.name:
        raise HTTPException(400,'Explicit repo creation confirmation required')
    # Creation is disabled by default: requires a scoped owner-authorised credential.
    token=os.getenv('GITHUB_REPO_CREATE_TOKEN','')
    if not token:raise HTTPException(503,'Configure GITHUB_REPO_CREATE_TOKEN for owner-authorised creation')
    import urllib.request,json
    body={'name':data.name,'private':data.private,'description':data.description,'auto_init':True}
    url='https://api.github.com/user/repos'
    # Org creation requires org-specific repository creation permissions.
    if os.getenv('GITHUB_CREATE_ORG','').lower()==data.owner.lower():
        url='https://api.github.com/orgs/'+data.owner+'/repos'
    req=urllib.request.Request(url,data=json.dumps(body).encode(),method='POST',headers={
        'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
        'Content-Type':'application/json','User-Agent':'TriAgent-Studio'})
    try:
        with urllib.request.urlopen(req,timeout=30) as result:
            info=json.load(result)
    except urllib.error.HTTPError as exc:
        raise HTTPException(exc.code,'GitHub rejected repository creation; check owner/token scopes')
    if info.get('owner',{}).get('login','').lower()!=data.owner.lower():
        raise HTTPException(409,'Created repository owner did not match requested owner')
    return {'full_name':info['full_name'],'html_url':info['html_url'],'private':info['private']}
