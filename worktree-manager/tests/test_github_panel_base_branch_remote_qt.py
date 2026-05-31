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


def test_base_branch_combo_populated_from_remote_branches(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main", "develop", "release/1.0"]):
        panel._populate_open_pr_form()
    base_items = [panel._base_branch_combo.itemText(i) for i in range(panel._base_branch_combo.count())]
    assert base_items == ["main", "develop", "release/1.0"]


def test_base_branch_defaults_to_main_from_remote(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["develop", "main", "release/1.0"]):
        panel._populate_open_pr_form()
    assert panel._base_branch_combo.currentText() == "main"



def test_base_branch_reloads_from_remote_when_repo_changes(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    store.save_repo(_repo_cfg("/repos/beta"))

    def remote_branches(path):
        return ["main", "feat-a"] if "alpha" in path else ["trunk", "feat-b"]

    with patch.object(vm, "list_branches_for_repo", return_value=["feature/x"]), \
         patch.object(vm, "list_remote_branches_for_repo", side_effect=remote_branches):
        panel._populate_open_pr_form()
        alpha_base = panel._base_branch_combo.currentText()
        other_idx = 1 - panel._repo_combo.currentIndex()
        panel._repo_combo.setCurrentIndex(other_idx)
        beta_base = panel._base_branch_combo.currentText()

    assert alpha_base != beta_base
