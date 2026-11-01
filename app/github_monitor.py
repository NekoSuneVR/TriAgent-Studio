"""Optional read-only GitHub Actions poller. Queues repair work; never pushes automatically."""
import json, os, time, urllib.request, urllib.error
from .core import db, make_job

def api(path):
    token=os.getenv('GITHUB_MONITOR_TOKEN','')
    if not token:raise RuntimeError('Set GITHUB_MONITOR_TOKEN')
    req=urllib.request.Request('https://api.github.com'+path,headers={
        'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28','User-Agent':'TriAgent-Studio'})
    with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)

def poll_once():
    repo=os.getenv('GITHUB_MONITOR_REPO','').strip()
    if not repo or not __import__('re').fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
        raise ValueError('Set a valid GITHUB_MONITOR_REPO in owner/repository format')
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
            if os.getenv('GITHUB_MONITOR_ENABLED','false').lower()=='true':poll_once()
        except Exception as e:print('GitHub Actions monitor:',str(e),flush=True)
        time.sleep(max(60,int(os.getenv('GITHUB_POLL_SECONDS','180'))))

if __name__=='__main__':main()
