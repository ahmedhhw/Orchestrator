import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.github_models import PullRequest, CICheck, Review
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, checks=None, reviews=None, mergeable=True, state="open"):
    return PullRequest(
        number=number, title="My Work", body="",
        html_url=f"https://github.com/o/r/pull/{number}",
        head_branch="feat", base_branch="main",
        state=state, draft=False, mergeable=mergeable,
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


def test_merge_button_exists(panel):
    assert hasattr(panel, "_merge_btn")


def test_squash_checkbox_exists(panel):
    assert hasattr(panel, "_squash_checkbox")


def test_merge_button_visible_when_checks_failed_but_approved_and_mergeable(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "failure")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    assert panel._merge_btn.isVisible()
    assert panel._squash_checkbox.isVisible()


def test_merge_button_hidden_when_not_mergeable(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=False,
    )
    _show_detail(panel, configured_vm, pr)
    assert not panel._merge_btn.isVisible()
    assert not panel._squash_checkbox.isVisible()


def test_merge_button_hidden_when_mergeable_unknown(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=None,
    )
    _show_detail(panel, configured_vm, pr)
    assert not panel._merge_btn.isVisible()


def test_merge_button_visible_when_ready(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    assert panel._merge_btn.isVisible()
    assert panel._squash_checkbox.isVisible()


def test_squash_checkbox_checked_by_default(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    assert panel._squash_checkbox.isChecked()


def test_merge_button_calls_service_with_squash(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    configured_vm._svc = MagicMock()
    configured_vm._svc.merge_pr.return_value = None
    configured_vm._svc.list_my_open_prs.return_value = []
    configured_vm.prs = [pr]
    panel._squash_checkbox.setChecked(True)
    panel._merge_btn.click()
    args, kwargs = configured_vm._svc.merge_pr.call_args
    assert args[0].number == 1
    assert kwargs["squash"] is True


def test_merge_button_calls_service_without_squash(panel, configured_vm, qtbot):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    configured_vm._svc = MagicMock()
    configured_vm._svc.merge_pr.return_value = None
    configured_vm._svc.list_my_open_prs.return_value = []
    configured_vm.prs = [pr]
    panel._squash_checkbox.setChecked(False)
    panel._merge_btn.click()
    args, kwargs = configured_vm._svc.merge_pr.call_args
    assert args[0].number == 1
    assert kwargs["squash"] is False


def test_merge_btn_reconnect_does_not_warn(panel, configured_vm, recwarn):
    """Showing a mergeable PR twice must not emit a RuntimeWarning for the merge button."""
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    _show_detail(panel, configured_vm, pr)
    _show_detail(panel, configured_vm, pr)

    runtime_warnings = [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)]
    assert runtime_warnings == []
