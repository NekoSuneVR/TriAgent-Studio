"""Optional read-only GitHub Actions poller. Queues repair work; never pushes automatically."""
import json, os, time
from .core import db, make_job
from .github_access import api, allowed_repo
from .github_settings import get, enabled

def poll_once():
    repo=get('monitor_repo').strip()
    if not repo or not __import__('re').fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
        raise ValueError('Set a valid GITHUB_MONITOR_REPO in owner/repository format')
    allowed_repo(repo)
    runs=api('/repos/'+repo+'/actions/runs?status=completed&per_page=20').get('workflow_runs',[])
    conn=db()
    conn.execute('CREATE TABLE IF NOT EXISTS workflow_seen (run_id INTEGER PRIMARY KEY, repo TEXT, conclusion TEXT, job_id TEXT, created INTEGER)')
    conn.commit()
    for r in runs:
        if r.get('conclusion') not in ('failure','timed_out'):continue
        rid=int(r['id'])
        if conn.execute('SELECT 1 FROM workflow_seen WHERE run_id=?',(rid,)).fetchone():continue
        jobs=api('/repos/'+repo+'/actions/runs/'+str(rid)+'/jobs?per_page=100').get('jobs',[])
        details=[]
        for j in jobs:
            if j.get('conclusion') in ('failure','timed_out'):
                failed=[x['name'] for x in j.get('steps',[]) if x.get('conclusion')=='failure']
                details.append('Job '+str(j.get('name'))+'; failed steps: '+', '.join(failed))
        prompt=('Investigate and propose code changes to fix this failed GitHub Actions run. '
                'Run safe tests, avoid changing security controls merely to make CI pass. '
                'Changes must be manually reviewed before publication.\n'
                'Repository: '+repo+'\nWorkflow: '+str(r.get('name'))+
                '\nRef: '+str(r.get('head_branch'))+'\nCommit: '+str(r.get('head_sha'))+
                '\nRun URL: '+str(r.get('html_url'))+'\nFailures: '+'; '.join(details))
        try:
            jid=make_job('ci-repair-'+str(rid),prompt,'https://github.com/'+repo)
        except ValueError as exc:
            print('Unable to queue run',rid,str(exc),flush=True)
            continue
        conn.execute('INSERT INTO workflow_seen VALUES(?,?,?,?,?)',(rid,repo,str(r['conclusion']),jid,int(time.time())))
        conn.commit()
        print('Queued GitHub Actions repair job',jid,flush=True)
    conn.close()

def main():
    while True:
        try:
            if enabled('monitor_enabled'):poll_once()
        except Exception as e:print('GitHub Actions monitor:',str(e),flush=True)
        time.sleep(max(60,int(get('poll_seconds'))))

if __name__=='__main__':main()
