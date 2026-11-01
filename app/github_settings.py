"""Dashboard-managed GitHub automation policy. Secrets stay in environment variables.

The dashboard may only select repositories already admitted by GITHUB_ALLOWED_REPOS
and the GitHub App installation. Never let a web request expand server-side scope.
"""
import os, re
from .core import db

DEFAULTS = {
    'monitor_enabled': 'GITHUB_MONITOR_ENABLED',
    'monitor_repo': 'GITHUB_MONITOR_REPO',
    'poll_seconds': 'GITHUB_POLL_SECONDS',
    'autopublish': 'GITHUB_AUTOPUBLISH',
    'review_prs': 'GITHUB_REVIEW_PRS',
    'security_watch': 'GITHUB_SECURITY_WATCH',
    'auto_repair_prs': 'GITHUB_AUTO_REPAIR_PRS',
    'auto_repair_security': 'GITHUB_AUTO_REPAIR_SECURITY',
    'collaborator_seconds': 'GITHUB_COLLABORATOR_SECONDS',
}
BOOL_FIELDS = {'monitor_enabled','autopublish','review_prs','security_watch','auto_repair_prs','auto_repair_security'}
INT_FIELDS = {'poll_seconds':(60,86400),'collaborator_seconds':(300,86400)}
# Environment variables are installation-level permissions, NOT dashboard fields.
def allowed_repositories():
    return sorted({v.strip() for v in os.getenv('GITHUB_ALLOWED_REPOS','').split(',') if v.strip()})

def _conn():
    c=db()
    c.execute('CREATE TABLE IF NOT EXISTS github_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    c.commit()
    return c

def get(key):
    if key not in DEFAULTS:raise KeyError(key)
    c=_conn()
    try:
        record=c.execute('SELECT value FROM github_settings WHERE key=?',(key,)).fetchone()
        return record['value'] if record else os.getenv(DEFAULTS[key], 'false' if key in BOOL_FIELDS else '')
    finally:c.close()

def enabled(key):
    return get(key).lower()=='true'

def current():
    values={key:(enabled(key) if key in BOOL_FIELDS else int(get(key) or (180 if key=='poll_seconds' else 1800)) if key in INT_FIELDS else get(key)) for key in DEFAULTS}
    return {'settings':values, 'allowed_repositories':allowed_repositories(),
            'credentials':{'github_app_configured':all(os.getenv(k) for k in ('GITHUB_APP_ID','GITHUB_APP_INSTALLATION_ID','GITHUB_APP_PRIVATE_KEY')),
            'webhook_secret_configured':bool(os.getenv('GITHUB_WEBHOOK_SECRET')),
            'monitor_token_configured':bool(os.getenv('GITHUB_MONITOR_TOKEN')),
            'repo_create_token_configured':bool(os.getenv('GITHUB_REPO_CREATE_TOKEN'))}}

def update(changes):
    if not isinstance(changes,dict) or not changes or set(changes)-set(DEFAULTS):
        raise ValueError('Unknown or empty GitHub settings')
    normalized={}
    for key,value in changes.items():
        if key in BOOL_FIELDS:
            if type(value) is not bool:raise ValueError(key+' must be boolean')
            normalized[key]='true' if value else 'false'
        elif key in INT_FIELDS:
            low,high=INT_FIELDS[key]
            if type(value) is not int or not low<=value<=high:raise ValueError(key+' out of range')
            normalized[key]=str(value)
        elif key=='monitor_repo':
            if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value):
                raise ValueError('Invalid monitor repository')
            if value.lower() not in {r.lower() for r in allowed_repositories()}:
                raise ValueError('Repository must be allowlisted in server .env')
            normalized[key]=value
    c=_conn()
    try:
        with c:
            c.executemany('INSERT INTO github_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',normalized.items())
    finally:c.close()
    return current()
