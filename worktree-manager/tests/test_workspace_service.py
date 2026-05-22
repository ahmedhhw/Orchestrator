import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from worktree_manager.models import WorkspaceProject, WorkspaceEntry
from worktree_manager.workspace_service import WorkspaceService


@pytest.fixture
def workspace_dir(tmp_path):
    return tmp_path / "workspaces"


@pytest.fixture
def svc(workspace_dir):
    return WorkspaceService(workspace_dir=workspace_dir)


def test_generate_code_workspace_creates_file(svc, workspace_dir):
    project = WorkspaceProject(name="my-feature", entries=[
        WorkspaceEntry(worktree_path="/repos/api-wt/fix-login"),
        WorkspaceEntry(worktree_path="/repos/web-wt/main"),
    ])
    path = svc.generate_code_workspace(project)
    assert path == workspace_dir / "my-feature.code-workspace"
    assert path.exists()


def test_generate_code_workspace_json_structure(svc, workspace_dir):
    project = WorkspaceProject(name="myproj", entries=[
        WorkspaceEntry(worktree_path="/repos/api-wt/fix-login"),
        WorkspaceEntry(worktree_path="/repos/web-wt/main"),
    ])
    path = svc.generate_code_workspace(project)
    data = json.loads(path.read_text())
    assert "folders" in data
    assert len(data["folders"]) == 2
    paths = [f["path"] for f in data["folders"]]
    assert "/repos/api-wt/fix-login" in paths
    assert "/repos/web-wt/main" in paths


def test_generate_code_workspace_creates_parent_dir(tmp_path):
    deep_dir = tmp_path / "a" / "b" / "workspaces"
    svc = WorkspaceService(workspace_dir=deep_dir)
    project = WorkspaceProject(name="p", entries=[])
    svc.generate_code_workspace(project)
    assert deep_dir.exists()


def test_generate_code_workspace_overwrites_existing(svc, workspace_dir):
    project = WorkspaceProject(name="myproj", entries=[WorkspaceEntry("/old")])
    svc.generate_code_workspace(project)
    project2 = WorkspaceProject(name="myproj", entries=[WorkspaceEntry("/new")])
    path = svc.generate_code_workspace(project2)
    data = json.loads(path.read_text())
    paths = [f["path"] for f in data["folders"]]
    assert "/new" in paths
    assert "/old" not in paths


def test_open_in_editor_calls_correct_command(svc, workspace_dir):
    project = WorkspaceProject(name="myproj", entries=[WorkspaceEntry("/repos/wt")])
    ws_path = svc.generate_code_workspace(project)
    with patch("worktree_manager.workspace_service._resolve_editor_cmd", return_value="/usr/bin/cursor") as mock_cmd:
        with patch("subprocess.Popen") as mock_popen:
            svc.open_in_editor(project, "cursor")
            mock_cmd.assert_called_once_with("cursor")
            mock_popen.assert_called_once_with(["/usr/bin/cursor", str(ws_path)])


def test_open_in_editor_no_r_flag(svc, workspace_dir):
    project = WorkspaceProject(name="myproj", entries=[WorkspaceEntry("/repos/wt")])
    svc.generate_code_workspace(project)
    with patch("worktree_manager.workspace_service._resolve_editor_cmd", return_value="/usr/bin/code"):
        with patch("subprocess.Popen") as mock_popen:
            svc.open_in_editor(project, "vscode")
            call_args = mock_popen.call_args[0][0]
            assert "-r" not in call_args
