"""Iteration 1 — Re-try CIs from the PR detail screen (button tests)."""
import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.github_models import PullRequest, CICheck
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, checks=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/o/r/pull/{number}",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
        checks=checks or [],
    )


def _failed_check(name="build", run_id="42", suite_id="suite-1"):
    return CICheck(name=name, status="completed", conclusion="failure",
                   check_suite_id=suite_id, run_id=run_id)


def _passing_check(name="build", run_id="42", suite_id="suite-1"):
    return CICheck(name=name, status="completed", conclusion="success",
                   check_suite_id=suite_id, run_id=run_id)


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


# ── Test 1: detail shows both retry buttons when a check failed ────────────────

def test_detail_shows_both_retry_buttons_when_check_failed(panel, configured_vm, qtbot):
    pr = _make_pr(checks=[_failed_check()])
    _show_detail(panel, configured_vm, pr)
    assert panel._retry_failed_btn.isVisible()
    assert panel._retry_all_btn.isVisible()


# ── Test 2: detail hides the failed button when no check failed ────────────────

def test_detail_hides_failed_button_when_no_check_failed(panel, configured_vm, qtbot):
    pr = _make_pr(checks=[_passing_check()])
    _show_detail(panel, configured_vm, pr)
    assert not panel._retry_failed_btn.isVisible()
    assert panel._retry_all_btn.isVisible()


# ── Test 3: detail hides both buttons when there are no checks ────────────────

def test_detail_hides_both_buttons_when_no_checks(panel, configured_vm, qtbot):
    pr = _make_pr(checks=[])
    _show_detail(panel, configured_vm, pr)
    assert not panel._retry_failed_btn.isVisible()
    assert not panel._retry_all_btn.isVisible()


# ── Test 4: clicking re-try failed invokes VM retry_failed_cis ────────────────

def test_clicking_retry_failed_invokes_vm_retry_failed_cis(panel, configured_vm, qtbot):
    pr = _make_pr(checks=[_failed_check()])
    _show_detail(panel, configured_vm, pr)
    configured_vm.retry_failed_cis = MagicMock(return_value="")
    panel._retry_failed_btn.click()
    configured_vm.retry_failed_cis.assert_called_once_with(pr)


# ── Test 5: clicking re-try all invokes VM retry_all_cis ─────────────────────

def test_clicking_retry_all_invokes_vm_retry_all_cis(panel, configured_vm, qtbot):
    pr = _make_pr(checks=[_passing_check()])
    _show_detail(panel, configured_vm, pr)
    configured_vm.retry_all_cis = MagicMock()
    panel._retry_all_btn.click()
    configured_vm.retry_all_cis.assert_called_once_with(pr)


# ── Test 6: re-try failed shows status line, including non-rerunnable note ────

def test_retry_failed_shows_running_status_including_note_when_present(panel, configured_vm, qtbot):
    # A failed check without run_id is not rerunnable → VM returns a note
    pr = _make_pr(checks=[_failed_check(run_id=None)])
    _show_detail(panel, configured_vm, pr)
    # But with run_id=None, failed_actions_run_ids() returns [] so the button
    # would be hidden. We need at least one rerunnable check alongside a
    # non-rerunnable one so the button is shown and the note appears.
    pr2 = _make_pr(checks=[
        _failed_check(name="actions-job", run_id="99"),    # rerunnable
        _failed_check(name="required-check", run_id=None), # not rerunnable → note
    ])
    _show_detail(panel, configured_vm, pr2)
    configured_vm.retry_failed_cis = MagicMock(return_value="1 non-Actions check can't be re-run")
    panel._retry_failed_btn.click()
    assert panel._rerun_status_label.isVisible()
    label_text = panel._rerun_status_label.text()
    assert "⏳" in label_text
    assert "non-Actions" in label_text


# ── Test 7: an API error on re-try all surfaces visibly instead of crashing ───

def test_retry_all_surfaces_error_instead_of_raising(panel, configured_vm, qtbot):
    import requests
    pr = _make_pr(checks=[_passing_check()])
    _show_detail(panel, configured_vm, pr)
    configured_vm.retry_all_cis = MagicMock(
        side_effect=requests.HTTPError("403 Client Error: Forbidden")
    )
    # Must NOT raise — the click handler surfaces the error in the status label.
    panel._retry_all_btn.click()
    assert panel._rerun_status_label.isVisible()
    assert "403" in panel._rerun_status_label.text()


# ── Test 8: an API error on re-try failed surfaces visibly instead of crashing ─

def test_retry_failed_surfaces_error_instead_of_raising(panel, configured_vm, qtbot):
    import requests
    pr = _make_pr(checks=[_failed_check(run_id="99")])
    _show_detail(panel, configured_vm, pr)
    configured_vm.retry_failed_cis = MagicMock(
        side_effect=requests.HTTPError("403 Client Error: Forbidden")
    )
    panel._retry_failed_btn.click()
    assert panel._rerun_status_label.isVisible()
    assert "403" in panel._rerun_status_label.text()
