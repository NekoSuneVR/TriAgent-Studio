import json, os, pathlib, shlex, subprocess, sys, time, urllib.request, urllib.error
from .core import db, claim, finish, event, workspace, run, ROOT

TOOLS=[
 {'type':'function','function':{'name':'list_files','description':'List files under workspace (excluding node_modules and .git).','parameters':{'type':'object','properties':{'directory':{'type':'string'}},'required':['directory']}}},
 {'type':'function','function':{'name':'read_file','description':'Read a UTF-8 file in the workspace.','parameters':{'type':'object','properties':{'path':{'type':'string'}} ,'required':['path']}}},
 {'type':'function','function':{'name':'write_file','description':'Create or replace UTF-8 code/file in workspace.','parameters':{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']}}},
 {'type':'function','function':{'name':'run_command','description':'Run a safe test/build command in the workspace, no shell.','parameters':{'type':'object','properties':{'command':{'type':'string'}},'required':['command']}}},
]

def safe_path(root,path):
    if not path or path.startswith('/') or '\\' in path:raise ValueError('Relative POSIX path required')
    p=(root/path).resolve()
    if not p.is_relative_to(root.resolve()) or '.git' in p.relative_to(root.resolve()).parts:raise ValueError('Path outside workspace or inside .git')
    return p

def execute(root,name,args):
    try:
        if name=='list_files':
            base=safe_path(root,args['directory'] or '.')
            if not base.is_dir():return 'Directory not found'
            return '\n'.join(str(p.relative_to(root)) for p in sorted(base.rglob('*')) if p.is_file() and not any(x in p.parts for x in ('.git','node_modules','.next','dist','venv','.venv')))[:12000]
        if name=='read_file':
            p=safe_path(root,args['path']);return p.read_text(encoding='utf8')[:30000]
        if name=='write_file':
            p=safe_path(root,args['path']);p.parent.mkdir(parents=True,exist_ok=True)
            s=args['content'];
            if len(s)>250000:return 'Refused: file too large'
            p.write_text(s,encoding='utf8');return 'Wrote '+str(p.relative_to(root))
        if name=='run_command':
            cmd=shlex.split(args['command'])
            if not cmd:return 'Empty command'
            # No shell, Git publishing, package installation, arbitrary interpreters, or network tools.
            allowed={('npm','test'),('npm','run'),('npm','--version'),('node','--check'),('python','-m'),('pytest',),('git','status'),('git','diff'),('git','ls-files')}
            if not any(tuple(cmd[:len(x)])==x for x in allowed):return 'Command blocked. Allowed: npm test, npm run <script>, node --check, python -m pytest/compileall, pytest, git status/diff/ls-files.'
            if cmd[:2]==['python','-m'] and (len(cmd)<3 or cmd[2] not in ('pytest','compileall')):return 'Python module blocked'
            if any('..' in t or t.startswith('/') for t in cmd[1:]):return 'Absolute paths and traversal blocked'
            p=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=60,start_new_session=True,env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':'/tmp','CI':'1','npm_config_offline':'true'})
            return f'exit={p.returncode}\n'+(p.stdout+'\n'+p.stderr)[-14000:]
    except Exception as e:return 'Tool error: '+str(e)
    return 'Unknown tool'

def chat(role,messages):
    prefix=role.upper()
    url=os.getenv(f'{prefix}_API_URL','https://api.openai.com/v1').rstrip('/')+'/chat/completions'
    key=os.getenv(f'{prefix}_API_KEY','')
    model=os.getenv(f'{prefix}_MODEL','gpt-4.1-mini')
    if not key:raise RuntimeError(f'Missing {prefix}_API_KEY in .env')
    body={'model':model,'messages':messages,'tools':TOOLS,'tool_choice':'auto','max_tokens':int(os.getenv('MAX_OUTPUT_TOKENS','3000')),'temperature':0.2}
    request=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=120) as resp:
            result=json.load(resp)
    except urllib.error.HTTPError as e:raise RuntimeError('Model API HTTP '+str(e.code)+': '+e.read().decode(errors='replace')[:1000])
    return result['choices'][0]['message']

def perform(jid,role):
    conn=db();job=conn.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone();root=workspace(jid,role)
    instruction={'frontend':'Implement frontend UI, UX, responsive styling, client application in web/; coordinate with backend through explicit API contracts. Avoid server/.',
                 'backend':'Implement backend APIs, data persistence, integrations, and documentation in server/; avoid web/.',
                 'review':'Review the integrated code, add or improve tests and documentation, run appropriate available checks. Do not approve unverified behavior.'}[role]
    messages=[{'role':'system','content':f'You are a software engineer in an isolated container. {instruction} You MUST actually create/edit files using tools; do not just describe intended edits. Only edit files for this project. Be careful about security. Do not write secrets. Prefer minimal dependencies. Do not call external services from commands. When done, summarize what changed, remaining issues, and what tests ran. Current role: {role}.'},
              {'role':'user','content':f'Project: {job["name"]}\nUser prompt:\n{job["prompt"]}\nUse tools to implement. Start by inspecting files.'}]
    limit=max(1,min(50,int(os.getenv('MAX_AGENT_STEPS','18'))))
    for step in range(limit):
        if conn.execute('SELECT status FROM jobs WHERE id=?',(jid,)).fetchone()['status']=='cancelled':raise RuntimeError('Task cancelled')
        msg=chat(role,messages)
        content=msg.get('content') or ''
        calls=msg.get('tool_calls') or []
        if content:event(conn,jid,role,str(content)[:2200])
        messages.append({'role':'assistant','content':content,'tool_calls':calls} if calls else {'role':'assistant','content':content})
        if not calls:break
        for call in calls:
            fn=call.get('function',{});name=fn.get('name','');raw=fn.get('arguments','{}')
            try:args=json.loads(raw)
            except ValueError:args={}
            result=execute(root,name,args)
            event(conn,jid,role,f'{name}({str(args.get("path",args.get("command",args.get("directory",""))))[:150]}): {result[:500]}')
            messages.append({'role':'tool','tool_call_id':call['id'],'content':result[:16000]})
    else:event(conn,jid,role,'Reached maximum agent steps')
    changed=run(['git','status','--porcelain'],cwd=root)
    if changed.strip():
        run(['git','add','-A'],cwd=root)
        run(['git','commit','-m',f'{role}: implement job {jid}'],cwd=root)
        event(conn,jid,role,'Changes committed to role branch')
    else:event(conn,jid,role,'No changed files were produced')
    conn.close()

def main():
    role=sys.argv[1] if len(sys.argv)>1 else ''
    if role not in ('frontend','backend','review'):raise SystemExit('Expected frontend, backend or review')
    print(f'{role} worker started',flush=True)
    while True:
        try:
            jid=claim(role)
            if not jid:time.sleep(3);continue
            try:perform(jid,role);finish(jid,role,True)
            except Exception as exc:finish(jid,role,False,str(exc))
        except Exception as exc:
            print(role,'worker error',repr(exc),flush=True);time.sleep(5)
if __name__=='__main__':main()
