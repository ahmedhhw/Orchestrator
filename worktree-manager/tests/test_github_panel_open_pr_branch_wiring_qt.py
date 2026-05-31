import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.ui.github_panel import GitHubPanel
from worktree_manager.models import RepoConfig


def _repo_cfg(path):
    return RepoConfig(
        repo_path=path,
        worktree_storage=path + "/.worktrees",
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


# ── title auto-updates when branch changes ────────────────────────────────────

def test_title_prefilled_from_initial_branch(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/my-work", "main"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()
    assert panel._pr_title_edit.text() == "My Work"


def test_title_updates_when_head_branch_changes(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/my-work", "fix/the-bug"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()
    panel._head_branch_combo.setCurrentIndex(1)
    assert panel._pr_title_edit.text() == "The Bug"


def test_title_updates_when_repo_changes(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    store.save_repo(_repo_cfg("/repos/beta"))

    def branches_for(path):
        return ["feat/alpha-thing"] if "alpha" in path else ["feat/beta-thing"]

    with patch.object(vm, "list_branches_for_repo", side_effect=branches_for), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()
        other_idx = 1 - panel._repo_combo.currentIndex()
        panel._repo_combo.setCurrentIndex(other_idx)

    title = panel._pr_title_edit.text()
    assert title in ("Alpha Thing", "Beta Thing")


# ── base branch (remote) defaults to main/master when available ───────────────

def test_base_branch_defaults_to_main(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["feature/foo", "main", "develop"]):
        panel._populate_open_pr_form()
    assert panel._base_branch_combo.currentText() == "main"


def test_base_branch_defaults_to_master_when_no_main(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["feature/foo", "master"]):
        panel._populate_open_pr_form()
    assert panel._base_branch_combo.currentText() == "master"


def test_base_branch_uses_first_remote_branch_when_no_main_or_master(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["develop", "feature/foo"]):
        panel._populate_open_pr_form()
    assert panel._base_branch_combo.currentText() == "develop"


def test_base_branch_reloads_from_remote_when_repo_changes(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    store.save_repo(_repo_cfg("/repos/beta"))

    def remote_branches(path):
        return ["main", "feature/a"] if "alpha" in path else ["trunk", "feature/b"]

    with patch.object(vm, "list_branches_for_repo", return_value=["feature/x"]), \
         patch.object(vm, "list_remote_branches_for_repo", side_effect=remote_branches):
        panel._populate_open_pr_form()
        alpha_base = panel._base_branch_combo.currentText()
        other_idx = 1 - panel._repo_combo.currentIndex()
        panel._repo_combo.setCurrentIndex(other_idx)
        beta_base = panel._base_branch_combo.currentText()

    assert alpha_base != beta_base
