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


def _make_wizard_with_protected(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    candidates = [
        CleanupCandidate("fix/a", None, True, False, now, merged_into="main"),
        CleanupCandidate("feature/payments", None, False, False, now - 5 * 86400, is_protected=True),
        CleanupCandidate("main", None, False, False, now, is_protected=True, is_checked_out=True),
    ]
    return CleanupWizard(root, candidates=candidates, on_delete_selected=MagicMock())


# ---------------------------------------------------------------------------
# Admin Mode toggle exists and defaults to OFF
# ---------------------------------------------------------------------------

def test_admin_mode_checkbox_exists(root):
    wiz = _make_wizard_with_protected(root)
    assert hasattr(wiz, "_admin_mode_var")
    wiz.destroy()


def test_admin_mode_off_by_default(root):
    wiz = _make_wizard_with_protected(root)
    assert wiz._admin_mode_var.get() is False
    wiz.destroy()


def test_admin_mode_checkbox_label_shown(root):
    wiz = _make_wizard_with_protected(root)
    texts = _collect_text(wiz)
    assert any("Admin Mode" in t for t in texts)
    wiz.destroy()


def test_admin_mode_warning_hint_shown(root):
    wiz = _make_wizard_with_protected(root)
    texts = _collect_text(wiz)
    assert any("know what you're doing" in t for t in texts)
    wiz.destroy()


# ---------------------------------------------------------------------------
# Warning banner hidden by default, shown when Admin Mode ON
# ---------------------------------------------------------------------------

def test_warning_banner_hidden_when_admin_mode_off(root):
    wiz = _make_wizard_with_protected(root)
    assert not wiz._admin_banner.winfo_ismapped()
    wiz.destroy()


def test_warning_banner_shown_when_admin_mode_on(root):
    wiz = _make_wizard_with_protected(root)
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    assert wiz._admin_banner.winfo_ismapped()
    wiz.destroy()


def test_warning_banner_hidden_again_when_admin_mode_turned_off(root):
    wiz = _make_wizard_with_protected(root)
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    wiz._admin_mode_var.set(False)
    wiz._on_admin_mode_toggle()
    assert not wiz._admin_banner.winfo_ismapped()
    wiz.destroy()


# ---------------------------------------------------------------------------
# Protected checkboxes: disabled OFF, enabled ON
# ---------------------------------------------------------------------------

def test_protected_checkboxes_disabled_when_admin_mode_off(root):
    wiz = _make_wizard_with_protected(root)
    for c, var, cb in wiz._protected_triples:
        assert cb.cget("state") == "disabled"
    wiz.destroy()


def test_protected_checkboxes_enabled_when_admin_mode_on(root):
    wiz = _make_wizard_with_protected(root)
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    for c, var, cb in wiz._protected_triples:
        assert cb.cget("state") == "normal"
    wiz.destroy()


def test_protected_checkboxes_disabled_again_when_admin_mode_turned_off(root):
    wiz = _make_wizard_with_protected(root)
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    wiz._admin_mode_var.set(False)
    wiz._on_admin_mode_toggle()
    for c, var, cb in wiz._protected_triples:
        assert cb.cget("state") == "disabled"
    wiz.destroy()


# ---------------------------------------------------------------------------
# Protected branches never pre-checked, even when Admin Mode ON
# ---------------------------------------------------------------------------

def test_protected_branches_not_pre_checked_when_admin_mode_on(root):
    wiz = _make_wizard_with_protected(root)
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    for _, var, _ in wiz._protected_triples:
        assert var.get() is False
    wiz.destroy()


def test_protected_selections_cleared_when_admin_mode_turned_off(root):
    wiz = _make_wizard_with_protected(root)
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    # manually check a protected branch
    for _, var, _ in wiz._protected_triples:
        var.set(True)
    # turn off admin mode
    wiz._admin_mode_var.set(False)
    wiz._on_admin_mode_toggle()
    for _, var, _ in wiz._protected_triples:
        assert var.get() is False
    wiz.destroy()


# ---------------------------------------------------------------------------
# ⚠ admin only label on Protected header
# ---------------------------------------------------------------------------

def test_admin_only_label_hidden_when_admin_mode_off(root):
    wiz = _make_wizard_with_protected(root)
    assert not wiz._admin_only_label.winfo_ismapped()
    wiz.destroy()


def test_admin_only_label_shown_when_admin_mode_on(root):
    wiz = _make_wizard_with_protected(root)
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    assert wiz._admin_only_label.winfo_ismapped()
    wiz.destroy()


def test_admin_only_label_hidden_again_when_admin_mode_turned_off(root):
    wiz = _make_wizard_with_protected(root)
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    wiz._admin_mode_var.set(False)
    wiz._on_admin_mode_toggle()
    assert not wiz._admin_only_label.winfo_ismapped()
    wiz.destroy()


# ---------------------------------------------------------------------------
# Unoperable branches unaffected by Admin Mode
# ---------------------------------------------------------------------------

def test_unoperable_not_selectable_with_admin_mode_on(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    candidates = [
        CleanupCandidate("dev/active", None, False, False, now, is_checked_out=True),
        CleanupCandidate("feature/pay", None, False, False, now, is_protected=True),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=MagicMock())
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    # unoperable never appears in any selectable collection
    all_selectable_branches = [c.branch for c, _ in wiz._all_pairs] + [c.branch for c, _, _ in wiz._protected_triples]
    assert "dev/active" not in all_selectable_branches
    wiz.destroy()


# ---------------------------------------------------------------------------
# Delete includes selected protected branches when Admin Mode ON
# ---------------------------------------------------------------------------

def test_delete_includes_selected_protected_branch_when_admin_mode_on(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    protected = CleanupCandidate("feature/pay", None, False, False, now, is_protected=True)
    calls = []
    wiz = CleanupWizard(root, candidates=[protected], on_delete_selected=lambda s: calls.append(s))
    wiz._admin_mode_var.set(True)
    wiz._on_admin_mode_toggle()
    for _, var, _ in wiz._protected_triples:
        var.set(True)
    wiz._delete_selected()
    assert any(c.branch == "feature/pay" for c, _ in calls[0])
    wiz.destroy()


def test_delete_excludes_protected_branch_when_admin_mode_off(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    protected = CleanupCandidate("feature/pay", None, False, False, now, is_protected=True)
    operable = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    calls = []
    wiz = CleanupWizard(root, candidates=[protected, operable], on_delete_selected=lambda s: calls.append(s))
    wiz._delete_selected()
    deleted_branches = [c.branch for c, _ in calls[0]]
    assert "feature/pay" not in deleted_branches
    wiz.destroy()
