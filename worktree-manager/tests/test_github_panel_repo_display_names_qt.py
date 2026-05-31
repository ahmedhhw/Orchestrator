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
        return GitHubViewModel(store=store)


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    p._tabs.setCurrentIndex(1)
    return p


def test_repo_combo_shows_basename_not_full_path(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=[]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=[]):
        panel._populate_open_pr_form()
    items = [panel._repo_combo.itemText(i) for i in range(panel._repo_combo.count())]
    assert "alpha" in items
    assert "/repos/alpha" not in items


def test_repo_combo_resolves_to_full_path_for_branch_load(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    calls = []
    def capture(path):
        calls.append(path)
        return []
    with patch.object(vm, "list_branches_for_repo", side_effect=capture), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=[]):
        panel._populate_open_pr_form()
    assert "/repos/alpha" in calls


def test_repo_combo_collision_uses_full_path_as_display(panel, vm, store):
    store.save_repo(_repo_cfg("/work/myrepo"))
    store.save_repo(_repo_cfg("/personal/myrepo"))
    with patch.object(vm, "list_branches_for_repo", return_value=[]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=[]):
        panel._populate_open_pr_form()
    items = [panel._repo_combo.itemText(i) for i in range(panel._repo_combo.count())]
    assert "/work/myrepo" in items or "/personal/myrepo" in items


def test_push_open_pr_resolves_display_name_to_full_path(panel, vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    with patch.object(vm, "list_branches_for_repo", return_value=["main", "feature/foo"]), \
         patch.object(vm, "list_remote_branches_for_repo", return_value=["main"]):
        panel._populate_open_pr_form()

    idx = [panel._head_branch_combo.itemText(i) for i in range(panel._head_branch_combo.count())].index("feature/foo")
    panel._head_branch_combo.setCurrentIndex(idx)

    mock_svc = MagicMock()
    mock_svc.push_branch.return_value = None
    mock_svc.create_pull_request.return_value = MagicMock()
    vm._svc = mock_svc

    with patch("worktree_manager.ui.github_panel._github_api_base", return_value="https://api.github.com/repos/o/r"), \
         patch.object(vm, "refresh_prs"):
        panel._push_open_btn.click()

    mock_svc.push_branch.assert_called_once_with("feature/foo", repo_path="/repos/alpha")
