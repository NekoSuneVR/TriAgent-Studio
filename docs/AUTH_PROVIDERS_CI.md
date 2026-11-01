# Dashboard authentication, providers, and GitHub Actions monitoring

## Secure internet-facing deployment
Create a secret: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
Generate a password hash on a system with the app dependencies installed:
`python -m app.password_hash`. Paste the resulting `DASHBOARD_PASSWORD_HASH=...` into `.env`. Set `SESSION_SECRET`, `DASHBOARD_USERNAME`, and all provider credentials. Restart the Docker stack.

The dashboard exposes a username/password login and issues one-hour signed tokens held only in browser memory. Eight failed login attempts per observed IP within fifteen minutes trigger a temporary limit. This is a *single administrator* login, not multi-user identity management or MFA. Login attempts across processes or behind proxies have limitations because the rate-limit memory is per process. Rotate `SESSION_SECRET` to invalidate existing sessions.

**Never open plain HTTP to the public internet.** Terminate HTTPS at a reverse proxy with access controls (preferably Cloudflare Access, Tailscale or equivalent), set `DASHBOARD_BIND=0.0.0.0` only where your network protections require it, and restrict direct access via your firewall. All `/api/*` routes except login require an authenticated bearer session.

## LLM providers
Set three role-specific `ROLE_PROVIDER`, `ROLE_MODEL`, `ROLE_API_KEY` and optionally `ROLE_API_URL` values (ROLE is FRONTEND, BACKEND, REVIEW). Supported backends:
- `openai` and `codex`: OpenAI Chat Completions API with tool calling; Codex API usage is billed separately from a ChatGPT subscription.
- `anthropic` or `claude`: native Anthropic Messages API tool calling.
- `ollama`: OpenAI-compatible local endpoint; Docker defaults to `host.docker.internal:11434/v1`; enable appropriate Ollama host networking safely.
- `litellm`: LiteLLM proxy at `http://litellm:4000/v1`, or override its URL.
- `omniroute` and `custom`: specify an OpenAI-compatible `ROLE_API_URL`.
- `openrouter`: OpenRouter's OpenAI-compatible API.

Each agent can use a different provider. `ROLE_MODEL=auto` uses the first value in `ROLE_FREE_MODELS`, or an installed Ollama model from `/api/tags`. **This does not validate pricing, quality, availability, or provider quotas.** It does not automatically search the internet for the 'best' free model or switch after rate limiting. Set explicit model names for reliable production use.

## GitHub Actions monitor
Set `GITHUB_MONITOR_ENABLED=true`, `GITHUB_MONITOR_REPO=owner/repo`, and a fine-grained `GITHUB_MONITOR_TOKEN` with **Actions: read** and **Contents: read** for that repo. The monitor checks up to the 20 most recent completed workflow runs every `GITHUB_POLL_SECONDS` (minimum 60s) and deduplicates by workflow run ID. It queues a normal 3-agent task based on failed job names and failed step names.

**Limitations:** It currently clones the repository default branch; it does not check out the exact failed SHA, retrieve full logs, push patches or create a PR. The resulting local fix is not guaranteed to fix the failed workflow. Review its output before applying it. GitHub automatic writes are deliberately disabled.

## Operational limitations
This is not safe to expose directly to untrusted users or to run untrusted repository scripts with provider credentials inside the worker containers. Use stronger isolated sandboxes, additional network controls, and per-job credentials before production unattended use.
