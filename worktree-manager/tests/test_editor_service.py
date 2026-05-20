import pytest
from unittest.mock import patch, MagicMock
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
    ))
    return s


@pytest.fixture
def svc(store):
    return EditorService(store)


def test_open_vscode_new_window(svc):
    with patch("subprocess.Popen") as mock_popen:
        svc.open("/repos/proj-wt/feat", editor="vscode", reuse_window=False, repo_path="/repos/proj")
    mock_popen.assert_called_once_with(["code", "--new-window", "/repos/proj-wt/feat"])


def test_open_vscode_reuse_window(svc):
    with patch("subprocess.Popen") as mock_popen:
        svc.open("/repos/proj-wt/feat", editor="vscode", reuse_window=True, repo_path="/repos/proj")
    mock_popen.assert_called_once_with(["code", "--reuse-window", "/repos/proj-wt/feat"])


def test_open_cursor_new_window(svc):
    with patch("subprocess.Popen") as mock_popen:
        svc.open("/repos/proj-wt/feat", editor="cursor", reuse_window=False, repo_path="/repos/proj")
    mock_popen.assert_called_once_with(["cursor", "--new-window", "/repos/proj-wt/feat"])


def test_open_cursor_reuse_window(svc):
    with patch("subprocess.Popen") as mock_popen:
        svc.open("/repos/proj-wt/feat", editor="cursor", reuse_window=True, repo_path="/repos/proj")
    mock_popen.assert_called_once_with(["cursor", "--reuse-window", "/repos/proj-wt/feat"])


def test_open_persists_last_editor(svc, store):
    with patch("subprocess.Popen"):
        svc.open("/repos/proj-wt/feat", editor="vscode", reuse_window=True, repo_path="/repos/proj")
    cfg = store.get_repo("/repos/proj")
    assert cfg.last_editor == "vscode"
    assert cfg.last_editor_mode == "reuse"


def test_open_persists_new_mode(svc, store):
    with patch("subprocess.Popen"):
        svc.open("/repos/proj-wt/feat", editor="cursor", reuse_window=False, repo_path="/repos/proj")
    cfg = store.get_repo("/repos/proj")
    assert cfg.last_editor_mode == "new"
