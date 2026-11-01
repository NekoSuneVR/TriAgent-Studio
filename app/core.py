import os, re, sqlite3, subprocess, time, json, uuid, pathlib, fcntl
from contextlib import contextmanager

ROOT=pathlib.Path('/data')
DB=ROOT/'tasks.sqlite3'
ROLES=('frontend','backend','review')

def db():
    ROOT.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB, timeout=30)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=30000')
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, name TEXT, prompt TEXT, status TEXT, created INTEGER, updated INTEGER, error TEXT DEFAULT "", repository TEXT DEFAULT "")')
    c.execute('CREATE TABLE IF NOT EXISTS stages (job_id TEXT, role TEXT, status TEXT, detail TEXT DEFAULT "", updated INTEGER, PRIMARY KEY(job_id,role))')
    c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, role TEXT, message TEXT, ts INTEGER)')
    c.commit()
    return c

def run(args, cwd=None, timeout=100, check=True):
    p=subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout, env={**os.environ,'GIT_AUTHOR_NAME':'TriAgent','GIT_AUTHOR_EMAIL':'triagent@localhost','GIT_COMMITTER_NAME':'TriAgent','GIT_COMMITTER_EMAIL':'triagent@localhost'}, start_new_session=True)
    if check and p.returncode: raise RuntimeError(f'{args[0]} exit {p.returncode}: {(p.stderr or p.stdout)[-1800:]}')
    return (p.stdout+'\n'+p.stderr)[-8000:]

def safe_name(name):
    n=re.sub(r'[^a-z0-9-]+','-',name.lower()).strip('-')[:50]
    if not n: raise ValueError('Invalid project name')
    return n

def event(conn,job_id,role,msg):
    conn.execute('INSERT INTO events(job_id,role,message,ts) VALUES(?,?,?,?)',(job_id,role,msg[:5000],int(time.time())))
    conn.commit()

def make_job(name,prompt,repository=''):
    name=safe_name(name)
    if not (10 <= len(prompt) <= 12000): raise ValueError('Prompt must be 10–12000 characters')
    if repository and not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?', repository):
        raise ValueError('Only public GitHub HTTPS clone URLs are currently supported')
    conn=db(); now=int(time.time()); jid=uuid.uuid4().hex[:12]
    today=now-86400
    if conn.execute('SELECT COUNT(*) FROM jobs WHERE created>=?',(today,)).fetchone()[0]>=int(os.getenv('MAX_TASKS_PER_DAY','20')):
        raise ValueError('Daily job limit reached')
    project=ROOT/'projects'/jid
    project.parent.mkdir(exist_ok=True)
    if repository:
        from .github_access import allowed_repo
        from .github_git import git_with_token
        match=re.fullmatch(r'https://github\\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\\.git)?',repository)
        owner_repo=match.group(1) if match else ''
        try:
            allowed_repo(owner_repo)
            git_with_token(['clone','--depth','1',repository,str(project)],timeout=100)
        except PermissionError:
            # Non-allowlisted repositories may only be cloned anonymously.
            run(['git','clone','--depth','1',repository,str(project)],timeout=100)
    else:
        project.mkdir()
        (project/'README.md').write_text(f'# {name}\n\nCreated with TriAgent.\n')
        run(['git','init','-b','main'],cwd=project)
        run(['git','add','.'],cwd=project)
        run(['git','commit','-m','Initialize project'],cwd=project)
    run(['git','checkout','-b',f'job-{jid}-integrated'],cwd=project)
    for role in ('frontend','backend'):
        ws=workspace(jid,role)
        ws.parent.mkdir(parents=True,exist_ok=True)
        run(['git','worktree','add','-b',f'job-{jid}-{role}',str(ws),'HEAD'],cwd=project)
    conn.execute('INSERT INTO jobs(id,name,prompt,status,created,updated,repository) VALUES(?,?,?,?,?,?,?)',(jid,name,prompt,'running',now,now,repository))
    for role in ROLES:
        conn.execute('INSERT INTO stages(job_id,role,status,updated) VALUES(?,?,?,?)',(jid,role,'pending' if role!='review' else 'blocked',now))
    conn.commit(); event(conn,jid,'system','Project created. Frontend and backend agents queued.')
    return jid

def workspace(jid,role):return ROOT/'workspaces'/f'{jid}-{role}'

def claim(role):
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT s.job_id FROM stages s JOIN jobs j ON j.id=s.job_id WHERE s.role=? AND s.status="pending" AND j.status="running" ORDER BY j.created LIMIT 1',(role,)).fetchone()
        if not row: c.rollback(); return None
        jid=row['job_id']
        c.execute('UPDATE stages SET status="running",updated=? WHERE job_id=? AND role=?',(int(time.time()),jid,role));c.commit()
        return jid
    finally:c.close()

@contextmanager
def project_lock(jid):
    p=ROOT/'projects'/jid/'.triagent.lock'
    with open(p,'w') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)

def finish(jid,role,ok,detail=''):
    c=db(); now=int(time.time()); status='done' if ok else 'failed'
    c.execute('UPDATE stages SET status=?,detail=?,updated=? WHERE job_id=? AND role=?',(status,detail[-2000:],now,jid,role))
    event(c,jid,role,'Completed' if ok else 'Failed: '+detail[-1500:])
    c.execute('UPDATE jobs SET updated=? WHERE id=?',(now,jid));c.commit()
    if not ok:
        c.execute('UPDATE jobs SET status="failed",error=? WHERE id=?',(f'{role}: {detail[-1500:]}',jid)); c.commit(); c.close();return
    if role=='review':
        try:
            with project_lock(jid):
                repo=ROOT/'projects'/jid
                run(['git','merge','--no-ff','--no-edit',f'job-{jid}-review'],cwd=repo,timeout=90)
        except Exception as exc:
            run(['git','merge','--abort'],cwd=ROOT/'projects'/jid,check=False)
            c.execute('UPDATE jobs SET status="failed",error=? WHERE id=?',(f'Review merge: {exc}',jid));c.commit();c.close();return
        c.execute('UPDATE jobs SET status="ready_for_review" WHERE id=?',(jid,));c.commit();c.close();return
    stages={r['role']:r['status'] for r in c.execute('SELECT role,status FROM stages WHERE job_id=?',(jid,))}
    if stages['frontend']=='done' and stages['backend']=='done':
        with project_lock(jid):
            # Guard against two workers both attempting the integration.
            c.execute('BEGIN IMMEDIATE')
            current=c.execute('SELECT status FROM stages WHERE job_id=? AND role="review"',(jid,)).fetchone()['status']
            if current!='blocked':c.rollback();c.close();return
            c.execute('UPDATE stages SET status="integrating" WHERE job_id=? AND role="review"',(jid,));c.commit()
            repo=ROOT/'projects'/jid
            try:
                for part in ('backend','frontend'):
                    run(['git','merge','--no-ff','--no-edit',f'job-{jid}-{part}'],cwd=repo,timeout=90)
                ws=workspace(jid,'review');ws.parent.mkdir(parents=True,exist_ok=True)
                run(['git','worktree','add','-b',f'job-{jid}-review',str(ws),'HEAD'],cwd=repo)
                c.execute('UPDATE stages SET status="pending",updated=? WHERE job_id=? AND role="review"',(int(time.time()),jid));c.commit()
                event(c,jid,'system','Both agents merged. Review agent queued.')
            except Exception as exc:
                run(['git','merge','--abort'],cwd=repo,check=False)
                msg='Integration conflict: '+str(exc)
                c.execute('UPDATE stages SET status="failed",detail=? WHERE job_id=? AND role="review"',(msg[-2000:],jid))
                c.execute('UPDATE jobs SET status="failed",error=? WHERE id=?',(msg[-2000:],jid));c.commit()
                event(c,jid,'system',msg)
    c.close()
