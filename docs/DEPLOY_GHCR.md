# Image deployment (GHCR)

The `Build and publish Docker images` workflow tests the application on pull requests. On pushes to `main`, it publishes multi-platform `linux/amd64` and `linux/arm64` images to:

`ghcr.io/nekosunevr/triagent-studio:latest`

Find builds under **Actions** and images under **Packages**. If the package is private, authenticate with a GitHub token that has `read:packages` scope.

To deploy the prebuilt image from Dockge or Docker Compose, copy `docker-compose.yml`, then replace `build: .` under `x-common` with:

```yaml
image: ghcr.io/nekosunevr/triagent-studio:latest
```

Make a matching `.env` file and start with `docker compose up -d`. The dashboard remains bound to localhost by default. All services share the same image but launch different commands.

## Operational notes
- The images are **not** a safe code execution sandbox. Do not expose the dashboard publicly without HTTPS and access control, or run untrusted repos with privileged or sensitive credentials.
- No production rollout, GitHub push, or PR creation occurs automatically.
- If an interrupted worker stays in `running`, an administrator must restart/recover it. Avoid simply resetting the status while the original process is still alive.
