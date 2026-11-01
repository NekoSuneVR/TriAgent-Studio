"""Publish a *reviewed and validated* local repair as a GitHub PR; never merge."""
import os,subprocess,re,tempfile,pathlib
from .core import db, ROOT
from .github_access import _get_token,api,allowed_repo

def publish_job(jid):
    conn=db()
    job=conn.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
    if not job or job['status']!='ready_for_review':raise ValueError('Job is not ready for review')
    repo_url=job['repository'] or ''
    match=re.fullmatch(r'https://github\.com/([\w.-]+/[\w.-]+)(?:\.git)?',repo_url)
    if not match:raise ValueError('Publishing requires a GitHub repository')
    repo=allowed_repo(match.group(1))
    project=ROOT/'projects'/jid
    branch='job-'+jid+'-integrated'
    # A successful local review alone is NOT adequate verification.
    # Require owner-configured CI to have passed on the exact branch HEAD.
    sha=subprocess.check_output(['git','rev-parse',branch],cwd=project,text=True).strip()
    checks=api('/repos/'+repo+'/commits/'+sha+'/check-runs')
    if not any(x.get('conclusion')=='success' for x in checks.get('check_runs',[])):
        raise ValueError('No successful GitHub checks for exact commit; publish using the GitHub Actions workflow instead')
    # Published branches must already be on remote for matching checks to exist.
    # This function only opens PRs; it never bypasses CI or protected branches.
    head=api('/repos/'+repo+'/git/ref/heads/'+branch)
    if head['object']['sha']!=sha:raise ValueError('Remote branch differs from locally validated commit')
    base=os.getenv('GITHUB_PR_BASE','main')
    response=api('/repos/'+repo+'/pulls','POST',{
        'title':'TriAgent verified repair '+jid,
        'head':branch,'base':base,
        'body':'AI-assisted repair. Validated check runs were detected for the exact commit. Review required; no auto-merge.'
    })
    conn.close()
    return {'url':response['html_url'],'number':response['number']}
