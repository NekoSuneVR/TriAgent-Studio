"""Safe project scaffolding for Unity/VRChat code repositories.

These templates provide source control structures, not a licensed Unity editor,
VRChat SDK distribution, or a functioning world/scene without Unity setup.
"""
import pathlib,re
from .core import run

GITIGNORE="""[Ll]ibrary/
[Tt]emp/
[Oo]bj/
[Bb]uild/
[Bb]uilds/
[Ll]ogs/
UserSettings/
.vs/
.idea/
*.csproj
*.sln
*.unitypackage
*.apk
*.vrcw
*.vrca
"""
UDON="""using UdonSharp;
using UnityEngine;
using VRC.SDKBase;
using VRC.Udon;

public class ExampleInteractable : UdonSharpBehaviour
{
    [SerializeField] private GameObject target;

    public override void Interact()
    {
        if (target != null)
        {
            target.SetActive(!target.activeSelf);
        }
    }
}
"""
def files_for(template,name):
    if template=='vrchat-udonsharp':
        return {
            '.gitignore':GITIGNORE,
            'Assets/UdonScripts/ExampleInteractable.cs':UDON,
            'README.md':f'# {name}\n\nVRChat UdonSharp source starter.\n\nOpen with the supported Unity editor and import the official VRChat Worlds SDK through the VRChat Creator Companion. Create an UdonSharp Behaviour, attach it to an interactable object and assign the target. This repository does not bundle a licensed SDK or a complete Unity scene.\n',
            'AGENTS.md':'# Developer instructions\nThis is a VRChat Worlds/UdonSharp project. Preserve Unity .meta GUIDs, Unity scenes, prefabs, and the VPM manifest when present. Use only APIs supported by UdonSharp. Do not upgrade Unity or VRCSDK without explicit developer approval. Do not publish worlds automatically.\n',
            '.github/workflows/source-checks.yml':"""name: Unity source hygiene
on: [push, pull_request]
jobs:
  source:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Ensure scripts contain no obvious conflict markers
        run: |
          if git grep -n -E '^(<<<<<<< |=======|>>>>>>> )' -- '*.cs' '*.unity' '*.prefab'; then
            echo 'Merge conflict markers detected'; exit 1
          fi
          echo 'Source hygiene passed (not a Unity/Udon compile)'
""",
        }
    if template=='unity':
        return {'.gitignore':GITIGNORE,'README.md':f'# {name}\n\nUnity source repository starter. Use Unity Hub to create/import a project, then commit Assets/, Packages/ and ProjectSettings/ including all .meta files.\n'}
    raise ValueError('Unsupported project template')

def scaffold(project,template,name):
    project=pathlib.Path(project)
    files=files_for(template,name)
    for relative,content in files.items():
        target=project/relative
        if target.exists():raise ValueError('Refusing to overwrite '+relative)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(content,encoding='utf-8')
    run(['git','add','.'],cwd=project)
    run(['git','commit','-m','Add '+template+' source scaffold'],cwd=project)
