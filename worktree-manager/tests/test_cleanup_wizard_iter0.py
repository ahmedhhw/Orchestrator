import pytest
import time
from unittest.mock import MagicMock, patch


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


def test_cleanup_wizard_has_no_filter_radio_buttons(root):
    from worktree_manager.models import CleanupCandidate
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    now = int(time.time())
    candidates = [
        CleanupCandidate("fix/old", None, True, False, now - 5 * 86400, "main"),
    ]
    wizard = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    assert not hasattr(wizard, "_filter")
    wizard.destroy()


def test_cleanup_wizard_has_no_also_branches_checkbox(root):
    from worktree_manager.models import CleanupCandidate
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    now = int(time.time())
    candidates = [
        CleanupCandidate("fix/old", None, True, False, now - 5 * 86400, "main"),
    ]
    wizard = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    assert not hasattr(wizard, "_also_branches")
    wizard.destroy()


def test_cleanup_wizard_delete_calls_callback_with_pairs(root):
    from worktree_manager.models import CleanupCandidate
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    now = int(time.time())
    candidates = [
        CleanupCandidate("fix/old", None, True, False, now - 5 * 86400, "main"),
    ]
    calls = []
    wizard = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: calls.append(s))
    for c, var in wizard._all_pairs:
        var.set(True)
    wizard._delete_selected()
    assert len(calls) == 1
    assert calls[0][0][0].branch == "fix/old"
    wizard.destroy()


def test_cleanup_wizard_groups_merged_before_stale(root):
    from worktree_manager.models import CleanupCandidate
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    now = int(time.time())
    candidates = [
        CleanupCandidate("stale/one", None, False, True, now - 40 * 86400),
        CleanupCandidate("merged/one", None, True, False, now - 5 * 86400, "main"),
    ]
    wizard = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    branches_in_order = [c.branch for c, _ in wizard._all_pairs]
    assert branches_in_order.index("merged/one") < branches_in_order.index("stale/one")
    wizard.destroy()


def test_cleanup_wizard_priority_items_pre_checked(root):
    from worktree_manager.models import CleanupCandidate
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    now = int(time.time())
    candidates = [
        CleanupCandidate("fix/merged", None, True, False, now - 5 * 86400, "main"),
        CleanupCandidate("fix/stale", None, False, True, now - 40 * 86400),
        CleanupCandidate("fix/healthy", None, False, False, now - 1 * 86400),
    ]
    wizard = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    status = {c.branch: v.get() for c, v in wizard._all_pairs}
    assert status["fix/merged"] is True
    assert status["fix/stale"] is True
    assert status["fix/healthy"] is False
    wizard.destroy()


def test_cleanup_wizard_uncommitted_items_disabled(root):
    import customtkinter as ctk
    from worktree_manager.models import CleanupCandidate
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    now = int(time.time())
    candidates = [
        CleanupCandidate("fix/dirty", None, True, False, now - 5 * 86400, "main", has_uncommitted=True),
    ]
    wizard = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    # Uncommitted item should not be checked
    status = {c.branch: v.get() for c, v in wizard._all_pairs}
    assert status["fix/dirty"] is False
    wizard.destroy()
