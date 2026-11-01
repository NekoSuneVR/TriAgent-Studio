# GitHub integration and security-gated repair publishing

## Connect private and public repositories
Create a GitHub App owned by you or your organisation. Enable **Contents: Read and write**, **Pull requests: Read and write**, **Actions: Read**, **Metadata: Read**, and read access to desired code-scanning/security alerts. Subscribe to **Push**, **Pull request**, **Workflow run**, and desired security alert webhook events. Set the webhook URL to `https://YOUR-DOMAIN/api/github/webhook` and configure a strong `GITHUB_WEBHOOK_SECRET`. Install your App on selected repositories only. Set `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, and `GITHUB_APP_PRIVATE_KEY` in the server environment. The PEM private key must use literal `\\n` escaping when in a one-line environment variable. Configure `GITHUB_ALLOWED_REPOS=owner/repo,owner/another` as a mandatory allowlist. Restart the dashboard and agent services.

This is an **admin-configured GitHub App integration**, not a per-user OAuth GitHub login or multi-user account linking flow. Additional organisations may require separate GitHub App installations. GitHub App permissions and organisation policies determine private repo access.

## Observe changes in near real time
Signed GitHub webhooks write push, pull-request, workflow-run and security-alert event summaries to the dashboard's GitHub activity panel. Delivery IDs deduplicate retries. The dashboard refreshes on its normal five-second interval. Signatures are verified using HMAC-SHA256, and unlisted repos are rejected. The events represent activity metadata; they are not complete diffs or code-review results.

## Automatically publish verified repairs
Set `GITHUB_MONITOR_ENABLED=true` to detect failed workflows and enqueue a repair task. Set `GITHUB_AUTOPUBLISH=true` to push repair branches when agent tasks become ready for review. The publisher waits for the exact pushed commit to pass **python-checks**, **docker** and **security** GitHub checks before it opens a PR. Failed checks prevent automated PR publication. GitHub App permissions must allow writing to the repo and creating PRs. Protect the `main` branch with required reviews and checks.

**Automated PR publication is not automated merge or production deployment.** The resulting PR must be reviewed and merged in GitHub before publishing the main Docker image. This is intentionally conservative for security-sensitive AI-generated changes.

## Security checks
`.github/workflows/security.yml` runs Trivy filesystem vulnerability, exposed secret and misconfiguration scanning; high and critical findings can fail the job. SARIF results are uploaded to GitHub code scanning where supported. These scans cannot prove code is vulnerability-free; manual code review and additional language-specific analysis remain important.

## Known limitations
- GitHub repair prompts currently include failed steps, not full failing step logs. Repairs are based on the repository default branch rather than the exact failing commit.
- The dashboard currently supports one administrator password. It does not offer a per-user GitHub OAuth connect button, fine-grained user-level permissions, or multi-organisation installation selection.
- Event monitoring is near real time, not file-by-file live editing/collaborative editing.
- Workers execute untrusted project code in containers that are not security hardened. Never give them access to unrestricted sensitive credentials or allow arbitrary untrusted users to submit code.
- Automated publication should stay disabled until the required checks, GitHub App permissions and repo branch protections are verified on the VPS.
