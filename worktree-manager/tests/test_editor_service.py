import pytest
from unittest.mock import patch, MagicMock, call
from worktree_manager.editor_service import EditorService
from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.json"


@pytest.fixture
def store(config_path):
    s = ConfigStore(config_path)
    s.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
        editor="cursor",
        window_mode="multi",
        cur_open_path=None,
    ))
    return s


@pytest.fixture
def svc(store):
    return EditorService(store)


def test_open_new_launches_with_no_flags(svc):
    with patch("worktree_manager.editor_service._resolve_editor_cmd", return_value="cursor"), \
         patch("subprocess.Popen") as mock_popen:
        svc.open_new("/repos/proj-wt/feat", editor="cursor")
    mock_popen.assert_called_once_with(["cursor", "/repos/proj-wt/feat"])


def test_open_new_vscode_launches_with_no_flags(svc):
    with patch("worktree_manager.editor_service._resolve_editor_cmd", return_value="code"), \
         patch("subprocess.Popen") as mock_popen:
        svc.open_new("/repos/proj-wt/feat", editor="vscode")
    mock_popen.assert_called_once_with(["code", "/repos/proj-wt/feat"])


def test_open_replacing_runs_two_commands_in_sequence(svc):
    with patch("worktree_manager.editor_service._resolve_editor_cmd", return_value="cursor"), \
         patch("subprocess.run") as mock_run:
        svc.open_replacing(
            cur_path="/repos/proj-wt/old",
            new_path="/repos/proj-wt/new",
            editor="cursor",
        )
    assert mock_run.call_count == 2
    assert mock_run.call_args_list[0] == call(
        ["cursor", "-r", "/repos/proj-wt/old"], check=False
    )
    assert mock_run.call_args_list[1] == call(
        ["cursor", "-r", "/repos/proj-wt/new"], check=False
    )


def test_open_replacing_vscode(svc):
    with patch("worktree_manager.editor_service._resolve_editor_cmd", return_value="code"), \
         patch("subprocess.run") as mock_run:
        svc.open_replacing(
            cur_path="/repos/proj-wt/old",
            new_path="/repos/proj-wt/new",
            editor="vscode",
        )
    assert mock_run.call_args_list[0] == call(
        ["code", "-r", "/repos/proj-wt/old"], check=False
    )
    assert mock_run.call_args_list[1] == call(
        ["code", "-r", "/repos/proj-wt/new"], check=False
    )


def test_open_new_returns_popen_object(svc):
    mock_proc = MagicMock()
    with patch("worktree_manager.editor_service._resolve_editor_cmd", return_value="cursor"), \
         patch("subprocess.Popen", return_value=mock_proc):
        result = svc.open_new("/repos/proj-wt/feat", editor="cursor")
    assert result is mock_proc


def test_open_new_raises_when_editor_not_found(svc):
    with patch("worktree_manager.editor_service._resolve_editor_cmd",
               side_effect=FileNotFoundError("not found")):
        with pytest.raises(FileNotFoundError):
            svc.open_new("/repos/proj-wt/feat", editor="cursor")


def test_open_replacing_raises_when_editor_not_found(svc):
    with patch("worktree_manager.editor_service._resolve_editor_cmd",
               side_effect=FileNotFoundError("not found")):
        with pytest.raises(FileNotFoundError):
            svc.open_replacing("/old", "/new", editor="cursor")
