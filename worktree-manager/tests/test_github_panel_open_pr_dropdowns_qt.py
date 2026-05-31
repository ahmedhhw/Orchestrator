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
    # switch to the Open PR tab
    p._tabs.setCurrentIndex(1)
    return p


# ── widget existence ──────────────────────────────────────────────────────────

def test_repo_combo_exists(panel):
    assert hasattr(panel, "_repo_combo")
    assert panel._repo_combo is not None


def test_branch_combo_exists(panel):
    assert hasattr(panel, "_head_branch_combo")
    assert panel._head_branch_combo is not None


# ── repo combo populated from VM ─────────────────────────────────────────────

def test_repo_combo_shows_repos_from_vm(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    store.save_repo(_repo_cfg("/repos/beta"))
    with patch.object(vm, "list_branches_for_repo", return_value=[]):
        panel._populate_open_pr_form()
    repo_items = [panel._repo_combo.itemText(i) for i in range(panel._repo_combo.count())]
    # Display names are basenames, not full paths
    assert "alpha" in repo_items
    assert "beta" in repo_items


def test_repo_combo_empty_when_no_repos(panel, vm):
    with patch.object(vm, "list_branches_for_repo", return_value=[]):
        panel._populate_open_pr_form()
    assert panel._repo_combo.count() == 0


# ── branch combo populated per repo ─────────────────────────────────────────

def test_branch_combo_shows_branches_for_selected_repo(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["main", "feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()
    branch_items = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())]
    assert "main" in branch_items
    assert "feature/foo" in branch_items


def test_branch_combo_reloads_when_repo_changes(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    store.save_repo(_repo_cfg("/repos/beta"))

    def branches_for(path):
        return ["main", "feat-a"] if path == "/repos/alpha" else ["main", "feat-b"]

    with patch.object(vm, "list_branches_for_repo", side_effect=branches_for), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()
        panel._repo_combo.setCurrentIndex(1)

    branch_items = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())]
    assert len(branch_items) > 0


def test_branch_combo_empty_when_no_branches(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=[]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()
    assert panel._head_branch_combo.count() == 0


# ── push uses selected repo path ─────────────────────────────────────────────

def test_push_open_pr_uses_selected_repo_and_branch(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["main", "feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()

    # pick repo and branch
    panel._repo_combo.setCurrentIndex(0)
    idx = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())].index("feature/foo")
    panel._head_branch_combo.setCurrentIndex(idx)

    mock_svc = MagicMock()
    mock_svc.push_branch.return_value = None
    mock_svc.create_pull_request.return_value = MagicMock()
    vm._svc = mock_svc

    with patch("worktree_manager.ui.github_panel._github_api_base", return_value="https://api.github.com/repos/o/r"), \
         patch.object(vm, "total_fetch"):
        panel._push_open_btn.click()

    mock_svc.push_branch.assert_called_once_with("feature/foo", repo_path="/repos/alpha")
