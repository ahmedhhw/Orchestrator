import pytest
import time
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
    for cls in (ctk.CTkLabel, ctk.CTkCheckBox, ctk.CTkButton):
        if isinstance(widget, cls):
            result.append(getattr(widget, "_text", ""))
    for child in widget.winfo_children():
        result.extend(_collect_text(child))
    return result


# ---------------------------------------------------------------------------
# Global Select All / Deselect All toggle
# ---------------------------------------------------------------------------

def test_global_button_shows_deselect_all_when_all_checked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    # fix/a is merged so pre-checked — all operable are checked
    texts = _collect_text(wiz)
    assert any("Deselect All" in t for t in texts)
    assert not any(t == "Select All" for t in texts)
    wiz.destroy()


def test_global_button_shows_select_all_when_not_all_checked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("wip/thing", None, False, False, now - 2 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    # healthy — not pre-checked
    texts = _collect_text(wiz)
    assert any("Select All" in t for t in texts)
    assert not any(t == "Deselect All" for t in texts)
    wiz.destroy()


def test_global_button_toggles_to_deselect_after_select_all(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("wip/thing", None, False, False, now - 2 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    wiz._select_all()
    texts = _collect_text(wiz)
    assert any("Deselect All" in t for t in texts)
    assert not any(t == "Select All" for t in texts)
    wiz.destroy()


def test_global_button_toggles_back_to_select_after_deselect_all(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    wiz._deselect_all()
    texts = _collect_text(wiz)
    assert any("Select All" in t for t in texts)
    assert not any(t == "Deselect All" for t in texts)
    wiz.destroy()


# ---------------------------------------------------------------------------
# Per-subgroup merged toggle
# ---------------------------------------------------------------------------

def test_subgroup_button_shows_deselect_all_when_all_in_group_checked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    # fix/a is pre-checked (merged) — subgroup all selected
    texts = _collect_text(wiz)
    assert any("Deselect all" in t for t in texts)
    wiz.destroy()


def test_subgroup_button_shows_select_all_when_group_not_fully_checked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    a = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    b = CleanupCandidate("fix/b", None, True, False, now, merged_into="main")
    wiz = CleanupWizard(root, candidates=[a, b], on_delete_selected=MagicMock())
    # uncheck one
    for c, v in wiz._all_pairs:
        if c.branch == "fix/a":
            v.set(False)
    wiz._refresh_button_labels()
    texts = _collect_text(wiz)
    assert any("Select all" in t for t in texts)
    wiz.destroy()


def test_subgroup_button_toggles_to_deselect_after_select_subgroup(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    wiz._deselect_all()
    wiz._select_subgroup("main")
    texts = _collect_text(wiz)
    assert any("Deselect all" in t for t in texts)
    wiz.destroy()


def test_subgroup_button_independent_of_other_subgroup(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    a = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    b = CleanupCandidate("fix/b", None, True, False, now, merged_into="feature/payments")
    wiz = CleanupWizard(root, candidates=[a, b], on_delete_selected=MagicMock())
    # uncheck only the payments branch
    for c, v in wiz._all_pairs:
        if c.branch == "fix/b":
            v.set(False)
    wiz._refresh_button_labels()
    # main subgroup is fully checked — should show Deselect all
    assert wiz._subgroup_btn["main"]._text == "Deselect all"
    # payments subgroup is not fully checked — should show Select all
    assert wiz._subgroup_btn["feature/payments"]._text == "Select all"
    wiz.destroy()


# ---------------------------------------------------------------------------
# Stale toggle
# ---------------------------------------------------------------------------

def test_stale_button_shows_deselect_all_when_all_stale_checked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("old/thing", None, False, True, now - 40 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    # stale is pre-checked
    texts = _collect_text(wiz)
    assert any("Deselect all" in t for t in texts)
    wiz.destroy()


def test_stale_button_shows_select_all_when_stale_unchecked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("old/thing", None, False, True, now - 40 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    wiz._deselect_all()
    wiz._refresh_button_labels()
    texts = _collect_text(wiz)
    assert any("Select all" in t for t in texts)
    wiz.destroy()


def test_stale_button_toggles_to_deselect_after_select_stale(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("old/thing", None, False, True, now - 40 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    wiz._deselect_all()
    wiz._select_stale()
    texts = _collect_text(wiz)
    assert any("Deselect all" in t for t in texts)
    wiz.destroy()
