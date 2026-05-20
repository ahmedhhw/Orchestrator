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
