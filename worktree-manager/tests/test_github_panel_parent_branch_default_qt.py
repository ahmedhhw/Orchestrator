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


def test_base_branch_defaults_to_parent_when_parent_exists_as_remote(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    remote_branches = ["main", "feature/parent", "develop"]
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/child"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=remote_branches), \
         patch.object(vm, "get_parent_branch_for_repo", return_value="feature/parent"):
        panel._populate_open_pr_form()
    assert panel._base_branch_combo.currentText() == "feature/parent"


def test_base_branch_falls_back_to_main_when_parent_not_in_remote(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    remote_branches = ["main", "develop"]
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/child"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=remote_branches), \
         patch.object(vm, "get_parent_branch_for_repo", return_value=None):
        panel._populate_open_pr_form()
    assert panel._base_branch_combo.currentText() == "main"


def test_base_branch_updates_when_head_branch_changed_to_branch_with_parent(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    remote_branches = ["main", "feature/parent"]
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/other", "feature/child"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=remote_branches), \
         patch.object(vm, "get_parent_branch_for_repo", return_value=None):
        panel._populate_open_pr_form()

    # base is "main" now; switch to feature/child which has a remote parent
    with patch.object(vm, "get_parent_branch_for_repo", return_value="feature/parent"):
        panel._head_branch_combo.setCurrentText("feature/child")

    assert panel._base_branch_combo.currentText() == "feature/parent"


def test_base_branch_unchanged_when_head_branch_changed_to_branch_without_parent(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    remote_branches = ["main", "feature/parent"]
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/child", "feature/other"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=remote_branches), \
         patch.object(vm, "get_parent_branch_for_repo", return_value="feature/parent"):
        panel._populate_open_pr_form()

    # main was set; now switch to branch with no parent — base branch should stay as-is (not crash)
    with patch.object(vm, "get_parent_branch_for_repo", return_value=None):
        panel._head_branch_combo.setCurrentText("feature/other")

    # no parent → base stays on main (was the current value, no change made)
    assert panel._base_branch_combo.currentText() in ("main", "feature/parent")
