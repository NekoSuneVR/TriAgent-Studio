# TriAgent Studio — VPS coding agent dashboard

A working **starter** for a three-agent, self-hosted AI coding workflow: a browser prompt dashboard, separate frontend/backend/reviewer workers, persistent SQLite job queue, audit logs, shared disk, isolated Git worktrees, integration stage and a manual approval boundary. **This is not an unattended production-safe software factory.** Review generated changes before using, merging, or deploying them.

## Install on Ubuntu 24.04 VPS

Install Docker Engine and the Docker Compose plugin, then:

```bash
unzip triagent-vps.zip
cd triagent-vps
cp .env.example .env
# Generate a 32-byte+ dashboard secret
python3 -c 'import secrets; print(secrets.token_urlsafe(36))'
nano .env   # Paste token, and configure all three API keys/models
mkdir -p data
chmod 700 data
chmod 600 .env
docker compose up -d --build
docker compose logs -f --tail=50
```

Default dashboard listens on `127.0.0.1:8088` on the VPS (not public). From your computer:

```bash
ssh -L 8088:127.0.0.1:8088 ubuntu@YOUR_VPS_IP
```

Then browse to **http://localhost:8088**, paste `DASHBOARD_TOKEN`, and click **Connect**. Use a properly configured HTTPS reverse proxy + access control if you need internet-facing access. Do **not** expose the dashboard HTTP port to the internet directly.

## How it works

1. Submit a project name, instructions and optionally a public GitHub HTTPS repository.
2. The server initializes a local Git project under `data/projects/JOBID` (or clones the public GitHub repo) and creates `frontend` and `backend` Git worktrees under `data/workspaces/`.
3. Both workers concurrently call their configured OpenAI-compatible Chat Completions APIs (tool calls are required) and implement their respective portions using `write_file`, `read_file`, `list_files`, and restricted `run_command`.
4. They commit code on their own branches. Integration merges both branches; conflicts stop the job for human resolution.
5. The reviewer gets an integrated worktree, adds tests/docs or fixes and commits. Its branch is merged into `job-JOBID-integrated`.
6. The task becomes `ready_for_review`. Inspect code manually under `./data/projects/JOBID`, and push or create a PR yourself. **The app does not automatically push code, merge PRs or deploy.**

## Model setup

Set `{FRONTEND,BACKEND,REVIEW}_API_URL`, `_API_KEY`, and `_MODEL`. Defaults point at OpenAI-compatible `https://api.openai.com/v1`. You may use separate providers only if they implement compatible `/chat/completions` with `tools` + tool call IDs. Ollama may work with compatible models/endpoints but isn't guaranteed. This project does not install local models.

## Security and operational limits

- **Trusted private VPS only.** The agent-generated code and existing repositories are *untrusted*. Builds or tests execute inside a worker container and may run arbitrary project scripts despite command allowlisting. This prototype is **not** an adequate security boundary against malicious code or prompt injection. To run unknown repos safely, deploy dedicated locked-down ephemeral sandboxes with separate credentials, rootless containers, network restrictions, read-only mounts and per-job isolation.
- Workers receive provider API keys via environment and use a shared `/data` mount. Never load untrusted third-party code without stronger isolation; malicious tests could attempt credential theft. Avoid sensitive/private repositories in this starter.
- No automatic remote Git publishing or deployment; no SSH key access required.
- Docker service starts as container root; `no-new-privileges` and limits help but are not a comprehensive sandbox.
- The dashboard uses bearer-token auth for `/api/*`; the token is kept in page memory, not browser local storage. Set a strong token and terminate TLS at a trusted reverse proxy if exposing it remotely.
- Queue persisted in SQLite (WAL). A crashed worker may leave a stage `running`; no automatic recovery of orphaned in-progress stages yet.
- Work is bounded by `MAX_AGENT_STEPS`, request timeouts, `MAX_OUTPUT_TOKENS`, `MAX_TASKS_PER_DAY`; model API billing still applies.
- This is a starter: no automatic issue sync, no git push, no backups, no multiuser RBAC, no streaming tokens, no retries or sophisticated dependency planning.

## Compose / debugging

```bash
docker compose ps
docker compose logs -f frontend-agent backend-agent review-agent
docker compose restart dashboard
docker compose down       # retains ./data
```

To inspect a generated Git project:

```bash
cd data/projects/JOBID
git log --oneline --graph --all
git status
git diff main..job-JOBID-integrated
```

For cloned repos, `main` might be named differently; use `git branch -a` to find the original base.

## Changing worker count

The compose file starts exactly one worker per role. They cooperate through SQLite, so the queue prevents two workers from claiming the same stage. Roles are intentionally fixed at three for this starter.
