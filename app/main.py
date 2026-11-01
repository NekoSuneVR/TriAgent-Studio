import os, time
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .core import db, make_job, ROOT
from .auth import auth, login, LoginInput
from .providers import public_config
from .github_webhooks import router as github_webhook_router, recent_events
from .github_publish import publish_job
from .github_actions import list_installation_repositories, merge_explicitly, deploy_explicitly, MergeRequest, DeploymentRequest
from .github_repository_creator import RepoCreateRequest,create_repository
from .github_settings import current as github_settings_current, update as github_settings_update
class GithubSettingsUpdate(BaseModel):
    changes:dict[str,str|int|bool]

app_placeholder = None

app=FastAPI(title='TriAgent VPS',docs_url=None,redoc_url=None,openapi_url=None)
app.include_router(github_webhook_router)
class JobInput(BaseModel):
    name:str=Field(min_length=1,max_length=60)
    prompt:str=Field(min_length=10,max_length=12000)
    repository:str=Field(default='',max_length=300)
    template:str=Field(default='general',max_length=40)

@app.get('/')
def index():return FileResponse(Path(__file__).parent/'static'/'index.html')
@app.post('/api/auth/login')
def login_route(payload:LoginInput,request:Request):return login(payload,request)
@app.post('/api/github/repositories',dependencies=[Depends(auth)])
def github_create_repo(payload:RepoCreateRequest):return create_repository(payload)
@app.get('/api/github/repositories',dependencies=[Depends(auth)])
def github_repositories():return list_installation_repositories()
@app.post('/api/github/merge',dependencies=[Depends(auth)])
def github_merge(request:MergeRequest):return merge_explicitly(request)
@app.post('/api/github/deploy',dependencies=[Depends(auth)])
def github_deploy(request:DeploymentRequest):return deploy_explicitly(request)
@app.get('/api/github/settings',dependencies=[Depends(auth)])
def github_settings_read():return github_settings_current()
@app.put('/api/github/settings',dependencies=[Depends(auth)])
def github_settings_write(payload:GithubSettingsUpdate):
    try:return github_settings_update(payload.changes)
    except ValueError as exc:raise HTTPException(400,str(exc))
@app.get('/api/github/events',dependencies=[Depends(auth)])
def github_events():return recent_events()
@app.post('/api/jobs/{jid}/publish',dependencies=[Depends(auth)])
def publish(jid:str):
    try:return publish_job(jid)
    except (ValueError,PermissionError,RuntimeError,KeyError) as exc:raise HTTPException(409,str(exc))
@app.get('/api/providers',dependencies=[Depends(auth)])
def providers():return public_config()
@app.get('/api/status',dependencies=[Depends(auth)])
def status():
    c=db(); rows=c.execute('SELECT status,COUNT(*) as n FROM jobs GROUP BY status').fetchall()
    return {'jobs':{r['status']:r['n'] for r in rows},'workers':['frontend','backend','review']}
@app.post('/api/jobs',dependencies=[Depends(auth)])
def create(payload:JobInput):
    try:return {'id':make_job(payload.name,payload.prompt,payload.repository,payload.template)}
    except (ValueError,RuntimeError) as e:raise HTTPException(400,str(e))
@app.get('/api/jobs',dependencies=[Depends(auth)])
def jobs():
    c=db();items=[dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 100')]
    for j in items:j['stages']=[dict(s) for s in c.execute('SELECT role,status,detail FROM stages WHERE job_id=?',(j['id'],))]
    return items
@app.get('/api/jobs/{jid}',dependencies=[Depends(auth)])
def detail(jid:str):
    c=db();row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
    if not row:raise HTTPException(404,'Not found')
    item=dict(row);item['stages']=[dict(r) for r in c.execute('SELECT * FROM stages WHERE job_id=?',(jid,))]
    item['events']=[dict(r) for r in c.execute('SELECT role,message,ts FROM events WHERE job_id=? ORDER BY id DESC LIMIT 150',(jid,))][::-1]
    item['project_path']=f'./data/projects/{jid}'
    item['branch']=f'job-{jid}-integrated'
    return item
@app.post('/api/jobs/{jid}/cancel',dependencies=[Depends(auth)])
def cancel(jid:str):
    c=db();row=c.execute('SELECT status FROM jobs WHERE id=?',(jid,)).fetchone()
    if not row:raise HTTPException(404,'Not found')
    if row['status']!='running':raise HTTPException(409,'Not running')
    c.execute('UPDATE jobs SET status="cancelled",updated=? WHERE id=?',(int(time.time()),jid));c.commit()
    return {'status':'cancelled'}
