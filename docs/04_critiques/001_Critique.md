Given the project structure and your requirements, the best practice setup in VSCode is to use a **multi-root workspace** pointing to your backend and frontend folders separately, while keeping the root directory for common configuration like `pyproject.toml`.

***

## Recommended VSCode Multi-Root Workspace Setup

1. Create a `.code-workspace` file (e.g., `extractor.code-workspace`) in your root directory `/home/graham/workspace/experiments/extractor/` with this structure:

```json
{
  "folders": [
    {
      "path": "src/extractor",
      "name": "Backend"
    },
    {
      "path": "tools",
      "name": "Frontend Tools"
    },
    {
      "path": "prototypes",
      "name": "Frontend Prototypes"
    }
  ],
  "settings": {
    // Optional: Per-folder python interpreter paths can be specified in folder-specific settings, or here at workspace level
  }
}
```

2. In each folder (`src/extractor`, `tools`, `prototypes`), keep an isolated Python virtual environment `.venv` or configure the interpreter path specifically via `.vscode/settings.json` in each folder:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python"
}
```

3. Your root `pyproject.toml` stays in `/home/graham/workspace/experiments/extractor/` and can be used mainly for the backend Python project dependencies. Frontend folders can have their own package managers or dependency configurations if needed.

4. Open the `.code-workspace` file in VSCode to launch the multi-root workspace. This allows smooth switching between backend and frontend contexts with independent Python virtual environments, terminal sessions, and isolated settings.

***

## Why This Is Best Practice

- Keeps backend and frontend logically separated while sharing the same VSCode window for visibility.
- Allows Per-folder virtual environments, so no need to change the root-level `pyproject.toml` or merge virtualenv configurations.
- You can run and debug backend code in `src/extractor` while simultaneously working on frontend tools or prototypes.
- The `pyproject.toml` defines your main Python project dependencies centrally without conflict.
- Terminal and workspace settings are manageable independently per root folder within the multi-root workspace.

***

This aligns with VSCode multi-root workspace recommendations and Python environment management best practices, ideal for a full-stack project like yours with separate frontend and backend pieces under one repo root.[1][2][10]

If desired, additional workspace or folder-specific settings can be set in `.code-workspace` or `.vscode/settings.json` to handle linting, formatting, or testing independently per workspace folder.

[1](https://code.visualstudio.com/docs/editing/workspaces/multi-root-workspaces)
[2](https://code.visualstudio.com/docs/editing/workspaces/workspaces)
[3](https://www.youtube.com/watch?v=TQtrSMgkMVM)
[4](https://stackoverflow.com/questions/76937843/vscode-variable-for-multi-root-workspace-root-directory)
[5](https://devblogs.microsoft.com/ise/multi_root_workspaces_in_visual_studio_code/)
[6](https://code.visualstudio.com/docs/configure/settings)
[7](https://www.reddit.com/r/vscode/comments/ykuocg/how_do_you_organize_multiple_workspaces_and_vs/)
[8](https://users.rust-lang.org/t/multi-root-workspace-in-vscode/104572)
[9](https://www.youtube.com/watch?v=82wPjHiH1M8)
[10](https://code.visualstudio.com/docs/python/environments)