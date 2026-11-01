"""Single-container supervisor for dashboard, AI workers, and GitHub services.

All child processes are local; a failing child makes the container unhealthy by
stopping the supervisor so Docker's restart policy can recover it.
"""
import os, signal, subprocess, sys, time

CHILDREN = [
    [sys.executable,'-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8080'],
    *[[sys.executable,'-m','app.worker',role] for role in ('frontend','backend','review')],
    [sys.executable,'-m','app.github_monitor'],
    [sys.executable,'-m','app.github_publish'],
    [sys.executable,'-m','app.github_collaborator'],
]

def main():
    children=[]
    stopping=False
    def shutdown(_sig,_frame):
        nonlocal stopping
        stopping=True
        for p in children:
            if p.poll() is None:p.terminate()
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    try:
        for cmd in CHILDREN:
            children.append(subprocess.Popen(cmd))
            print('Started',cmd[-1],flush=True)
        while not stopping:
            for p in children:
                if p.poll() is not None:
                    print('Component exited:',p.args,'status',p.returncode,flush=True)
                    stopping=True
                    break
            if not stopping:time.sleep(2)
    finally:
        shutdown(None,None)
        for p in children:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill()
    if any(p.returncode not in (0,-signal.SIGTERM) for p in children):
        sys.exit(1)

if __name__=='__main__':main()
