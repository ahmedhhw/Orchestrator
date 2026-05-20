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
