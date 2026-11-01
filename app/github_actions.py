"""Explicit developer-initiated GitHub actions. No scheduled merge or deploy."""
from pydantic import BaseModel,Field
from fastapi import HTTPException
from .github_access import api,allowed_repo

class MergeRequest(BaseModel):
    repo:str
    pr_number:int=Field(gt=0)
    expected_sha:str=Field(min_length=40,max_length=40)
    confirmation:str
class DeploymentRequest(BaseModel):
    repo:str
    workflow:str=Field(min_length=1,max_length=150)
    ref:str=Field(min_length=1,max_length=120)
    confirmation:str

def list_installation_repositories():
    """Lists accessible repositories, without automatically authorising them."""
    try:
        data=api('/installation/repositories?per_page=100')
        return [{'full_name':r['full_name'],'private':r['private'],
                 'selected':_selected(r['full_name'])} for r in data.get('repositories',[])]
    except Exception as exc:
        raise HTTPException(503,'GitHub App repository listing unavailable: '+str(exc))

def _selected(repo):
    try:allowed_repo(repo);return True
    except (PermissionError,ValueError):return False

def merge_explicitly(request:MergeRequest):
    repo=allowed_repo(request.repo)
    if request.confirmation!='MERGE '+repo+'#'+str(request.pr_number):
        raise HTTPException(400,'Explicit merge confirmation required')
    pr=api('/repos/'+repo+'/pulls/'+str(request.pr_number))
    if pr['head']['sha']!=request.expected_sha:raise HTTPException(409,'PR changed; review newest commit')
    if pr.get('draft') or pr.get('mergeable') is False:
        raise HTTPException(409,'PR is draft or has conflicts')
    # Never bypass GitHub's branch protection or required reviews.
    return api('/repos/'+repo+'/pulls/'+str(request.pr_number)+'/merge','PUT',{
        'sha':request.expected_sha,'merge_method':'squash',
        'commit_title':'TriAgent owner-approved PR #'+str(request.pr_number)})

def deploy_explicitly(request:DeploymentRequest):
    repo=allowed_repo(request.repo)
    if request.confirmation!='DEPLOY '+repo+'@'+request.ref:
        raise HTTPException(400,'Explicit deployment confirmation required')
    # Trigger an existing, trusted GitHub Actions workflow, never arbitrary code.
    from urllib.parse import quote
    workflow=quote(request.workflow,safe='')
    return api('/repos/'+repo+'/actions/workflows/'+workflow+'/dispatches','POST',{'ref':request.ref})
