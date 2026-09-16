#!/usr/bin/env python3
import json, subprocess, time
from pathlib import Path
BASE=Path(__file__).resolve().parent
QUEUE=BASE/'upload_queue.jsonl'
MAX_ATTEMPTS=6

def entries():
    latest={}
    if QUEUE.exists():
        for line in QUEUE.read_text(errors='ignore').splitlines():
            try:
                e=json.loads(line); key=e.get('video_path')
                if key: latest[key]=e
            except Exception: pass
    return list(latest.values())

def append(e):
    with QUEUE.open('a') as f: f.write(json.dumps(e,ensure_ascii=False)+'\n')

candidates=[]
for e in entries():
    if e.get('status') not in ('pending','failed','retry_wait'): continue
    path=Path(e.get('video_path','')); script=Path(e.get('script_path',''))
    if not path.is_file() or not script.is_file():
        append({**e,'status':'permanent_failure','reason':'missing_render_or_script','checked_at':time.time()}); continue
    attempts=int(e.get('attempts',0))+1
    if attempts<=MAX_ATTEMPTS: candidates.append((e,attempts))

print(json.dumps({'candidates':len(candidates),'max_attempts':MAX_ATTEMPTS}))
for e,attempt in candidates:
    path=e['video_path']; script=e['script_path']; privacy=e.get('privacy','public'); publish=e.get('publish_at')
    cmd=['python3',str(BASE/'upload_youtube.py'),path,script,privacy]
    if publish: cmd.append(publish)
    started=time.time(); p=subprocess.run(cmd,cwd=BASE,text=True,capture_output=True)
    combined=(p.stdout+'\n'+p.stderr).strip()
    if p.returncode==0: status='uploaded'; reason=None
    elif 'invalid_grant' in combined or ('oauth' in combined.lower() and 'token' in combined.lower()): status='needs_reauth'; reason='oauth_reauth_required'
    elif any(x in combined for x in ('HTTP Error 429','HTTP Error 500','HTTP Error 502','HTTP Error 503','HTTP Error 504','timed out','timedout','Upload PUT failed')): status='retry_wait'; reason='transient_upload_error'
    else: status='permanent_failure'; reason='non_retryable_upload_error'
    append({**e,'status':status,'attempts':attempt,'last_error':combined[-1000:] if p.returncode else None,'updated_at':time.time(),'duration_seconds':round(time.time()-started,1)})
    print(json.dumps({'video_path':path,'attempt':attempt,'status':status,'reason':reason,'exit_code':p.returncode},ensure_ascii=False))
