import pytest
import time
from unittest.mock import MagicMock
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.models import RepoConfig, WorktreeModel
from worktree_manager.main_window_vm import MainWindowViewModel


def _ctk_available():
    try:
        import customtkinter
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# VM — protected branches included with is_protected=True
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    s = ConfigStore(tmp_path / "config.json")
    s.save_repo(RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-23T10:00:00",
    ))
    return s


@pytest.fixture
def git():
    return MagicMock(spec=GitService)


def _make_vm(store, git, worktrees, local_branches=None, feature_branches=None, merged_map=None, last_commit_ts=None):
    git.list_worktrees.return_value = worktrees
    git.list_local_branches.return_value = local_branches or []
    git.list_feature_branches.return_value = feature_branches or []
    git.build_merged_map.return_value = merged_map or {}
    git.has_uncommitted_changes.return_value = False
    if last_commit_ts is not None:
        git.last_commit_ts.return_value = last_commit_ts
    vm = MainWindowViewModel(repo_path="/repos/proj", config_store=store, git_service=git)
    vm.load_worktrees()
    return vm


def test_all_cleanup_candidates_includes_protected_worktree(store, git):
    now = int(time.time())
    vm = _make_vm(store, git, [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feature-pay", "feature/payments", False, now - 5 * 86400, False, False),
        WorktreeModel("/repos/proj-wt/fix-bug", "fix/bug", False, now - 40 * 86400, False, True),
    ])
    candidates = vm.all_cleanup_candidates()
    protected = [c for c in candidates if c.branch == "feature/payments"]
    assert len(protected) == 1
    assert protected[0].is_protected is True


def test_all_cleanup_candidates_includes_protected_orphan_branch(store, git):
    now = int(time.time())
    vm = _make_vm(store, git,
        worktrees=[WorktreeModel("/repos/proj", "main", True, now, False, False)],
        local_branches=["main", "feature/payments"],
        feature_branches=["feature/payments"],
        merged_map={"feature/payments": "main"},
        last_commit_ts=now - 5 * 86400,
    )
    candidates = vm.all_cleanup_candidates()
    protected = [c for c in candidates if c.branch == "feature/payments"]
    assert len(protected) == 1
    assert protected[0].is_protected is True


def test_all_cleanup_candidates_main_worktree_included_as_protected(store, git):
    now = int(time.time())
    vm = _make_vm(store, git, [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-bug", "fix/bug", False, now - 40 * 86400, False, True),
    ])
    candidates = vm.all_cleanup_candidates()
    main_candidates = [c for c in candidates if c.branch == "main"]
    assert len(main_candidates) == 1
    assert main_candidates[0].is_protected is True
    assert main_candidates[0].is_checked_out is True


def test_all_cleanup_candidates_main_worktree_with_uncommitted(store, git):
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    git.list_local_branches.return_value = []
    git.list_feature_branches.return_value = []
    git.build_merged_map.return_value = {}
    git.has_uncommitted_changes.return_value = True
    vm = MainWindowViewModel(repo_path="/repos/proj", config_store=store, git_service=git)
    vm.load_worktrees()
    candidates = vm.all_cleanup_candidates()
    main_c = next(c for c in candidates if c.branch == "main")
    assert main_c.has_uncommitted is True


def test_all_cleanup_candidates_operable_branch_has_is_protected_false(store, git):
    now = int(time.time())
    vm = _make_vm(store, git,
        worktrees=[WorktreeModel("/repos/proj", "main", True, now, False, False)],
        local_branches=["main", "fix/thing"],
        merged_map={"fix/thing": "main"},
        last_commit_ts=now - 5 * 86400,
    )
    candidates = vm.all_cleanup_candidates()
    fix = next(c for c in candidates if c.branch == "fix/thing")
    assert fix.is_protected is False


# ---------------------------------------------------------------------------
# Wizard — _group_candidates routes protected and unoperable into own buckets
# ---------------------------------------------------------------------------

def test_group_candidates_protected_goes_to_protected_bucket():
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("feature/pay", None, False, False, now - 5 * 86400, is_protected=True)
    result = _group_candidates([c])
    assert c in result["protected"]
    assert c not in result["merged"]
    assert c not in result["stale"]
    assert c not in result["healthy"]


def test_group_candidates_unoperable_checked_out_goes_to_unoperable():
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("dev/active", None, False, False, now - 1 * 86400, is_checked_out=True)
    result = _group_candidates([c])
    assert c in result["unoperable"]
    assert c not in result["merged"]
    assert c not in result["healthy"]


def test_group_candidates_unoperable_uncommitted_goes_to_unoperable():
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("wip/dirty", None, False, False, now - 1 * 86400, has_uncommitted=True)
    result = _group_candidates([c])
    assert c in result["unoperable"]
    assert c not in result["healthy"]


def test_group_candidates_returns_five_keys():
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    result = _group_candidates([])
    assert set(result.keys()) == {"merged", "stale", "healthy", "protected", "unoperable"}


def test_group_candidates_operable_branch_not_in_protected_or_unoperable():
    from worktree_manager.ui.cleanup_wizard import _group_candidates
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("fix/bug", None, True, False, now - 5 * 86400, merged_into="main")
    result = _group_candidates([c])
    assert c not in result["protected"]
    assert c not in result["unoperable"]
    assert c in result["merged"]


# ---------------------------------------------------------------------------
# Wizard UI — Protected and Cannot-delete sections rendered correctly
# ---------------------------------------------------------------------------

pytestmark_ctk = pytest.mark.skipif(not _ctk_available(), reason="customtkinter not installed")


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


@pytestmark_ctk
def test_wizard_shows_protected_section_header(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("feature/pay", None, False, False, now - 5 * 86400, is_protected=True)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("Protected" in t for t in texts)
    wiz.destroy()


@pytestmark_ctk
def test_wizard_shows_cannot_delete_section_header(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("dev/active", None, False, False, now - 1 * 86400, is_checked_out=True)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("Cannot delete" in t for t in texts)
    wiz.destroy()


@pytestmark_ctk
def test_wizard_protected_branch_not_in_all_pairs(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    protected = CleanupCandidate("feature/pay", None, False, False, now - 5 * 86400, is_protected=True)
    operable = CleanupCandidate("fix/bug", None, True, False, now - 5 * 86400, merged_into="main")
    wiz = CleanupWizard(root, candidates=[protected, operable], on_delete_selected=MagicMock())
    pair_branches = [c.branch for c, _ in wiz._all_pairs]
    assert "feature/pay" not in pair_branches
    assert "fix/bug" in pair_branches
    wiz.destroy()


@pytestmark_ctk
def test_wizard_unoperable_branch_not_in_all_pairs(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    unoperable = CleanupCandidate("dev/active", None, False, False, now - 1 * 86400, is_checked_out=True)
    operable = CleanupCandidate("fix/bug", None, True, False, now - 5 * 86400, merged_into="main")
    wiz = CleanupWizard(root, candidates=[unoperable, operable], on_delete_selected=MagicMock())
    pair_branches = [c.branch for c, _ in wiz._all_pairs]
    assert "dev/active" not in pair_branches
    assert "fix/bug" in pair_branches
    wiz.destroy()


@pytestmark_ctk
def test_wizard_select_all_does_not_affect_protected(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    protected = CleanupCandidate("feature/pay", None, False, False, now - 5 * 86400, is_protected=True)
    operable = CleanupCandidate("fix/bug", None, True, False, now - 5 * 86400, merged_into="main")
    wiz = CleanupWizard(root, candidates=[protected, operable], on_delete_selected=MagicMock())
    wiz._select_all()
    pair_branches = [c.branch for c, _ in wiz._all_pairs]
    assert "feature/pay" not in pair_branches
    wiz.destroy()


@pytestmark_ctk
def test_wizard_protected_branch_shows_warning_tag(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    main_branch = CleanupCandidate("main", None, False, False, now - 1 * 86400, is_protected=True)
    wiz = CleanupWizard(root, candidates=[main_branch], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("main" in t.lower() for t in texts)
    wiz.destroy()


@pytestmark_ctk
def test_wizard_feature_protected_branch_shows_feature_tag(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    feat = CleanupCandidate("feature/payments", None, False, False, now - 1 * 86400, is_protected=True)
    wiz = CleanupWizard(root, candidates=[feat], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("feature" in t.lower() for t in texts)
    wiz.destroy()


@pytestmark_ctk
def test_wizard_unoperable_checked_out_shows_dash_not_checkbox(root):
    from worktree_manager.ui.cleanup_wizard import CleanupWizard
    from worktree_manager.models import CleanupCandidate
    now = int(time.time())
    c = CleanupCandidate("dev/active", None, False, False, now - 1 * 86400, is_checked_out=True)
    wiz = CleanupWizard(root, candidates=[c], on_delete_selected=MagicMock())
    texts = _collect_text(wiz)
    assert any("—" in t or "checked out" in t.lower() for t in texts)
    wiz.destroy()
