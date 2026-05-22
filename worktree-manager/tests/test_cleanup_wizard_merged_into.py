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
    wiz = CleanupWizard(root, candidates=[healthy, stale], on_delete_selected=lambda s: None)
    status = {c.branch: v.get() for c, v in wiz._all_pairs}
    assert status["old/thing"] is True
    assert status["wip/thing"] is False
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
    wiz = CleanupWizard(root, candidates=[healthy, stale], on_delete_selected=lambda s: None)
    branches_in_order = [c.branch for c, _ in wiz._all_pairs]
    assert branches_in_order.index("old/thing") < branches_in_order.index("wip/thing")
    wiz.destroy()


def test_cleanup_wizard_smoke_with_healthy_and_stale(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("wip/thing", None, False, False, now - 2 * 86400),
        CleanupCandidate("release/1.0", None, True, False, now - 5 * 86400),
        CleanupCandidate("hotfix/patch", None, False, False, now - 1 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    wiz.destroy()


def test_uncommitted_item_is_unchecked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate(
        branch="wip/dirty", path=None, is_merged=False, is_stale=True,
        last_commit_ts=now - 40 * 86400, has_uncommitted=True,
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    status = {cand.branch: v.get() for cand, v in wiz._all_pairs}
    assert status["wip/dirty"] is False
    wiz.destroy()


def test_uncommitted_item_shows_warning_label(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate(
        branch="wip/dirty", path=None, is_merged=False, is_stale=True,
        last_commit_ts=now - 40 * 86400, has_uncommitted=True,
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("uncommitted" in t.lower() for t in texts)
    wiz.destroy()


def test_clean_merged_item_is_checked(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate(
        branch="old/clean", path=None, is_merged=True, is_stale=False,
        last_commit_ts=now - 5 * 86400, has_uncommitted=False,
    )
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    status = {cand.branch: v.get() for cand, v in wiz._all_pairs}
    assert status["old/clean"] is True
    texts = _collect_text(wiz)
    assert not any("uncommitted" in t.lower() for t in texts)
    wiz.destroy()


def test_select_all_checks_all_vars(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("a", None, False, False, now - 1 * 86400),
        CleanupCandidate("b", None, False, False, now - 2 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    wiz._select_all()
    assert all(v.get() for _, v in wiz._all_pairs)
    wiz.destroy()


def test_deselect_all_unchecks_all_vars(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("a", None, False, True, now - 40 * 86400),
        CleanupCandidate("b", None, True, False, now - 5 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    wiz._deselect_all()
    assert not any(v.get() for _, v in wiz._all_pairs)
    wiz.destroy()


def test_delete_selected_passes_selected_pairs(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate("stale-branch", None, False, True, now - 40 * 86400)
    calls = []
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=lambda s: calls.append(s))
    for _, v in wiz._all_pairs:
        v.set(True)
    wiz._delete_selected()
    assert len(calls) == 1
    assert calls[0][0][0].branch == "stale-branch"


def test_uncommitted_excluded_from_delete_callback(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    dirty = CleanupCandidate(
        branch="wip/dirty", path=None, is_merged=False, is_stale=True,
        last_commit_ts=now - 40 * 86400, has_uncommitted=True,
    )
    clean = CleanupCandidate(
        branch="old/clean", path=None, is_merged=True, is_stale=False,
        last_commit_ts=now - 5 * 86400, has_uncommitted=False,
    )
    deleted = []
    wiz = CleanupWizard(root, candidates=[dirty, clean],
                        on_delete_selected=lambda s: deleted.extend([c for c, _ in s]))
    wiz._delete_selected()
    assert all(c.branch != "wip/dirty" for c in deleted)
    assert any(c.branch == "old/clean" for c in deleted)
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


# ---------------------------------------------------------------------------
# _group_candidates — pure function
# ---------------------------------------------------------------------------

def test_group_candidates_merged_goes_to_merged():
    import time
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("m", None, True, False, now - 5 * 86400)
    result = _group_candidates([c])
    assert c in result["merged"]
    assert c not in result["stale"]
    assert c not in result["healthy"]


def test_group_candidates_stale_goes_to_stale():
    import time
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("s", None, False, True, now - 30 * 86400)
    result = _group_candidates([c])
    assert c in result["stale"]
    assert c not in result["merged"]
    assert c not in result["healthy"]


def test_group_candidates_healthy_goes_to_healthy():
    import time
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("h", None, False, False, now - 2 * 86400)
    result = _group_candidates([c])
    assert c in result["healthy"]
    assert c not in result["merged"]
    assert c not in result["stale"]


def test_group_candidates_both_merged_and_stale_goes_to_merged_only():
    import time
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("both", None, True, True, now - 40 * 86400)
    result = _group_candidates([c])
    assert c in result["merged"]
    assert c not in result["stale"]
    assert c not in result["healthy"]


def test_group_candidates_stale_sorted_oldest_first():
    import time
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    newer = CleanupCandidate("newer", None, False, True, now - 10 * 86400)
    older = CleanupCandidate("older", None, False, True, now - 50 * 86400)
    result = _group_candidates([newer, older])
    assert result["stale"][0].branch == "older"
    assert result["stale"][1].branch == "newer"


def test_group_candidates_merged_sorted_by_target_then_branch():
    import time
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    b = CleanupCandidate("b-branch", None, True, False, now, merged_into="main")
    a = CleanupCandidate("a-branch", None, True, False, now, merged_into="main")
    d = CleanupCandidate("d-branch", None, True, False, now, merged_into="develop")
    result = _group_candidates([b, a, d])
    names = [c.branch for c in result["merged"]]
    assert names == ["d-branch", "a-branch", "b-branch"]


def test_group_candidates_merged_none_target_sorts_as_main():
    import time
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    no_target = CleanupCandidate("z-branch", None, True, False, now, merged_into=None)
    develop = CleanupCandidate("a-branch", None, True, False, now, merged_into="develop")
    result = _group_candidates([no_target, develop])
    assert result["merged"][0].merged_into == "develop"
    assert result["merged"][1].merged_into is None


def test_group_candidates_healthy_preserves_insertion_order():
    import time
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    a = CleanupCandidate("a", None, False, False, now - 5 * 86400)
    b = CleanupCandidate("b", None, False, False, now - 1 * 86400)
    result = _group_candidates([a, b])
    assert result["healthy"] == [a, b]


def test_group_candidates_empty_list_returns_empty_groups():
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    result = _group_candidates([])
    assert result == {"merged": [], "stale": [], "healthy": []}


def test_group_candidates_returns_all_three_keys():
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    result = _group_candidates([])
    assert set(result.keys()) == {"merged", "stale", "healthy"}


# ---------------------------------------------------------------------------
# Three-category rendering
# ---------------------------------------------------------------------------

def test_section_shows_merged_label(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate("m", None, True, False, now - 5 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=lambda s: None)
    texts = _collect_text(wiz)
    assert any("Merged" in t for t in texts)
    wiz.destroy()


def test_section_shows_stale_label(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate("s", None, False, True, now - 40 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=lambda s: None)
    texts = _collect_text(wiz)
    assert any("Stale" in t for t in texts)
    wiz.destroy()


def test_section_shows_healthy_label(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate("h", None, False, False, now - 2 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=lambda s: None)
    texts = _collect_text(wiz)
    assert any("Healthy" in t for t in texts)
    wiz.destroy()


def test_section_shows_none_for_empty_stale_group(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    c = CleanupCandidate("h", None, False, False, now - 2 * 86400)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=lambda s: None)
    texts = _collect_text(wiz)
    assert any("none" in t.lower() for t in texts)
    wiz.destroy()


def test_stale_rendered_oldest_first_in_ui(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("newer-stale", None, False, True, now - 10 * 86400),
        CleanupCandidate("older-stale", None, False, True, now - 50 * 86400),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    texts = _collect_text(wiz)
    combined = " ".join(texts)
    assert combined.index("50d") < combined.index("10d")
    wiz.destroy()


def test_merged_rendered_sorted_by_target_then_branch_in_ui(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    import time
    now = int(time.time())
    candidates = [
        CleanupCandidate("z-branch", None, True, False, now, merged_into="main"),
        CleanupCandidate("a-branch", None, True, False, now, merged_into="develop"),
    ]
    wiz = CleanupWizard(root, candidates=candidates, on_delete_selected=lambda s: None)
    texts = _collect_text(wiz)
    combined = " ".join(texts)
    assert combined.index("develop") < combined.index("main")
    wiz.destroy()
