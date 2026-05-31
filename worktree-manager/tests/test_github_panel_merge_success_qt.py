import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.github_models import PullRequest, CICheck, Review
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, checks=None, reviews=None, mergeable=True):
    return PullRequest(
        number=number, title="My Work", body="",
        html_url=f"https://github.com/o/r/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=mergeable,
        checks=checks or [], reviews=reviews or [],
    )


@pytest.fixture
def configured_vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
    return v


@pytest.fixture
def panel(configured_vm, qtbot):
    p = GitHubPanel(vm=configured_vm)
    qtbot.addWidget(p)
    p.show()
    return p


def _show_detail(panel, vm, pr):
    vm.selected_pr = pr
    vm.pr_detail_updated.emit()


def test_merge_success_navigates_back_to_list(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    configured_vm._svc = MagicMock()
    configured_vm._svc.merge_pr.return_value = None
    configured_vm._svc.list_my_open_prs.return_value = []

    panel._merge_btn.click()

    assert panel._my_prs_stack.currentWidget() is panel._pr_list_widget


def test_merge_failure_shows_error_label(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    configured_vm._svc = MagicMock()
    configured_vm._svc.merge_pr.side_effect = RuntimeError("Merge conflict")
    configured_vm.prs = [pr]

    panel._merge_btn.click()

    assert panel._merge_error_label.isVisible()
    assert "Merge conflict" in panel._merge_error_label.text()


def test_merge_failure_does_not_navigate_back(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    configured_vm._svc = MagicMock()
    configured_vm._svc.merge_pr.side_effect = RuntimeError("Branch protection rule")
    configured_vm.prs = [pr]

    panel._merge_btn.click()

    assert panel._my_prs_stack.currentWidget() is panel._pr_detail_widget


def test_vm_emits_pr_merged_event_on_successful_merge(configured_vm, qtbot):
    merged_events = []
    configured_vm.pr_event.connect(lambda num, evt, msg: merged_events.append((num, evt, msg)))
    configured_vm._svc = MagicMock()
    configured_vm._svc.merge_pr.return_value = None
    configured_vm._svc.list_my_open_prs.return_value = []

    pr = _make_pr(1)
    configured_vm.prs = [pr]
    configured_vm.merge_pr(1, squash=True)

    assert any(e[1] == "pr_merged" for e in merged_events)
    assert any("My Work" in e[2] for e in merged_events)
