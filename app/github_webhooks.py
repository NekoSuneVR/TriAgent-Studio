"""Verify and ingest GitHub push and workflow webhooks; no blind writes."""
import hashlib,hmac,json,os,time
from fastapi import APIRouter,Request,HTTPException
from .core import db
from .github_access import allowed_repo

router=APIRouter()
@router.post('/api/github/webhook')
async def webhook(request:Request):
    secret=os.getenv('GITHUB_WEBHOOK_SECRET','')
    if len(secret)<24:raise HTTPException(503,'GITHUB_WEBHOOK_SECRET not configured')
    raw=await request.body()
    if len(raw)>2_000_000:raise HTTPException(413,'Payload too large')
    expected='sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get('x-hub-signature-256',''),expected):
        raise HTTPException(401,'Invalid webhook signature')
    payload=json.loads(raw)
    try:repo=allowed_repo(payload.get('repository',{}).get('full_name',''))
    except (ValueError,PermissionError):raise HTTPException(403,'Repository not authorised')
    kind=request.headers.get('x-github-event','')
    delivery=request.headers.get('x-github-delivery','')
    if not delivery or len(delivery)>100:raise HTTPException(400,'Missing delivery id')
    if kind not in ('push','pull_request','workflow_run','code_scanning_alert','dependabot_alert','security_advisory'):
        return {'accepted':False}
    conn=db()
    conn.execute('CREATE TABLE IF NOT EXISTS github_events (delivery TEXT PRIMARY KEY, repo TEXT, kind TEXT, summary TEXT, ts INTEGER)')
    if kind=='push':
        summary='Push '+str(payload.get('ref',''))+' '+str(payload.get('after',''))[:12]
    elif kind=='workflow_run':
        run=payload.get('workflow_run',{})
        summary='Workflow '+str(run.get('name'))+' '+str(run.get('conclusion'))
    else:
        summary=kind+' '+str(payload.get('action',''))
    conn.execute('INSERT OR IGNORE INTO github_events VALUES(?,?,?,?,?)',(delivery,repo,kind,summary[:400],int(time.time())))
    conn.commit();conn.close()
    return {'accepted':True}

def recent_events(limit=50):
    conn=db()
    conn.execute('CREATE TABLE IF NOT EXISTS github_events (delivery TEXT PRIMARY KEY, repo TEXT, kind TEXT, summary TEXT, ts INTEGER)')
    rows=[dict(x) for x in conn.execute('SELECT repo,kind,summary,ts FROM github_events ORDER BY ts DESC LIMIT ?', (limit,))]
    conn.close()
    return rows
