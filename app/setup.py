"""First-boot local administrator enrollment. Never returns stored credentials."""
import os, secrets, sqlite3, time
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from .core import db
from .auth import hash_password, make_session, FAILURES

class SetupInput(BaseModel):
    username: str = Field(min_length=3,max_length=64,pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=12,max_length=256)

def _table(c):
    c.execute('CREATE TABLE IF NOT EXISTS admin_account (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, password_hash TEXT NOT NULL, created INTEGER NOT NULL)')
    c.commit()

def account():
    c=db()
    try:
        _table(c)
        row=c.execute('SELECT username,password_hash FROM admin_account WHERE id=1').fetchone()
        return row
    finally:c.close()

def setup_status():
    return {'setup_required':not bool(account() or os.getenv('DASHBOARD_PASSWORD_HASH'))}

def enroll(data:SetupInput, request:Request):
    # Allow only loopback or private reverse proxy deployments, enforce HTTPS for remote.
    if request.url.scheme!='https' and not (request.client and request.client.host in ('127.0.0.1','::1')):
        # Reverse proxy deployment requires correct forwarded scheme and trusted proxy headers.
        raise HTTPException(403,'First-time setup requires HTTPS (or local loopback)')
    if os.getenv('DASHBOARD_PASSWORD_HASH'):raise HTTPException(409,'An administrator is already configured in .env')
    if os.getenv('DASHBOARD_SETUP_TOKEN','') and request.headers.get('x-setup-token')!=os.getenv('DASHBOARD_SETUP_TOKEN'):
        raise HTTPException(403,'Incorrect setup token')
    c=db()
    try:
        _table(c)
        try:
            c.execute('INSERT INTO admin_account(id,username,password_hash,created) VALUES(1,?,?,?)',
                      (data.username,hash_password(data.password),int(time.time())))
            c.commit()
        except sqlite3.IntegrityError:raise HTTPException(409,'Setup has already been completed')
    finally:c.close()
    return {'access_token':make_session(),'expires_in':3600}
