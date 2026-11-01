"""Authenticated Git fetch/push without embedding credentials in command-line URLs."""
import os, subprocess, tempfile, pathlib

def git_with_token(args,cwd=None,timeout=120):
    from .github_access import _get_token
    token=_get_token()
    script='#!/bin/sh\ncase "$1" in *Username*) printf "%s\\n" "x-access-token";; *) printf "%s\\n" "$TRIAGENT_GITHUB_TOKEN";; esac\n'
    with tempfile.TemporaryDirectory(prefix='triagent-git-') as d:
        helper=pathlib.Path(d)/'askpass'
        helper.write_text(script)
        helper.chmod(0o700)
        env={**os.environ,'TRIAGENT_GITHUB_TOKEN':token,'GIT_ASKPASS':str(helper),
             'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1'}
        proc=subprocess.run(['git',*args],cwd=cwd,env=env,timeout=timeout,
                            capture_output=True,text=True,start_new_session=True)
        if proc.returncode:
            err=(proc.stderr or proc.stdout).replace(token,'[REDACTED]')
            raise RuntimeError('Git operation failed: '+err[-1400:])
        return proc.stdout
