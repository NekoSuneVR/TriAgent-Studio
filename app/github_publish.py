"""Automated publication of validated repair branches as reviewable pull requests.

The background publisher pushes a new repair branch, waits for GitHub's
CI and security checks, then creates a PR. It never merges or deploys.
"""
import os,re,subprocess,time
from .core import db, ROOT
from .github_access import api,allowed_repo
from .github_git import git_with_token
from .github_settings import get, enabled

def identifiers(job):
    m=re.fullmatch(r'https://github\.com/([\w.-]+/[\w.-]+)(?:\.git)?',job['repository'] or '')
    if not m:raise ValueError('Only GitHub-backed repair jobs can publish')
    return allowed_repo(m.group(1))

def branch_and_sha(jid):
    project=ROOT/'projects'/jid
    branch='job-'+jid+'-integrated'
    sha=subprocess.check_output(['git','rev-parse',branch],cwd=project,text=True).strip()
    return project,branch,sha

def publish_job(jid):
    """Push candidate branch; return pending until checks have passed; create PR once."""
    conn=db()
    conn.execute('CREATE TABLE IF NOT EXISTS publications (job_id TEXT PRIMARY KEY, sha TEXT, status TEXT, url TEXT DEFAULT "", updated INTEGER)')
    job=conn.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
    if not job or job['status']!='ready_for_review':
        raise ValueError('Job must be ready for review')
    repo=identifiers(job)
    project,branch,sha=branch_and_sha(jid)
    previous=conn.execute('SELECT * FROM publications WHERE job_id=?',(jid,)).fetchone()
    if previous and previous['sha']!=sha:raise ValueError('Repair branch changed after publication started')
    if previous and previous['status']=='published':return {'status':'published','url':previous['url']}
    if not previous:
        git_with_token(['push','--porcelain','origin',branch+':refs/heads/'+branch],cwd=project)
        conn.execute('INSERT INTO publications(job_id,sha,status,updated) VALUES(?,?,?,?)',(jid,sha,'waiting_ci',int(time.time())))
        conn.commit()
        return {'status':'waiting_ci','branch':branch}
    # Require the three named CI jobs to finish and succeed on the exact SHA.
    runs=api('/repos/'+repo+'/commits/'+sha+'/check-runs?per_page=100').get('check_runs',[])
    latest={}
    for check in sorted(runs,key=lambda x:x.get('started_at') or ''):
        latest[check.get('name','')]=check
    required=('python-checks','docker','security')
    if not all(name in latest for name in required):
        return {'status':'waiting_ci','missing_checks':[x for x in required if x not in latest]}
    failed=[name for name in required if latest[name].get('conclusion') in ('failure','cancelled','timed_out','action_required')]
    if failed:
        conn.execute('UPDATE publications SET status=?,updated=? WHERE job_id=?',('checks_failed',int(time.time()),jid));conn.commit()
        return {'status':'checks_failed','failed':failed}
    if any(latest[name].get('conclusion')!='success' for name in required):
        return {'status':'waiting_ci'}
    # GitHub's branch protection can require human review before merge.
    existing=api('/repos/'+repo+'/pulls?state=open&head='+repo.split('/')[0]+':'+branch)
    if existing:
        result=existing[0]
    else:
        result=api('/repos/'+repo+'/pulls','POST',{
            'title':'TriAgent verified repair '+jid,'head':branch,
            'base':os.getenv('GITHUB_PR_BASE','main'),
            'body':'AI-assisted change. Python, container and security CI checks succeeded on '+sha+'. Review and approval required; this service does not auto-merge.'})
    url=result['html_url']
    conn.execute('UPDATE publications SET status=?,url=?,updated=? WHERE job_id=?',('published',url,int(time.time()),jid));conn.commit()
    return {'status':'published','url':url}

def publish_ready():
    if not enabled('autopublish'):return
    conn=db()
    conn.execute('CREATE TABLE IF NOT EXISTS publications (job_id TEXT PRIMARY KEY, sha TEXT, status TEXT, url TEXT DEFAULT "", updated INTEGER)')
    rows=conn.execute("""SELECT j.id FROM jobs j LEFT JOIN publications p ON j.id=p.job_id
                         WHERE j.status='ready_for_review' AND j.repository LIKE 'https://github.com/%'
                         AND (p.status IS NULL OR p.status='waiting_ci') ORDER BY j.created DESC LIMIT 10""").fetchall()
    conn.close()
    for row in rows:
        try:print('Publication check',row['id'],publish_job(row['id']),flush=True)
        except Exception as exc:print('Publication error',row['id'],str(exc),flush=True)

def main():
    while True:
        try:publish_ready()
        except Exception as exc:print('Publisher error:',str(exc),flush=True)
        time.sleep(max(30,int(get('poll_seconds'))))

if __name__=='__main__':main()
