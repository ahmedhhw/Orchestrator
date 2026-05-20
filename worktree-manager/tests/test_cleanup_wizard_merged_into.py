import pytest
from unittest.mock import MagicMock


def _ctk_available():
    try:
        import customtkinter
        return True
    except ImportError:
        return False

pytestmark = pytest.mark.skipif(not _ctk_available(), reason="customtkinter not installed")


@pytest.fixture
def root():
    import customtkinter as ctk
    r = ctk.CTk()
    r.withdraw()
    yield r
    r.destroy()


def _collect_text(widget):
    import customtkinter as ctk
    result = []
    for cls in (ctk.CTkLabel, ctk.CTkCheckBox):
        if isinstance(widget, cls):
            result.append(getattr(widget, "_text", ""))
    for child in widget.winfo_children():
        result.extend(_collect_text(child))
    return result


def test_wizard_shows_merged_into_main(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    c = CleanupCandidate(
        branch="fix/old", path=None, is_merged=True, is_stale=False,
        last_commit_ts=int(time.time()), merged_into="main",
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("main" in t for t in texts)
    wiz.destroy()


def test_wizard_shows_merged_into_feature_branch(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    c = CleanupCandidate(
        branch="fix/old", path=None, is_merged=True, is_stale=False,
        last_commit_ts=int(time.time()), merged_into="feature/payments",
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("feature/payments" in t for t in texts)
    wiz.destroy()


def test_wizard_shows_merged_without_target_when_none(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    c = CleanupCandidate(
        branch="fix/old", path=None, is_merged=True, is_stale=False,
        last_commit_ts=int(time.time()), merged_into=None,
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("merged" in t.lower() for t in texts)
    wiz.destroy()


def test_wizard_healthy_items_are_unchecked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    healthy = CleanupCandidate(
        branch="wip/thing", path=None, is_merged=False, is_stale=False,
        last_commit_ts=now - 2 * 86400, merged_into=None,
    )
    stale = CleanupCandidate(
        branch="old/thing", path=None, is_merged=False, is_stale=True,
        last_commit_ts=now - 40 * 86400, merged_into=None,
    )
    wiz = CleanupWizard(root, candidates=[healthy, stale], on_delete_selected=lambda s, b: None)
    stale_idx = next(i for i, c in enumerate(wiz._candidates) if c.branch == "old/thing")
    healthy_idx = next(i for i, c in enumerate(wiz._candidates) if c.branch == "wip/thing")
    assert wiz._vars[stale_idx].get() is True
    assert wiz._vars[healthy_idx].get() is False
    wiz.destroy()


def test_wizard_stale_sorted_before_healthy(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    healthy = CleanupCandidate(
        branch="wip/thing", path=None, is_merged=False, is_stale=False,
        last_commit_ts=now - 2 * 86400, merged_into=None,
    )
    stale = CleanupCandidate(
        branch="old/thing", path=None, is_merged=False, is_stale=True,
        last_commit_ts=now - 40 * 86400, merged_into=None,
    )
    wiz = CleanupWizard(root, candidates=[healthy, stale], on_delete_selected=lambda s, b: None)
    branches_in_order = [c.branch for c in wiz._candidates]
    assert branches_in_order.index("old/thing") < branches_in_order.index("wip/thing")
    wiz.destroy()


def test_cleanup_wizard_smoke_with_healthy_and_stale(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("chore/deps", "/wt/chore-deps", False, True, now - 35 * 86400),
        CleanupCandidate("wip/thing", "/wt/wip-thing", False, False, now - 2 * 86400),
        CleanupCandidate("release/1.0", None, True, False, now - 5 * 86400),
        CleanupCandidate("hotfix/patch", None, False, False, now - 1 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    wiz.destroy()


def test_uncommitted_worktree_is_unchecked_and_disabled(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate(
        branch="wip/dirty", path="/wt/wip-dirty", is_merged=False, is_stale=True,
        last_commit_ts=now - 40 * 86400, has_uncommitted=True,
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    idx = next(i for i, cand in enumerate(wiz._candidates) if cand.branch == "wip/dirty")
    assert wiz._vars[idx].get() is False
    wiz.destroy()


def test_uncommitted_worktree_excluded_from_delete_selected(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    dirty = CleanupCandidate(
        branch="wip/dirty", path="/wt/wip-dirty", is_merged=False, is_stale=True,
        last_commit_ts=now - 40 * 86400, has_uncommitted=True,
    )
    clean = CleanupCandidate(
        branch="old/clean", path="/wt/old-clean", is_merged=True, is_stale=False,
        last_commit_ts=now - 5 * 86400, has_uncommitted=False,
    )
    deleted = []
    wiz = CleanupWizard(root, candidates=[dirty, clean],
                        on_delete_selected=lambda s, b: deleted.extend(s))
    wiz._delete_selected()
    assert all(c.branch != "wip/dirty" for c in deleted)
    assert any(c.branch == "old/clean" for c in deleted)
    wiz.destroy()


def test_uncommitted_worktree_shows_warning_label(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate(
        branch="wip/dirty", path="/wt/wip-dirty", is_merged=False, is_stale=True,
        last_commit_ts=now - 40 * 86400, has_uncommitted=True,
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("uncommitted" in t.lower() for t in texts)
    wiz.destroy()


def test_clean_worktree_is_checked_and_has_no_warning(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate(
        branch="old/clean", path="/wt/old-clean", is_merged=True, is_stale=False,
        last_commit_ts=now - 5 * 86400, has_uncommitted=False,
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    idx = next(i for i, cand in enumerate(wiz._candidates) if cand.branch == "old/clean")
    assert wiz._vars[idx].get() is True
    texts = _collect_text(wiz)
    assert not any("uncommitted" in t.lower() for t in texts)
    wiz.destroy()


# ---------------------------------------------------------------------------
# Pure-function unit tests (no Tk needed)
# ---------------------------------------------------------------------------

def test_fmt_age_zero_returns_no_commits():
    from worktree_manager.ui.cleanup_wizard import _fmt_age
    assert _fmt_age(0) == "no commits"


def test_fmt_age_counts_days():
    import time
    from worktree_manager.ui.cleanup_wizard import _fmt_age
    ts = int(time.time()) - 7 * 86400
    assert _fmt_age(ts) == "7d"


def test_reason_merged_with_target():
    import time
    from worktree_manager.ui.cleanup_wizard import _reason
    from worktree_manager.models import CleanupCandidate
    c = CleanupCandidate("b", None, True, False, int(time.time()), merged_into="develop")
    assert _reason(c) == "merged into develop"


def test_reason_merged_without_target_defaults_to_main():
    import time
    from worktree_manager.ui.cleanup_wizard import _reason
    from worktree_manager.models import CleanupCandidate
    c = CleanupCandidate("b", None, True, False, int(time.time()), merged_into=None)
    assert _reason(c) == "merged into main"


def test_reason_stale_includes_age_and_stale():
    import time
    from worktree_manager.ui.cleanup_wizard import _reason
    from worktree_manager.models import CleanupCandidate
    ts = int(time.time()) - 10 * 86400
    c = CleanupCandidate("b", None, False, True, ts)
    assert _reason(c) == "10d, stale"


def test_reason_healthy_shows_age_ago():
    import time
    from worktree_manager.ui.cleanup_wizard import _reason
    from worktree_manager.models import CleanupCandidate
    ts = int(time.time()) - 3 * 86400
    c = CleanupCandidate("b", None, False, False, ts)
    assert _reason(c) == "3d ago"


def test_sort_candidates_puts_priority_first():
    import time
    from worktree_manager.ui.cleanup_wizard import _sort_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    healthy = CleanupCandidate("healthy", None, False, False, now)
    stale = CleanupCandidate("stale", None, False, True, now)
    merged = CleanupCandidate("merged", None, True, False, now)
    result = _sort_candidates([healthy, stale, merged])
    names = [c.branch for c in result]
    assert names.index("healthy") > names.index("stale")
    assert names.index("healthy") > names.index("merged")


def test_sort_candidates_healthy_only():
    import time
    from worktree_manager.ui.cleanup_wizard import _sort_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    items = [CleanupCandidate(f"b{i}", None, False, False, now) for i in range(3)]
    assert _sort_candidates(items) == items


# ---------------------------------------------------------------------------
# Filter logic
# ---------------------------------------------------------------------------

def test_apply_filter_all_returns_everything(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard, _FILTER_ALL
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400),
        CleanupCandidate("merged-wt", "/wt/m", True, False, now - 5 * 86400),
        CleanupCandidate("healthy-wt", "/wt/h", False, False, now - 2 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    wiz._filter.set(_FILTER_ALL)
    result = wiz._apply_filter(wiz._all_worktree)
    assert len(result) == 3
    wiz.destroy()


def test_apply_filter_stale_returns_only_stale(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard, _FILTER_STALE
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400),
        CleanupCandidate("merged-wt", "/wt/m", True, False, now - 5 * 86400),
        CleanupCandidate("healthy-wt", "/wt/h", False, False, now - 2 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    wiz._filter.set(_FILTER_STALE)
    result = wiz._apply_filter(wiz._all_worktree)
    assert [c.branch for c in result] == ["stale-wt"]
    wiz.destroy()


def test_apply_filter_merged_returns_only_merged(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard, _FILTER_MERGED
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400),
        CleanupCandidate("merged-wt", "/wt/m", True, False, now - 5 * 86400),
        CleanupCandidate("healthy-wt", "/wt/h", False, False, now - 2 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    wiz._filter.set(_FILTER_MERGED)
    result = wiz._apply_filter(wiz._all_worktree)
    assert [c.branch for c in result] == ["merged-wt"]
    wiz.destroy()


def test_apply_filter_stale_excludes_merged_stale(root):
    """A branch that is both stale AND merged should not appear under Stale filter."""
    from worktree_manager.ui.cleanup_wizard import CleanupWizard, _FILTER_STALE
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    both = CleanupCandidate("both", "/wt/b", True, True, now - 40 * 86400)
    wiz = CleanupWizard(root, candidates=[both], on_delete_selected=lambda s, b: None)
    wiz._filter.set(_FILTER_STALE)
    result = wiz._apply_filter(wiz._all_worktree)
    assert result == []
    wiz.destroy()


def test_filter_rebuild_updates_candidates(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard, _FILTER_STALE
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400),
        CleanupCandidate("merged-wt", "/wt/m", True, False, now - 5 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    assert len(wiz._candidates) == 2

    wiz._filter.set(_FILTER_STALE)
    wiz._rebuild_lists()

    assert [c.branch for c in wiz._candidates] == ["stale-wt"]
    wiz.destroy()


def test_filter_rebuild_clears_vars(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard, _FILTER_MERGED
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400),
        CleanupCandidate("merged-wt", "/wt/m", True, False, now - 5 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    wiz._filter.set(_FILTER_MERGED)
    wiz._rebuild_lists()
    assert len(wiz._vars) == len(wiz._candidates)
    wiz.destroy()


# ---------------------------------------------------------------------------
# Select / deselect all
# ---------------------------------------------------------------------------

def test_select_all_checks_all_vars(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("a", "/wt/a", False, False, now - 1 * 86400),
        CleanupCandidate("b", "/wt/b", False, False, now - 2 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    wiz._select_all()
    assert all(v.get() for v in wiz._vars)
    wiz.destroy()


def test_deselect_all_unchecks_all_vars(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("a", "/wt/a", False, True, now - 40 * 86400),
        CleanupCandidate("b", "/wt/b", True, False, now - 5 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    wiz._deselect_all()
    assert not any(v.get() for v in wiz._vars)
    wiz.destroy()


# ---------------------------------------------------------------------------
# also_branches checkbox auto-state
# ---------------------------------------------------------------------------

def test_also_branches_auto_checked_when_priority_worktrees_present(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    assert wiz._also_branches.get() is True
    wiz.destroy()


def test_also_branches_unchecked_when_only_healthy_worktrees(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("healthy-wt", "/wt/h", False, False, now - 2 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    assert wiz._also_branches.get() is False
    wiz.destroy()


# ---------------------------------------------------------------------------
# delete_selected passes also_branches flag correctly
# ---------------------------------------------------------------------------

def test_delete_selected_passes_also_branches_true(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400)
    calls = []
    wiz = CleanupWizard(root, candidates=[c],
                        on_delete_selected=lambda s, b: calls.append(b))
    wiz._also_branches.set(True)
    wiz._delete_selected()
    assert calls == [True]


def test_delete_selected_passes_also_branches_false(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400)
    calls = []
    wiz = CleanupWizard(root, candidates=[c],
                        on_delete_selected=lambda s, b: calls.append(b))
    wiz._also_branches.set(False)
    wiz._delete_selected()
    assert calls == [False]


# ---------------------------------------------------------------------------
# Worktree vs branch candidate splitting
# ---------------------------------------------------------------------------

def test_worktree_candidates_have_path(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("wt-branch", "/wt/x", True, False, now),
        CleanupCandidate("orphan-branch", None, True, False, now),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    assert all(c.path is not None for c in wiz._all_worktree)
    assert all(c.path is None for c in wiz._all_branch)
    wiz.destroy()


def test_empty_worktrees_does_not_crash(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [CleanupCandidate("orphan", None, True, False, now)]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    assert wiz._all_worktree == []
    wiz.destroy()


def test_empty_branches_does_not_crash(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [CleanupCandidate("stale-wt", "/wt/s", False, True, now - 40 * 86400)]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s, b: None)
    assert wiz._all_branch == []
    wiz.destroy()
