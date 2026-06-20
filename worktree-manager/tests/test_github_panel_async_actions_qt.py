"""
Panel-side wiring tests for async merge and open-PR actions.

Tests prove that:
- _on_merge_pr calls vm.merge_pr and does NOT sleep / block
- merge_finished signal navigates to the list and shows merged state
- merge_failed signal shows error label and re-enables the merge button
- _on_push_open_pr calls vm.open_pull_request (no inline push/sleep)
- open_pr_finished signal re-enables the button and switches to My PRs tab
- open_pr_failed signal shows error label and re-enables the button
"""
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


def _show_mergeable_detail(panel, vm):
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    vm.selected_pr = pr
    vm.pr_detail_updated.emit()
    return pr


# ── merge_finished signal handling ───────────────────────────────────────────

def test_merge_finished_signal_navigates_back_to_list(panel, configured_vm, qtbot):
    """When vm emits merge_finished, the panel navigates back to the PR list."""
    pr = _show_mergeable_detail(panel, configured_vm)

    configured_vm.merge_finished.emit(pr.pr_key)

    assert panel._my_prs_stack.currentWidget() is panel._pr_list_widget


def test_merge_finished_signal_hides_merge_button(panel, configured_vm, qtbot):
    """When vm emits merge_finished, the merge button is hidden."""
    pr = _show_mergeable_detail(panel, configured_vm)

    configured_vm.merge_finished.emit(pr.pr_key)

    assert not panel._merge_btn.isVisible()


def test_merge_finished_signal_hides_squash_checkbox(panel, configured_vm, qtbot):
    """When vm emits merge_finished, the squash checkbox is hidden."""
    pr = _show_mergeable_detail(panel, configured_vm)

    configured_vm.merge_finished.emit(pr.pr_key)

    assert not panel._squash_checkbox.isVisible()


# ── merge_failed signal handling ─────────────────────────────────────────────

def test_merge_failed_signal_shows_error_label(panel, configured_vm, qtbot):
    """When vm emits merge_failed, the error label is visible with the message."""
    pr = _show_mergeable_detail(panel, configured_vm)
    panel._merge_btn.setEnabled(False)
    panel._merge_btn.setText("Merging…")

    configured_vm.merge_failed.emit(pr.pr_key, "Branch protection rule violated")

    assert panel._merge_error_label.isVisible()
    assert "Branch protection rule violated" in panel._merge_error_label.text()


def test_merge_failed_signal_re_enables_merge_button(panel, configured_vm, qtbot):
    """When vm emits merge_failed, the merge button is re-enabled with original text."""
    pr = _show_mergeable_detail(panel, configured_vm)
    panel._merge_btn.setEnabled(False)
    panel._merge_btn.setText("Merging…")

    configured_vm.merge_failed.emit(pr.pr_key, "some error")

    assert panel._merge_btn.isEnabled()
    assert panel._merge_btn.text() == "Merge PR"


def test_merge_failed_signal_does_not_navigate_back(panel, configured_vm, qtbot):
    """When vm emits merge_failed, the panel stays on the detail view."""
    pr = _show_mergeable_detail(panel, configured_vm)

    configured_vm.merge_failed.emit(pr.pr_key, "fail")

    assert panel._my_prs_stack.currentWidget() is panel._pr_detail_widget


# ── _on_merge_pr wiring ───────────────────────────────────────────────────────

def test_on_merge_pr_calls_vm_merge_pr_not_svc_directly(panel, configured_vm, qtbot):
    """
    Clicking Merge PR must call vm.merge_pr (delegated) — not _svc.merge_pr directly.
    The panel must not touch _svc; all blocking work goes through the VM.
    """
    pr = _show_mergeable_detail(panel, configured_vm)
    configured_vm.prs = [pr]

    configured_vm.merge_pr = MagicMock()

    panel._merge_btn.click()

    configured_vm.merge_pr.assert_called_once()
    call_args = configured_vm.merge_pr.call_args
    assert call_args[0][0].number == pr.number


def test_on_merge_pr_disables_button_before_vm_call(panel, configured_vm, qtbot):
    """
    When Merge PR is clicked, the button is disabled before vm.merge_pr is called
    (gives instant visual feedback without sleeping).
    """
    pr = _show_mergeable_detail(panel, configured_vm)
    configured_vm.prs = [pr]

    button_states = []

    def _capture(*args, **kwargs):
        button_states.append(panel._merge_btn.isEnabled())

    configured_vm.merge_pr = _capture

    panel._merge_btn.click()

    assert button_states == [False], (
        "Merge button was not disabled before vm.merge_pr was called"
    )


# ── open_pr_finished signal handling ─────────────────────────────────────────

def test_open_pr_finished_switches_to_my_prs_tab(panel, configured_vm, qtbot):
    """When vm emits open_pr_finished, the panel switches to tab index 0 (My PRs)."""
    # Switch to the Open PR tab first
    panel._tabs.setCurrentIndex(1)

    configured_vm.open_pr_finished.emit()

    assert panel._tabs.currentIndex() == 0


def test_open_pr_finished_re_enables_push_button(panel, configured_vm, qtbot):
    """When vm emits open_pr_finished, the Push & Open PR button is re-enabled."""
    panel._push_open_btn.setEnabled(False)
    panel._push_open_btn.setText("Pushing…")

    configured_vm.open_pr_finished.emit()

    assert panel._push_open_btn.isEnabled()
    assert panel._push_open_btn.text() == "Push & Open PR"


# ── open_pr_failed signal handling ───────────────────────────────────────────

def test_open_pr_failed_shows_error_label(panel, configured_vm, qtbot):
    """When vm emits open_pr_failed, the inline error label is not hidden and has the message."""
    panel._push_open_btn.setEnabled(False)

    configured_vm.open_pr_failed.emit("Authentication failed")

    # The label lives inside the Open PR tab which may not be the active tab,
    # so isVisible() (which walks ancestors) can return False even when the label
    # itself is shown. Use isHidden() which only tests the widget's own state.
    assert not panel._open_pr_error_label.isHidden()
    assert "Authentication failed" in panel._open_pr_error_label.text()


def test_open_pr_failed_re_enables_push_button(panel, configured_vm, qtbot):
    """When vm emits open_pr_failed, the Push & Open PR button is re-enabled."""
    panel._push_open_btn.setEnabled(False)
    panel._push_open_btn.setText("Pushing…")

    configured_vm.open_pr_failed.emit("fail")

    assert panel._push_open_btn.isEnabled()
    assert panel._push_open_btn.text() == "Push & Open PR"


def test_open_pr_failed_does_not_switch_tab(panel, configured_vm, qtbot):
    """When vm emits open_pr_failed, the panel stays on the Open PR tab."""
    panel._tabs.setCurrentIndex(1)

    configured_vm.open_pr_failed.emit("fail")

    assert panel._tabs.currentIndex() == 1


# ── _on_push_open_pr wiring ──────────────────────────────────────────────────

def _setup_open_pr_form(panel):
    """Set up minimum Open PR form state so validation passes."""
    panel._repo_display_map = {"myrepo": "/fake/repo"}
    panel._repo_combo.blockSignals(True)
    panel._repo_combo.clear()
    panel._repo_combo.addItem("myrepo")
    panel._repo_combo.blockSignals(False)
    panel._head_branch_combo.blockSignals(True)
    panel._head_branch_combo.clear()
    panel._head_branch_combo.addItem("feat/my-branch")
    panel._head_branch_combo.blockSignals(False)
    panel._base_branch_combo.clear()
    panel._base_branch_combo.addItem("main")
    panel._pr_title_edit.setText("My Title")


def test_on_push_open_pr_calls_vm_open_pull_request(panel, configured_vm, qtbot):
    """
    Clicking Push & Open PR must call vm.open_pull_request (not _svc directly).
    """
    _setup_open_pr_form(panel)
    configured_vm.open_pull_request = MagicMock()

    with patch("worktree_manager.ui.github_panel._github_api_base", return_value="https://api.github.com/repos/o/r"):
        panel._push_open_btn.click()

    configured_vm.open_pull_request.assert_called_once()
    call_kwargs = configured_vm.open_pull_request.call_args[1]
    assert call_kwargs["title"] == "My Title"
    assert call_kwargs["repo_base_url"] == "https://api.github.com/repos/o/r"


def test_on_push_open_pr_disables_button_immediately(panel, configured_vm, qtbot):
    """
    When Push & Open PR is clicked, the button is disabled before any network call.
    """
    _setup_open_pr_form(panel)

    button_states = []

    def _capture(*args, **kwargs):
        button_states.append(panel._push_open_btn.isEnabled())

    configured_vm.open_pull_request = _capture

    with patch("worktree_manager.ui.github_panel._github_api_base", return_value="https://api.github.com/repos/o/r"):
        panel._push_open_btn.click()

    assert button_states == [False], (
        "Push button was not disabled before vm.open_pull_request was called"
    )
