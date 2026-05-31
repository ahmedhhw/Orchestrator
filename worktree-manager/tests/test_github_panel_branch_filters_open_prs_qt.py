import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.ui.github_panel import GitHubPanel
from worktree_manager.models import RepoConfig
from worktree_manager.github_models import PullRequest


def _repo_cfg(path):
    return RepoConfig(
        repo_path=path,
        worktree_storage=path + "/.worktrees",
        stale_days=14, last_editor="code",
        last_editor_mode="reuse", last_opened=0, commands=[],
    )


def _pr(number, head_branch):
    return PullRequest(
        number=number, title="Some PR", body="",
        html_url=f"https://github.com/o/r/pull/{number}",
        head_branch=head_branch, base_branch="main",
        state="open", draft=False, mergeable=None,
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
        return GitHubViewModel(store=store)


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    p._tabs.setCurrentIndex(1)
    return p


def test_branch_with_open_pr_excluded_from_head_combo(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    vm.prs = [_pr(42, "feature/taken")]

    with patch.object(vm, "list_branches_for_repo", return_value=["feature/taken", "feature/free"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()

    items = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())]
    assert "feature/free" in items
    assert "feature/taken" not in items


def test_branch_without_open_pr_included_in_head_combo(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    vm.prs = []

    with patch.object(vm, "list_branches_for_repo", return_value=["feature/foo", "main"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()

    items = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())]
    assert "feature/foo" in items
    assert "main" in items


def test_multiple_branches_with_open_prs_all_excluded(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    vm.prs = [_pr(1, "feat/a"), _pr(2, "feat/b")]

    with patch.object(vm, "list_branches_for_repo", return_value=["feat/a", "feat/b", "feat/c"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()

    items = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())]
    assert "feat/c" in items
    assert "feat/a" not in items
    assert "feat/b" not in items


def test_branch_filter_refreshes_when_prs_updated(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    vm.prs = [_pr(1, "feat/a")]

    with patch.object(vm, "list_branches_for_repo", return_value=["feat/a", "feat/b"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()

    items_before = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())]
    assert "feat/a" not in items_before

    # PR for feat/a is now merged — prs list no longer contains it
    vm.prs = []
    with patch.object(vm, "list_branches_for_repo", return_value=["feat/a", "feat/b"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()

    items_after = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())]
    assert "feat/a" in items_after


def test_open_pr_form_always_visible_never_replaced(panel, vm, store):
    """The form is always shown — no blocking screen regardless of PR state."""
    store.save_repo(_repo_cfg("/repos/alpha"))
    vm.prs = [_pr(42, "feature/taken")]

    with patch.object(vm, "list_branches_for_repo", return_value=["feature/free"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()

    # The stack widget should not exist — form is shown directly
    assert not hasattr(panel, "_open_pr_stack")
