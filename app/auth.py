"""Password-hash login and short-lived HMAC-signed bearer sessions."""
import base64, hashlib, hmac, json, os, secrets, time
from collections import defaultdict
from fastapi import HTTPException, Header, Request
from pydantic import BaseModel, Field

FAILURES=defaultdict(list)
class LoginInput(BaseModel):
    username: str=Field(min_length=1,max_length=100)
    password: str=Field(min_length=1,max_length=256)

def hash_password(password,salt=None):
    salt=salt or secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1)
    return salt.hex()+':'+digest.hex()

def verify(password,stored):
    try:
        salt,expected=stored.split(':',1)
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=2**14,r=8,p=1).hex()
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError):return False

def signing_key():
    key=os.getenv('SESSION_SECRET','')
    if len(key)<32 or key.startswith('REPLACE_'):
        raise HTTPException(503,'Set SESSION_SECRET to a random secret (at least 32 characters)')
    return key.encode()

def make_session():
    payload=base64.urlsafe_b64encode(json.dumps({'exp':int(time.time())+3600,'nonce':secrets.token_hex(8)},separators=(',',':')).encode()).decode().rstrip('=')
    sig=hmac.new(signing_key(),payload.encode(),hashlib.sha256).hexdigest()
    return payload+'.'+sig

def auth(authorization:str|None=Header(None)):
    key=signing_key()
    if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Log in first')
    try:
        payload,sig=authorization[7:].split('.',1)
        expected=hmac.new(key,payload.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected):raise ValueError('bad signature')
        data=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
        if int(data['exp'])<=time.time():raise ValueError('expired')
    except (ValueError,KeyError,TypeError):raise HTTPException(401,'Session expired or invalid')

def login(body:LoginInput,request:Request):
    ip=request.client.host if request.client else 'unknown'
    now=time.time()
    FAILURES[ip]=[ts for ts in FAILURES[ip] if ts>now-900]
    if len(FAILURES[ip])>=8:raise HTTPException(429,'Too many attempts; try again later')
    username=os.getenv('DASHBOARD_USERNAME','admin')
    stored=os.getenv('DASHBOARD_PASSWORD_HASH','')
    if not stored:raise HTTPException(503,'DASHBOARD_PASSWORD_HASH is not configured')
    ok=hmac.compare_digest(body.username,username) and verify(body.password,stored)
    if not ok:
        FAILURES[ip].append(now)
        raise HTTPException(401,'Incorrect username or password')
    FAILURES.pop(ip,None)
    return {'access_token':make_session(),'expires_in':3600}
