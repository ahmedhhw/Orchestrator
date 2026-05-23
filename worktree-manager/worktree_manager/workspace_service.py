import json
import subprocess
from pathlib import Path
from worktree_manager.editor_service import _resolve_editor_cmd
from worktree_manager.models import WorkspaceProject


class WorkspaceService:
    def __init__(self, workspace_dir: Path | None = None):
        if workspace_dir is None:
            workspace_dir = Path.home() / ".config" / "worktree-manager" / "workspaces"
        self._workspace_dir = Path(workspace_dir)

    def generate_code_workspace(self, project: WorkspaceProject) -> Path:
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        path = self._workspace_dir / f"{project.name}.code-workspace"
        data = {
            "folders": [{"path": e.worktree_path} for e in project.entries],
        }
        path.write_text(json.dumps(data, indent=2))
        return path

    def delete_code_workspace(self, name: str) -> None:
        path = self._workspace_dir / f"{name}.code-workspace"
        path.unlink(missing_ok=True)

    def open_in_editor(self, project: WorkspaceProject, editor: str) -> None:
        cmd = _resolve_editor_cmd(editor)
        ws_path = self._workspace_dir / f"{project.name}.code-workspace"
        subprocess.Popen([cmd, str(ws_path)])
