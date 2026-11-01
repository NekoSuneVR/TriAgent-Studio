# Unity and VRChat UdonSharp on a VPS

TriAgent can author and review Unity C# or VRChat UdonSharp source code, create local Git branches and publish reviewed changes through the existing opt-in GitHub publication workflow. This does NOT require you to code on your main PC.

## Create a source project
In the dashboard choose **Unity source project** or **VRChat Worlds / UdonSharp**, enter a project prompt and submit. For the VRChat template, TriAgent generates an example UdonSharpBehaviour, AGENTS.md instructions, .gitignore and basic source-hygiene workflow. This is a **code starter**, not a full ready-to-upload Unity world or downloaded VRChat SDK. For existing projects, select General and supply a GitHub URL, preserving the existing project structure, Unity assets and metadata.

## Unity/VRChat build support
The default Linux VPS image has Python, Git and Node.js, but does **not** include Unity Editor, Unity licensing, Creator Companion or VRChat SDK. VRChat currently requires a supported Unity 2022.3 version, not Unity 6; follow https://creators.vrchat.com/releases/ and https://creators.vrchat.com/worlds/udon/udonsharp/. UdonSharp uses a subset of C# and Unity APIs. To verify real Unity/Udon compilation and world behaviour, configure a **separate, authorised build runner** with the appropriate Unity version, compatible VRChat packages and licence/runner permissions. Linux VCC support is limited; use the supported creation workflow. Do not claim successful compilation based only on text checks.

## Create a GitHub repository
Set `GITHUB_CREATE_OWNERS=your-user,approved-org` and `GITHUB_REPO_CREATE_TOKEN` to a credential explicitly authorised to create repositories for these owners. An owner/org may additionally require organisation repository-creation permissions. The dashboard's Create GitHub repo control creates a **private** empty repository. This does not automatically push the local project to the new repo, and the new repo must also be accessible to the configured GitHub App/allowlist before automated push/PR workflows can run.

## Security
Treat scene assets, packages, GitHub workflow files and third-party scripts as untrusted. Never allow arbitrary scripts to run in a container holding GitHub credentials. Use branch protection, restricted build sandboxes and per-repository permissions. AI must not upload a VRChat world or avatar without explicit developer approval.

## Parallel projects
Compose scaling supports parallel *independent* jobs. Fine-grained subtask decomposition within a single Unity project is not implemented. Unity scenes and .meta files should not be edited concurrently by multiple workers.
