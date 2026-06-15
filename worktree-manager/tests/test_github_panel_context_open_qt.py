import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.github_models import PullRequest
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, html_url=None, mergeable=True):
    return PullRequest(
        number=number,
        title=f"PR {number}",
        body="",
        html_url=html_url or f"https://github.com/o/r/pull/{number}",
        head_branch="feat",
        base_branch="main",
        state="open",
        draft=False,
        mergeable=mergeable,
        checks=[],
        reviews=[],
    )


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        return GitHubViewModel(store=store)


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    return p


def _load_pr_into_list(panel, vm, pr):
    """Put one PR into the panel's list and return its QListWidgetItem."""
    vm.prs = [pr]
    vm.prs_updated.emit()
    return panel._pr_list.item(0)


def _action_texts(panel, pr_key):
    """Build the context menu for a given pr_key and return its action texts."""
    menu_actions = []
    original_exec = None

    class CapturingMenu:
        def __init__(self, parent):
            self._actions = []

        def addAction(self, text):
            self._actions.append(text)

        def exec(self, pos):
            return None  # dismiss without selecting

    import worktree_manager.ui.github_panel as gp_mod
    from PySide6.QtWidgets import QMenu

    captured = []

    with patch.object(gp_mod, "QMenu") as MockMenu:
        instance = MagicMock()
        instance_actions = []
        instance.addAction.side_effect = lambda t: instance_actions.append(t)
        instance.exec.return_value = None
        MockMenu.return_value = instance

        item = MagicMock(spec=QListWidgetItem)
        panel._show_pr_context_menu(pr_key, item)
        captured = list(instance_actions)

    return captured


# ── Test 1: "Open in browser" appears in the context menu ─────────────────────

def test_context_menu_includes_open_in_browser(panel, vm):
    pr = _make_pr(1, html_url="https://github.com/o/r/pull/1")
    _load_pr_into_list(panel, vm, pr)
    texts = _action_texts(panel, pr.pr_key)
    assert "↗ Open in browser" in texts


# ── Test 2: "Open in browser" is the FIRST action ─────────────────────────────

def test_open_in_browser_is_first_action(panel, vm):
    pr = _make_pr(1, html_url="https://github.com/o/r/pull/1")
    _load_pr_into_list(panel, vm, pr)
    texts = _action_texts(panel, pr.pr_key)
    assert texts[0] == "↗ Open in browser"


# ── Test 3: choosing "Open in browser" calls QDesktopServices.openUrl ─────────

def test_open_in_browser_calls_desktop_services(panel, vm):
    pr = _make_pr(1, html_url="https://github.com/o/r/pull/1")
    vm.prs = [pr]

    import worktree_manager.ui.github_panel as gp_mod
    from PySide6.QtWidgets import QListWidgetItem, QMenu

    open_action = MagicMock()
    open_action.text.return_value = "↗ Open in browser"

    with patch.object(gp_mod, "QMenu") as MockMenu, \
         patch("worktree_manager.ui.github_panel.QDesktopServices.openUrl") as mock_open:
        instance = MagicMock()
        instance.exec.return_value = open_action
        MockMenu.return_value = instance

        item = MagicMock(spec=QListWidgetItem)
        panel._show_pr_context_menu(pr.pr_key, item)

    mock_open.assert_called_once()
    called_url = mock_open.call_args[0][0]
    assert "pull/1" in called_url.toString()


# ── Test 4: existing actions still present ────────────────────────────────────

def test_existing_actions_still_present(panel, vm):
    pr = _make_pr(1, html_url="https://github.com/o/r/pull/1", mergeable=True)
    # Make it ready to merge so Merge (squash) appears
    with patch.object(pr.__class__, "is_ready_to_merge", return_value=True):
        vm.prs = [pr]
        texts = _action_texts(panel, pr.pr_key)

    assert "↗ View details" in texts
    assert "⧉ Copy URL" in texts


def test_merge_squash_present_when_ready_to_merge(panel, vm):
    pr = _make_pr(1, html_url="https://github.com/o/r/pull/1", mergeable=True)
    from worktree_manager.github_models import CICheck, Review
    pr = PullRequest(
        number=1, title="PR 1", body="",
        html_url="https://github.com/o/r/pull/1",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
    )
    vm.prs = [pr]
    texts = _action_texts(panel, pr.pr_key)
    assert "✓ Merge (squash)" in texts


def _choose_context_action(panel, pr, action_text):
    """Simulate the user picking *action_text* from the PR's context menu."""
    import worktree_manager.ui.github_panel as gp_mod
    chosen = MagicMock()
    chosen.text.return_value = action_text
    with patch.object(gp_mod, "QMenu") as MockMenu:
        instance = MagicMock()
        instance.exec.return_value = chosen
        MockMenu.return_value = instance
        item = MagicMock(spec=QListWidgetItem)
        panel._show_pr_context_menu(pr.pr_key, item)


def test_context_retry_all_surfaces_error_instead_of_raising(panel, vm):
    import requests
    from worktree_manager.github_models import CICheck
    pr = PullRequest(
        number=1, title="PR 1", body="", html_url="https://github.com/o/r/pull/1",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
        checks=[CICheck("build", "completed", "failure", check_suite_id="s1", run_id="9")],
    )
    vm.prs = [pr]
    vm.retry_all_cis = MagicMock(side_effect=requests.HTTPError("403 Forbidden"))
    # Must not raise; the list error label surfaces the message.
    _choose_context_action(panel, pr, "↺ Re-try all CIs")
    assert panel._pr_error_label.isVisible()
    assert "403" in panel._pr_error_label.text()


def test_context_retry_failed_surfaces_error_instead_of_raising(panel, vm):
    import requests
    from worktree_manager.github_models import CICheck
    pr = PullRequest(
        number=1, title="PR 1", body="", html_url="https://github.com/o/r/pull/1",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
        checks=[CICheck("build", "completed", "failure", check_suite_id="s1", run_id="9")],
    )
    vm.prs = [pr]
    vm.retry_failed_cis = MagicMock(side_effect=requests.HTTPError("403 Forbidden"))
    _choose_context_action(panel, pr, "↺ Re-try failed CIs")
    assert panel._pr_error_label.isVisible()
    assert "403" in panel._pr_error_label.text()
