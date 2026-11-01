"""Provider adapters. Configured auto/free selection is explicit, not a price guarantee."""
import json, os, urllib.request, urllib.error

PROVIDERS={
 'openai':('https://api.openai.com/v1',True),
 'codex':('https://api.openai.com/v1',True),
 'anthropic':('https://api.anthropic.com/v1',True),
 'claude':('https://api.anthropic.com/v1',True),
 'ollama':('http://host.docker.internal:11434/v1',False),
 'litellm':('http://litellm:4000/v1',False),
 'omniroute':('',False),
 'openrouter':('https://openrouter.ai/api/v1',True),
 'custom':('',False),
 'groq':('https://api.groq.com/openai/v1',True),
 'deepseek':('https://api.deepseek.com/v1',True),
 'together':('https://api.together.xyz/v1',True),
 'fireworks':('https://api.fireworks.ai/inference/v1',True),
 'mistral':('https://api.mistral.ai/v1',True),
 'cerebras':('https://api.cerebras.ai/v1',True),
 'gemini_compatible':('https://generativelanguage.googleapis.com/v1beta/openai',True),
 'nvidia':('https://integrate.api.nvidia.com/v1',True),
 'huggingface':('https://router.huggingface.co/v1',True),
}
def config(role):
    prefix=role.upper()
    provider=os.getenv(prefix+'_PROVIDER') or os.getenv('AI_PROVIDER','openai')
    provider=provider.lower()
    if provider not in PROVIDERS:raise RuntimeError('Unknown provider: '+provider)
    default_url,requires_key=PROVIDERS[provider]
    url=os.getenv(prefix+'_API_URL') or os.getenv('AI_API_URL') or default_url
    key=os.getenv(prefix+'_API_KEY') or os.getenv('AI_API_KEY','')
    model=os.getenv(prefix+'_MODEL') or os.getenv('AI_MODEL','')
    if not url:raise RuntimeError(prefix+'_API_URL required for '+provider)
    if requires_key and not key:raise RuntimeError(prefix+'_API_KEY required for '+provider)
    if model.lower() in ('','auto','free'):
        model=choose_model(provider,url,key,os.getenv(prefix+'_FREE_MODELS') or os.getenv('AI_FREE_MODELS',''))
    return provider,url.rstrip('/'),key,model

def choose_model(provider,url,key,models):
    # Only owner-curated free models can be selected. Providers' pricing changes.
    choices=[m.strip() for m in models.split(',') if m.strip()]
    if choices:return choices[0]
    if provider=='ollama':
        try:
            base=url.removesuffix('/v1')
            req=urllib.request.Request(base+'/api/tags')
            with urllib.request.urlopen(req,timeout=5) as r:
                items=json.load(r).get('models',[])
            if items:return items[0]['name']
        except Exception:pass
    raise RuntimeError('Set ROLE_MODEL or ROLE_FREE_MODELS. No verified free model found.')

def send(url,body,headers):
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method='POST')
    try:
        with urllib.request.urlopen(req,timeout=120) as resp:return json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError('Model API HTTP '+str(e.code)+': '+e.read().decode(errors='replace')[:1200])

def anthropic_message(messages):
    system='\n'.join(m.get('content','') or '' for m in messages if m['role']=='system')
    result=[]
    for m in messages:
        r=m['role']
        if r=='system':continue
        if r=='tool':
            result.append({'role':'user','content':[{'type':'tool_result','tool_use_id':m['tool_call_id'],'content':m.get('content','')}]})
        elif r=='assistant':
            blocks=[]
            if m.get('content'):blocks.append({'type':'text','text':m['content']})
            for c in m.get('tool_calls',[]):
                blocks.append({'type':'tool_use','id':c['id'],'name':c['function']['name'],'input':json.loads(c['function']['arguments'])})
            result.append({'role':'assistant','content':blocks or [{'type':'text','text':'Working.'}]})
        else:result.append({'role':'user','content':m.get('content','')})
    return system,result

def chat(role,messages,tools):
    provider,url,key,model=config(role)
    limit=int(os.getenv('MAX_OUTPUT_TOKENS','3000'))
    if provider in ('anthropic','claude'):
        system,converted=anthropic_message(messages)
        body={'model':model,'system':system,'messages':converted,'max_tokens':limit,
              'tools':[{'name':t['function']['name'],'description':t['function']['description'],'input_schema':t['function']['parameters']} for t in tools]}
        r=send(url+'/messages',body,{'Content-Type':'application/json','x-api-key':key,'anthropic-version':'2023-06-01'})
        content='\n'.join(b.get('text','') for b in r.get('content',[]) if b.get('type')=='text')
        calls=[{'id':b['id'],'type':'function','function':{'name':b['name'],'arguments':json.dumps(b.get('input',{}))}} for b in r.get('content',[]) if b.get('type')=='tool_use']
        return {'content':content,'tool_calls':calls}
    body={'model':model,'messages':messages,'tools':tools,'tool_choice':'auto','max_tokens':limit}
    headers={'Content-Type':'application/json'}
    if key:headers['Authorization']='Bearer '+key
    r=send(url+'/chat/completions',body,headers)
    return r['choices'][0]['message']

def public_config():
    out={}
    for role in ('frontend','backend','review'):
        p=role.upper()
        out[role]={'provider':os.getenv(p+'_PROVIDER') or os.getenv('AI_PROVIDER','openai'),'model':os.getenv(p+'_MODEL') or os.getenv('AI_MODEL','auto'),
                   'free_models':[x for x in (os.getenv(p+'_FREE_MODELS') or os.getenv('AI_FREE_MODELS','')).split(',') if x]}
    return {'providers':list(PROVIDERS),'roles':out,'note':'Free depends on provider account, model and quota; Ollama locally avoids per-token API billing but uses VPS compute.'}
