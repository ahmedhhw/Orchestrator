"""
Tests: repo + worktree selection in DiffPanel persists across restarts.
"""
import time
from unittest.mock import MagicMock

from worktree_manager.config_store import ConfigStore
from worktree_manager.models import RepoConfig, WorktreeModel
from worktree_manager.diff_models import HistoryPoint
from worktree_manager.ui.diff_panel import DiffPanel


def _wt(path, is_main=False):
    return WorktreeModel(
        path=path, branch="main", is_main=is_main,
        last_commit_ts=int(time.time()), is_merged=False, is_stale=False,
    )


def _git(repo_a_wts, repo_b_wts):
    git = MagicMock()
    git.list_points.return_value = [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
    ]
    git.list_worktrees.side_effect = lambda path: (
        repo_a_wts if path.endswith("repo_a") else repo_b_wts
    )
    return git


def _store(tmp_path, repo_a, repo_b):
    store = ConfigStore(path=tmp_path / "config.json")
    base = dict(worktree_storage="", stale_days=30,
                last_editor="cursor", last_editor_mode="project", last_opened=0)
    store.save_repo(RepoConfig(repo_path=repo_a, **base))
    store.save_repo(RepoConfig(repo_path=repo_b, **base))
    return store


def _panel(qtbot, git, store):
    p = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(p)
    return p


# ── ConfigStore layer ──────────────────────────────────────────────────────────

def test_set_diff_selection_persists_to_disk(tmp_path):
    store = ConfigStore(path=tmp_path / "config.json")
    store.set_diff_selection("/repo/a", "/repo/a/wt1")
    store2 = ConfigStore(path=tmp_path / "config.json")
    sel = store2.get_diff_selection()
    assert sel["repo_path"] == "/repo/a"
    assert sel["worktree_path"] == "/repo/a/wt1"


def test_get_diff_selection_returns_empty_dict_when_not_set(tmp_path):
    store = ConfigStore(path=tmp_path / "config.json")
    assert store.get_diff_selection() == {}


# ── DiffPanel: saves on user interaction ─────────────────────────────────────

def test_changing_worktree_saves_selection(qtbot, tmp_path):
    repo_a = str(tmp_path / "repo_a")
    repo_b = str(tmp_path / "repo_b")
    wt_main = _wt(repo_a + "/main", is_main=True)
    wt_feat = _wt(repo_a + "/feat")
    git = _git([wt_main, wt_feat], [])
    store = _store(tmp_path, repo_a, repo_b)

    panel = _panel(qtbot, git, store)
    # select second worktree
    panel._worktree_combo.setCurrentIndex(1)

    sel = store.get_diff_selection()
    assert sel.get("worktree_path") == repo_a + "/feat"


def test_changing_repo_saves_selection(qtbot, tmp_path):
    repo_a = str(tmp_path / "repo_a")
    repo_b = str(tmp_path / "repo_b")
    git = _git([_wt(repo_a, is_main=True)], [_wt(repo_b, is_main=True)])
    store = _store(tmp_path, repo_a, repo_b)

    panel = _panel(qtbot, git, store)

    # switch to repo_b
    idx = panel._repo_combo.findData(repo_b)
    panel._repo_combo.setCurrentIndex(idx)

    sel = store.get_diff_selection()
    assert sel.get("repo_path") == repo_b


# ── DiffPanel: restores on startup ────────────────────────────────────────────

def test_repo_combo_restores_saved_repo_on_startup(qtbot, tmp_path):
    repo_a = str(tmp_path / "repo_a")
    repo_b = str(tmp_path / "repo_b")
    git = _git([_wt(repo_a, is_main=True)], [_wt(repo_b, is_main=True)])
    store = _store(tmp_path, repo_a, repo_b)
    store.set_diff_selection(repo_b, repo_b)

    panel = _panel(qtbot, git, store)

    assert panel._repo_combo.currentData() == repo_b


def test_worktree_combo_restores_saved_worktree_on_startup(qtbot, tmp_path):
    repo_a = str(tmp_path / "repo_a")
    wt_main = _wt(repo_a + "/main", is_main=True)
    wt_feat = _wt(repo_a + "/feat")
    git = _git([wt_main, wt_feat], [])
    store = _store(tmp_path, repo_a, str(tmp_path / "repo_b"))
    store.set_diff_selection(repo_a, repo_a + "/feat")

    panel = _panel(qtbot, git, store)

    assert panel._worktree_combo.currentData() == repo_a + "/feat"
