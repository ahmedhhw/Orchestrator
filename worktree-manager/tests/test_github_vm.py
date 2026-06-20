import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment
from worktree_manager.github_vm import GitHubViewModel, TokenState


def _make_pr(number=1, head="feat", base="main", checks=None, reviews=None, comments=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch=head, base_branch=base, state="open", draft=False, mergeable=True,
        checks=checks or [], reviews=reviews or [], comments=comments or [],
    )


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


# ── token state ──────────────────────────────────────────────────────────────


def test_vm_enters_configured_state_with_token_only(tmp_path):
    store = MagicMock()
    store.get_github_token.return_value = "ghp_test"
    store.get_github_owner.return_value = ""
    store.get_github_repo.return_value = ""
    store.get_github_poll_interval.return_value = 30

    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store)
    assert vm.token_state == TokenState.CONFIGURED
    vm.deleteLater()


def test_initial_token_state_configured_when_token_exists(store, qtbot):
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store)
    assert vm.token_state == TokenState.CONFIGURED
    vm.deleteLater()


def test_initial_token_state_missing_when_no_token(tmp_path, qtbot):
    from worktree_manager.config_store import ConfigStore
    empty_store = ConfigStore(path=tmp_path / "c.json")
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=empty_store)
    assert vm.token_state == TokenState.MISSING
    vm.deleteLater()


def test_save_token_updates_state_to_configured(tmp_path, qtbot):
    from worktree_manager.config_store import ConfigStore
    empty_store = ConfigStore(path=tmp_path / "c.json")
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=empty_store)
        vm.save_token("ghp_new")
    assert vm.token_state == TokenState.CONFIGURED
    assert empty_store.get_github_token() == "ghp_new"
    vm.deleteLater()


# ── PR list ───────────────────────────────────────────────────────────────────


def test_fetch_updates_pr_list(store, qtbot):
    svc = MagicMock()
    vm = _vm_with(svc, store)
    svc.fetch_all_open_prs.return_value = [_make_pr(1), _make_pr(2)]
    _run_fetch_sync(vm, "quick_fetch")
    assert len(vm.prs) == 2
    vm.deleteLater()


def test_fetch_on_401_sets_expired_state(store, qtbot):
    svc = MagicMock()
    vm = _vm_with(svc, store)
    svc.fetch_all_open_prs.side_effect = PermissionError("401")
    _run_fetch_sync(vm, "total_fetch")
    assert vm.token_state == TokenState.EXPIRED
    vm.deleteLater()


# ── total_fetch / quick_fetch ────────────────────────────────────────────────


def _vm_with(svc, store):
    """Create a VM with timers stopped and startup fetch suppressed."""
    from PySide6.QtWidgets import QApplication
    import time
    svc.fetch_all_open_prs.return_value = []
    svc.get_pr_detail.side_effect = None
    svc.get_pr_detail.return_value = None
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = svc
        vm = GitHubViewModel(store=store)
        vm._total_timer.stop()
        vm._quick_timer.stop()
    # wait for startup _run_total_fetch thread to finish
    deadline = time.monotonic() + 3.0
    while (not vm._initial_load_done or vm._total_fetch_running) and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    QApplication.processEvents()
    # reset to clean state for the actual test
    vm._known_prs = []
    vm.prs = []
    vm._pr_state = {}
    svc.fetch_all_open_prs.reset_mock()
    svc.fetch_all_open_prs.return_value = []
    svc.get_pr_detail.reset_mock()
    svc.get_pr_detail.side_effect = None
    return vm


def _run_fetch_sync(vm, method_name):
    """Run a VM fetch by calling the underlying _run_* method directly (no thread spawn)."""
    from PySide6.QtWidgets import QApplication
    inner = "_run_total_fetch" if method_name == "total_fetch" else "_run_quick_fetch"
    # set the loading_started side-effect manually for total_fetch
    if method_name == "total_fetch" and not vm._initial_load_done:
        vm.loading_started.emit()
    getattr(vm, inner)()
    QApplication.processEvents()


def test_total_fetch_calls_fetch_all_open_prs(store, qtbot):
    """total_fetch must call fetch_all_open_prs (single GraphQL call) and populate vm.prs."""
    svc = MagicMock()
    vm = _vm_with(svc, store)
    svc.fetch_all_open_prs.return_value = [_make_pr(1), _make_pr(2)]
    _run_fetch_sync(vm, "total_fetch")
    assert sorted(p.number for p in vm.prs) == [1, 2]
    svc.fetch_all_open_prs.assert_called_once()
    vm.deleteLater()


def test_quick_fetch_calls_fetch_all_open_prs(store, qtbot):
    """quick_fetch must call fetch_all_open_prs (same single-call path as total_fetch)."""
    svc = MagicMock()
    vm = _vm_with(svc, store)
    svc.fetch_all_open_prs.return_value = [_make_pr(5)]
    _run_fetch_sync(vm, "quick_fetch")
    assert [p.number for p in vm.prs] == [5]
    svc.fetch_all_open_prs.assert_called_once()
    vm.deleteLater()


def test_fetch_returns_only_prs_from_graphql(store, qtbot):
    """GraphQL returns exactly the PRs it got — only those are in vm.prs."""
    svc = MagicMock()
    vm = _vm_with(svc, store)
    svc.fetch_all_open_prs.return_value = [_make_pr(1)]
    _run_fetch_sync(vm, "total_fetch")
    assert [p.number for p in vm.prs] == [1]
    vm.deleteLater()


def test_fetch_carries_forward_last_known_mergeable(store, qtbot):
    import copy
    svc = MagicMock()
    vm = _vm_with(svc, store)
    good = _make_pr(1)
    good.mergeable = True
    good.mergeable_state = "clean"
    svc.fetch_all_open_prs.return_value = [copy.copy(good)]
    _run_fetch_sync(vm, "total_fetch")
    nullp = _make_pr(1)
    nullp.mergeable = None
    nullp.mergeable_state = "unknown"
    svc.fetch_all_open_prs.return_value = [copy.copy(nullp)]
    _run_fetch_sync(vm, "total_fetch")
    assert vm.prs[0].mergeable is True
    assert vm.prs[0].mergeable_state == "clean"
    vm.deleteLater()


def _make_pr_copy(src):
    import copy
    return copy.copy(src)


def test_total_fetch_on_401_sets_expired_state(store, qtbot):
    svc = MagicMock()
    vm = _vm_with(svc, store)
    svc.fetch_all_open_prs.side_effect = PermissionError("401")
    _run_fetch_sync(vm, "total_fetch")
    assert vm.token_state == TokenState.EXPIRED
    vm.deleteLater()


# ── two timers + skip-while-total ────────────────────────────────────────────


def test_two_timers_use_configured_intervals(store, qtbot):
    store.save_github_poll_interval(30)
    store.save_github_total_fetch_interval(300)
    svc = MagicMock()
    vm = _vm_with(svc, store)
    assert vm._quick_timer.interval() == 30 * 1000
    assert vm._total_timer.interval() == 300 * 1000
    vm.deleteLater()


def test_quick_fetch_skipped_while_total_running(store, qtbot):
    import time
    from PySide6.QtWidgets import QApplication
    svc = MagicMock()
    vm = _vm_with(svc, store)
    vm._total_fetch_running = True
    started = []
    original = vm._run_quick_fetch
    vm._run_quick_fetch = lambda: started.append(1)
    vm.quick_fetch()
    time.sleep(0.05)
    QApplication.processEvents()
    assert started == []
    vm._run_quick_fetch = original
    vm.deleteLater()


# ── notification de-dup ───────────────────────────────────────────────────────


def test_no_event_on_first_sighting(store, qtbot):
    svc = MagicMock()
    vm = _vm_with(svc, store)
    events = []
    vm.pr_event.connect(lambda k, t, m: events.append(t))
    vm._emit_pr_events([_make_pr(1, checks=[CICheck("b", "completed", "failure")])])
    assert events == []
    vm.deleteLater()


def test_no_repeat_event_when_state_unchanged(store, qtbot):
    svc = MagicMock()
    vm = _vm_with(svc, store)
    events = []
    vm.pr_event.connect(lambda k, t, m: events.append(t))
    pr = _make_pr(1, checks=[CICheck("b", "completed", "failure")])
    vm._emit_pr_events([pr])
    vm._emit_pr_events([pr])
    vm._emit_pr_events([pr])
    assert events == []
    vm.deleteLater()


def test_event_fires_on_ci_transition(store, qtbot):
    svc = MagicMock()
    vm = _vm_with(svc, store)
    events = []
    vm.pr_event.connect(lambda k, t, m: events.append(t))
    vm._emit_pr_events([_make_pr(1, checks=[CICheck("b", "in_progress", None)])])
    vm._emit_pr_events([_make_pr(1, checks=[CICheck("b", "completed", "failure")])])
    assert "ci_failed" in events
    vm.deleteLater()


def test_comment_notified_once(store, qtbot):
    svc = MagicMock()
    vm = _vm_with(svc, store)
    events = []
    vm.pr_event.connect(lambda k, t, m: events.append(t))
    c = PRComment(id=7, author="bob", body="hi", created_at="t")
    vm._emit_pr_events([_make_pr(1, comments=[c])])
    vm._emit_pr_events([_make_pr(1, comments=[c])])
    assert events.count("new_comment") == 0
    c2 = PRComment(id=8, author="al", body="yo", created_at="t")
    vm._emit_pr_events([_make_pr(1, comments=[c, c2])])
    assert events.count("new_comment") == 1
    vm.deleteLater()


# ── PR detail ─────────────────────────────────────────────────────────────────


def test_select_pr_fetches_detail(store, qtbot):
    pr = _make_pr(42, checks=[CICheck("build", "completed", "success")])
    svc = MagicMock()
    svc.get_pr_detail.return_value = pr
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = svc
        vm = GitHubViewModel(store=store)
    vm.prs = [pr]
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(pr)
    assert vm.selected_pr is not None
    assert vm.selected_pr.number == 42
    vm.deleteLater()


def test_deselect_pr_clears_selection(store, qtbot):
    pr = _make_pr(1)
    svc = MagicMock()
    svc.get_pr_detail.return_value = pr
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = svc
        vm = GitHubViewModel(store=store)
        vm.select_pr(pr)
        vm.deselect_pr()
    assert vm.selected_pr is None
    vm.deleteLater()


# ── polling pause/resume ───────────────────────────────────────────────────────


def test_polling_starts_active(store, qtbot):
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store)
    assert vm.polling_active is True
    vm.deleteLater()


def test_pause_polling_stops_timer(store, qtbot):
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store)
        vm.pause_polling()
    assert vm.polling_active is False
    vm.deleteLater()


def test_resume_polling_restarts_timer(store, qtbot):
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store)
        vm.pause_polling()
        vm.resume_polling()
    assert vm.polling_active is True
    vm.deleteLater()
