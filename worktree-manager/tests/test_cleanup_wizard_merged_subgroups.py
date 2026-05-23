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
# Pure function — _merged_subgroups
# ---------------------------------------------------------------------------

def test_merged_subgroups_groups_by_target():
    from worktree_manager.ui.cleanup_wizard import _merged_subgroups
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    a = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    b = CleanupCandidate("fix/b", None, True, False, now, merged_into="main")
    c = CleanupCandidate("fix/c", None, True, False, now, merged_into="feature/payments")
    result = _merged_subgroups([a, b, c])
    assert len(result) == 2
    targets = [t for t, _ in result]
    assert "main" in targets
    assert "feature/payments" in targets


def test_merged_subgroups_branches_sorted_within_group():
    from worktree_manager.ui.cleanup_wizard import _merged_subgroups
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    z = CleanupCandidate("z-fix", None, True, False, now, merged_into="main")
    a = CleanupCandidate("a-fix", None, True, False, now, merged_into="main")
    result = _merged_subgroups([z, a])
    _, branches = result[0]
    assert [c.branch for c in branches] == ["a-fix", "z-fix"]


def test_merged_subgroups_targets_sorted_alphabetically():
    from worktree_manager.ui.cleanup_wizard import _merged_subgroups
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    a = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    b = CleanupCandidate("fix/b", None, True, False, now, merged_into="feature/payments")
    c = CleanupCandidate("fix/c", None, True, False, now, merged_into="develop")
    result = _merged_subgroups([a, b, c])
    targets = [t for t, _ in result]
    assert targets == sorted(targets)


def test_merged_subgroups_none_target_treated_as_main():
    from worktree_manager.ui.cleanup_wizard import _merged_subgroups
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/x", None, True, False, now, merged_into=None)
    result = _merged_subgroups([c])
    target, branches = result[0]
    assert target == "main"
    assert c in branches


def test_merged_subgroups_empty_returns_empty():
    from worktree_manager.ui.cleanup_wizard import _merged_subgroups
    assert _merged_subgroups([]) == []


# ---------------------------------------------------------------------------
# Wizard UI — sub-group headers and Select all buttons rendered
# ---------------------------------------------------------------------------

def test_wizard_shows_into_main_subgroup_header(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("main" in t for t in texts)
    wiz.destroy()


def test_wizard_shows_into_feature_subgroup_header(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/a", None, True, False, now, merged_into="feature/payments")
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("feature/payments" in t for t in texts)
    wiz.destroy()


def test_wizard_shows_toggle_button_for_merged_subgroup(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("Select all" in t or "Deselect all" in t for t in texts)
    wiz.destroy()


def test_wizard_select_all_for_subgroup_only_checks_that_target(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    into_main = CleanupCandidate("fix/main-branch", None, True, False, now, merged_into="main")
    into_payments = CleanupCandidate("fix/pay-branch", None, True, False, now, merged_into="feature/payments")
    wiz = CleanupWizard(root, candidates=[into_main, into_payments], on_delete_selected=MagicMock())
    # Deselect everything first
    wiz._deselect_all()
    # Call the per-group select for "main"
    wiz._select_subgroup("main")
    status = {c.branch: v.get() for c, v in wiz._all_pairs}
    assert status["fix/main-branch"] is True
    assert status["fix/pay-branch"] is False
    wiz.destroy()


def test_wizard_select_subgroup_does_not_affect_protected(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    operable = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    protected = CleanupCandidate("feature/pay", None, True, False, now, merged_into="main", is_protected=True)
    wiz = CleanupWizard(root, candidates=[operable, protected], on_delete_selected=MagicMock())
    wiz._deselect_all()
    wiz._select_subgroup("main")
    pair_branches = [c.branch for c, _ in wiz._all_pairs]
    assert "feature/pay" not in pair_branches
    wiz.destroy()


def test_wizard_two_subgroups_both_have_toggle_buttons(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    a = CleanupCandidate("fix/a", None, True, False, now, merged_into="main")
    b = CleanupCandidate("fix/b", None, True, False, now, merged_into="feature/payments")
    wiz = CleanupWizard(root, candidates=[a, b], on_delete_selected=MagicMock())
    assert len(wiz._subgroup_btn) == 2
    wiz.destroy()


def test_wizard_stale_section_has_toggle_button(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("old/thing", None, False, True, now - 40 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    assert wiz._stale_btn is not None
    wiz.destroy()


def test_wizard_select_all_stale_checks_only_stale_branches(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    stale = CleanupCandidate("old/thing", None, False, True, now - 40 * 86400)
    healthy = CleanupCandidate("wip/thing", None, False, False, now - 2 * 86400)
    wiz = CleanupWizard(root, candidates=[stale, healthy], on_delete_selected=MagicMock())
    wiz._deselect_all()
    wiz._select_stale()
    status = {c.branch: v.get() for c, v in wiz._all_pairs}
    assert status["old/thing"] is True
    assert status["wip/thing"] is False
    wiz.destroy()
