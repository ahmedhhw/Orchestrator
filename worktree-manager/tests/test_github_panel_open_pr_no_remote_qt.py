import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.ui.github_panel import GitHubPanel
from worktree_manager.models import RepoConfig


def _repo_cfg(path):
    return RepoConfig(
        repo_path=path, worktree_storage=path + "/.worktrees",
        stale_days=14, last_editor="code",
        last_editor_mode="reuse", last_opened=0, commands=[],
    )


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


@pytest.fixture
def vm(store):
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = MagicMock()
        v = GitHubViewModel(store=store)
    return v


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    p._tabs.setCurrentIndex(1)
    return p


def test_no_remote_error_widget_exists(panel):
    assert hasattr(panel, "_open_pr_no_remote_label")


def test_no_remote_shows_error_when_remote_branches_empty(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=[]):
        panel._populate_open_pr_form()
    assert panel._open_pr_no_remote_label.isVisible()
    assert panel._repo_combo.isVisible()
    assert not panel._head_branch_combo.isEnabled()
    assert not panel._pr_title_edit.isEnabled()
    assert not panel._base_branch_combo.isEnabled()
    assert not panel._description_edit.isEnabled()
    assert not panel._draft_checkbox.isEnabled()
    assert not panel._push_open_btn.isEnabled()


def test_no_remote_hides_error_when_remote_branches_present(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()
    assert not panel._open_pr_no_remote_label.isVisible()
    assert panel._repo_combo.isVisible()
    assert panel._head_branch_combo.isEnabled()
    assert panel._push_open_btn.isEnabled()


def test_no_remote_error_message_mentions_remote(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=[]):
        panel._populate_open_pr_form()
    assert "remote" in panel._open_pr_no_remote_label.text().lower()


def test_no_remote_error_clears_when_repo_changes_to_one_with_remote(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    store.save_repo(_repo_cfg("/repos/beta"))

    def remote_branches(path):
        return [] if "alpha" in path else ["main"]

    with patch.object(vm, "list_branches_for_repo", return_value=["feature/x"]), \
         patch.object(vm, "list_remote_branches_for_repo", side_effect=remote_branches):
        panel._populate_open_pr_form()
        assert panel._open_pr_no_remote_label.isVisible()
        other_idx = 1 - panel._repo_combo.currentIndex()
        panel._repo_combo.setCurrentIndex(other_idx)

    assert not panel._open_pr_no_remote_label.isVisible()
    assert panel._repo_combo.isVisible()
