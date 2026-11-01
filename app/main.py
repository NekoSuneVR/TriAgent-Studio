import os, time, secrets
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .core import db, make_job, ROOT

app=FastAPI(title='TriAgent VPS',docs_url=None,redoc_url=None,openapi_url=None)
TOKEN=os.getenv('DASHBOARD_TOKEN','')

def auth(authorization: str|None=Header(None)):
    if not TOKEN or TOKEN=='REPLACE_WITH_LONG_RANDOM_SECRET':raise HTTPException(503,'Set DASHBOARD_TOKEN in .env')
    if not authorization or not authorization.startswith('Bearer ') or not secrets.compare_digest(authorization[7:],TOKEN):raise HTTPException(401,'Invalid dashboard token')

class JobInput(BaseModel):
    name:str=Field(min_length=1,max_length=60)
    prompt:str=Field(min_length=10,max_length=12000)
    repository:str=Field(default='',max_length=300)

@app.get('/')
def index():return FileResponse(Path(__file__).parent/'static'/'index.html')
@app.get('/api/status',dependencies=[Depends(auth)])
def status():
    c=db(); rows=c.execute('SELECT status,COUNT(*) as n FROM jobs GROUP BY status').fetchall()
    return {'jobs':{r['status']:r['n'] for r in rows},'workers':['frontend','backend','review']}
@app.post('/api/jobs',dependencies=[Depends(auth)])
def create(payload:JobInput):
    try:return {'id':make_job(payload.name,payload.prompt,payload.repository)}
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
