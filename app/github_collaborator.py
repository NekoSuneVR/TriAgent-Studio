"""GitHub collaborator: PR review, security advisory monitoring, and human-authorised operations.

Poll repositories explicitly allowlisted by the owner. PR feedback is advisory;
never modify fork-owned branches. All GitHub mutations use installation permissions.
"""
import os,time,re,urllib.parse
from .core import db,make_job
from .github_access import api,allowed_repo

def repos():
    return [allowed_repo(r.strip()) for r in os.getenv('GITHUB_ALLOWED_REPOS','').split(',') if r.strip()]

def ensure_tables(c):
    c.execute('CREATE TABLE IF NOT EXISTS github_assistant_events (repo TEXT, kind TEXT, source_id TEXT, outcome TEXT, ts INTEGER, PRIMARY KEY(repo,kind,source_id))')
    c.execute('CREATE TABLE IF NOT EXISTS github_approvals (repo TEXT, operation TEXT, subject TEXT, approved_by TEXT, ts INTEGER, PRIMARY KEY(repo,operation,subject))')
    c.commit()

def issue_comment(repo,number,message):
    allowed_repo(repo)
    return api('/repos/'+repo+'/issues/'+str(int(number))+'/comments','POST',{'body':message[:65000]})

def once(c,repo,kind,source_id,operation):
    if c.execute('SELECT 1 FROM github_assistant_events WHERE repo=? AND kind=? AND source_id=?',(repo,kind,str(source_id))).fetchone():
        return False
    outcome=operation()
    c.execute('INSERT INTO github_assistant_events VALUES(?,?,?,?,?)',(repo,kind,str(source_id),str(outcome)[:300],int(time.time())))
    c.commit()
    return True

def scan_pull_requests(c,repo):
    pulls=api('/repos/'+repo+'/pulls?state=open&per_page=40')
    for pr in pulls:
        number=pr['number']
        head=pr['head']['sha']
        source=str(number)+':'+head
        def review():
            files=api('/repos/'+repo+'/pulls/'+str(number)+'/files?per_page=100')
            risky=[]
            for f in files:
                patch=f.get('patch','')
                added=[line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++')]
                for line in added:
                    # Heuristics only, not verified vulnerabilities.
                    if re.search(r'\b(eval|exec)\s*\(|shell\s*=\s*True|child_process\.exec\s*\(|pickle\.loads\s*\(',line):
                        risky.append(f['filename']+': suspicious code execution API')
                    if re.search(r'(password|secret|api_key)\s*[=:]\s*["\x27][^"\x27]{12,}',line,re.I):
                        risky.append(f['filename']+': possible hard-coded credential')
            summary=('I reviewed the changed lines for common dangerous patterns. '+
                ('Potential issues to investigate:\n'+'\n'.join('- '+x for x in sorted(set(risky))[:20])
                if risky else 'No high-risk patterns matched these limited heuristics. This is **not** a security audit.'))
            issue_comment(repo,number,'**TriAgent advisory review** (commit `'+head[:12]+'`)\n\n'+summary+
                '\n\nAutomated review can miss vulnerabilities and may produce false positives. A human should inspect the code.')
            # Only enqueue a repair for a branch owned by this repository, not a contributor fork.
            if risky and pr['head']['repo']['full_name'].lower()==repo.lower() and os.getenv('GITHUB_AUTO_REPAIR_PRS','false').lower()=='true':
                prompt=('Investigate potential code-execution and credential risks in pull request #'+str(number)+
                    ' at '+head+'. Do not assume heuristics prove vulnerability. Create code changes and tests for confirmed problems; do not merge.\n'+summary)
                make_job('pr-review-'+str(number),prompt,'https://github.com/'+repo)
            return 'commented'
        try:once(c,repo,'pr_review',source,review)
        except Exception as exc:print('PR review error:',repo,number,str(exc),flush=True)

def security_alerts(c,repo):
    # Dependabot and code-scanning alerts are useful even without recent commits.
    for kind,path in [('dependabot','dependabot/alerts?state=open&per_page=100'),('code_scanning','code-scanning/alerts?state=open&per_page=100')]:
        try:alerts=api('/repos/'+repo+'/'+path)
        except Exception as exc:
            print('Security alert access unavailable:',repo,kind,str(exc),flush=True)
            continue
        for a in alerts:
            ident=str(a.get('number') or a.get('id'))
            def notify():
                severity=(a.get('security_advisory') or {}).get('severity') or (a.get('rule') or {}).get('security_severity_level') or 'unknown'
                url=a.get('html_url','')
                title=(a.get('security_advisory') or {}).get('summary') or (a.get('rule') or {}).get('description') or kind
                issue=api('/repos/'+repo+'/issues','POST',{'title':'[TriAgent security] '+str(title)[:150],
                    'body':'Security alert detected on a scheduled check, including inactive repositories.\n\n'+
                    'Severity: '+str(severity)+'\nAlert: '+url+
                    '\n\nInvestigate and confirm impact before applying changes. Do not expose exploits or secrets in comments.'})
                if os.getenv('GITHUB_AUTO_REPAIR_SECURITY','false').lower()=='true':
                    make_job('security-'+kind+'-'+ident,
                        'Investigate and remediate the security alert '+url+' in '+repo+'. Add a regression test and verify safely. Do not merge automatically.',
                        'https://github.com/'+repo)
                return issue.get('html_url','notified')
            try:once(c,repo,'security_'+kind,ident,notify)
            except Exception as exc:print('Security notification error:',repo,ident,str(exc),flush=True)

def poll():
    c=db()
    ensure_tables(c)
    for repo in repos():
        if os.getenv('GITHUB_REVIEW_PRS','false').lower()=='true':scan_pull_requests(c,repo)
        if os.getenv('GITHUB_SECURITY_WATCH','false').lower()=='true':security_alerts(c,repo)
    c.close()

def main():
    while True:
        try:poll()
        except Exception as exc:print('GitHub collaborator error:',str(exc),flush=True)
        time.sleep(max(300,int(os.getenv('GITHUB_COLLABORATOR_SECONDS','1800'))))

if __name__=='__main__':main()
