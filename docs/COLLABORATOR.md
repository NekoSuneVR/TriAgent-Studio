# TriAgent collaborative coding: PR feedback, inactive repos and approvals

## Developer-authorised repositories
Create a GitHub App and install it in each selected personal account or organisation. Organisational owners may need to approve installation. In the dashboard's **GitHub App repositories** panel you can view repositories accessible to the configured installation and whether each is included in `GITHUB_ALLOWED_REPOS`. Repository modification requires *both* App access and server-side allowlisting. This is currently one GitHub App installation per deployment, **not** GitHub OAuth login or self-service multi-account organisation selection. Do not claim that a dashboard login connects GitHub user identity.

## PR review comments
Set `GITHUB_REVIEW_PRS=true`. The collaborator polls up to 40 open PRs per allowlisted repo, examines added patch lines for a limited set of dangerous code execution or credential patterns, and adds a commit-specific advisory review comment. It deduplicates comments for each head SHA. This analysis is heuristic, not full AI code review, and must not be treated as proof that code is safe. When `GITHUB_AUTO_REPAIR_PRS=true`, PRs **whose source branch is in the same repository** may additionally enqueue an investigation task. Forked third-party PRs get advisory feedback only; they are not changed by the assistant.

## Stale repositories and vulnerability watch
Set `GITHUB_SECURITY_WATCH=true`. Every `GITHUB_COLLABORATOR_SECONDS` (minimum five minutes), the service requests open Dependabot and Code Scanning alerts from each allowlisted repository, including repositories with no recent commits. Each previously unseen alert gets a GitHub issue. `GITHUB_AUTO_REPAIR_SECURITY=true` optionally queues an investigation. This needs the GitHub App's Dependabot alerts and Code scanning alerts read permissions, plus Issues write for new issues. Alert coverage depends on GitHub security features enabled in the repository. Detection of RCE is not guaranteed.

## Additional parallel workers
Each worker role claims queued jobs through SQLite. To process several **independent jobs** simultaneously, run:
```bash
docker compose up -d --scale frontend-agent=2 --scale backend-agent=2 --scale review-agent=2
```
A single project still has one frontend stage, one backend stage and one review stage. Multiple agents of the *same role on one project* and automated partitioning of work into subtasks are not yet implemented. Never point multiple agents at the same writable Git worktree concurrently.

## Explicit merge or deploy
No scheduled worker can call merge/deploy. The authenticated developer may call the explicit endpoints:
- `POST /api/github/merge`: `{"repo":"owner/name","pr_number":123,"expected_sha":"40-character-head-sha","confirmation":"MERGE owner/name#123"}`
- `POST /api/github/deploy`: `{"repo":"owner/name","workflow":"deploy.yml","ref":"main","confirmation":"DEPLOY owner/name@main"}`

GitHub branch protections, required approvals and workflow permissions still apply. Deployment dispatch only runs an **existing workflow**; it does not write deployment code.

## Model endpoints
The OpenAI-compatible adapter also supports Groq, DeepSeek, Together, Fireworks, Mistral, Cerebras, Gemini-compatible, NVIDIA and Hugging Face routing. Verify that the selected model and provider support tool calling. APIs may charge money even if a model is described as free; local Ollama is not an unlimited free cloud service.

## Security and limitations
This implementation still needs a real deployment test and stronger isolation of untrusted project builds from GitHub App credentials. Do not publicly expose or enable autonomous write access before addressing that risk. Repair tasks currently clone the default branch and do not automatically apply fixes to the original PR head. Dashboard repository selection is read-only; installation scope and allowlist changes are made in GitHub and VPS configuration.
