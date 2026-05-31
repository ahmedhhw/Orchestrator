"""Tests for composite (owner, repo, number) PR key across the VM layer."""
import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck, PRComment


def _make_pr(number=1, owner="myorg", repo="myrepo", comments=None, checks=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        checks=checks or [], comments=comments or [],
    )


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.github_vm import GitHubViewModel
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    return v


# ── pr_state keyed by pr_key, not bare number ─────────────────────────────────

def test_pr_state_keyed_by_pr_key(vm):
    pr = _make_pr(2, owner="ahmedhhw", repo="Orchestrator")
    vm._emit_pr_events([pr])
    assert ("ahmedhhw", "Orchestrator", 2) in vm._pr_state
    assert 2 not in vm._pr_state


def test_two_prs_same_number_different_repos_both_in_state(vm):
    pr1 = _make_pr(2, owner="ahmedhhw", repo="Orchestrator")
    pr2 = _make_pr(2, owner="ahmedhhw", repo="time-control-swift")
    vm._emit_pr_events([pr1, pr2])
    assert ("ahmedhhw", "Orchestrator", 2) in vm._pr_state
    assert ("ahmedhhw", "time-control-swift", 2) in vm._pr_state


def test_events_de_duped_per_repo_not_globally(vm):
    """A comment on repo A must not suppress notification for same comment id on repo B."""
    c = PRComment(id=99, author="alice", body="hi", created_at="t")
    pr_a = _make_pr(2, owner="org", repo="a", comments=[c])
    pr_b = _make_pr(2, owner="org", repo="b", comments=[c])
    vm._emit_pr_events([pr_a, pr_b])  # seed both

    events = []
    vm.pr_event.connect(lambda key, t, m: events.append((key, t)))

    # New comment on repo a
    c2 = PRComment(id=100, author="bob", body="yo", created_at="t")
    pr_a2 = _make_pr(2, owner="org", repo="a", comments=[c, c2])
    pr_b2 = _make_pr(2, owner="org", repo="b", comments=[c])  # no new comment
    vm._emit_pr_events([pr_a2, pr_b2])

    new_comment_events = [(k, t) for k, t in events if t == "new_comment"]
    assert len(new_comment_events) == 1
    assert new_comment_events[0][0] == ("org", "a", 2)


# ── select_pr and merge_pr take a PullRequest ─────────────────────────────────

def test_select_pr_takes_pr_object(vm):
    pr = _make_pr(2, owner="ahmedhhw", repo="Orchestrator")
    vm.prs = [pr]
    svc = MagicMock()
    svc.get_pr_detail.return_value = pr
    vm._svc = svc
    vm.select_pr(pr)
    svc.get_pr_detail.assert_called_once_with(2, pr=pr)


def test_merge_pr_takes_pr_object(vm):
    pr = _make_pr(2, owner="ahmedhhw", repo="Orchestrator")
    vm.prs = [pr]
    svc = MagicMock()
    vm._svc = svc
    with patch.object(vm, "total_fetch"):
        vm.merge_pr(pr)
    svc.merge_pr.assert_called_once_with(pr, squash=True)


# ── unread_comment_count / mark_pr_comments_seen take a PullRequest ───────────

def test_unread_comment_count_takes_pr_object(vm):
    pr = _make_pr(2, owner="ahmedhhw", repo="Orchestrator")
    assert vm.unread_comment_count(pr) == 0


def test_mark_pr_comments_seen_takes_pr_object(vm):
    pr = _make_pr(2, owner="ahmedhhw", repo="Orchestrator")
    vm._unseen_comment_ids_by_pr[pr.pr_key] = {10, 11}
    vm.mark_pr_comments_seen(pr)
    assert vm.unread_comment_count(pr) == 0


# ── persistence uses pr_key as JSON key ───────────────────────────────────────

def test_persisted_state_uses_composite_key(tmp_path):
    import json
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.github_vm import GitHubViewModel
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()

    pr1 = _make_pr(2, owner="ahmedhhw", repo="Orchestrator")
    pr2 = _make_pr(2, owner="ahmedhhw", repo="time-control-swift")
    v._emit_pr_events([pr1, pr2])

    data = json.loads((tmp_path / "github_pr_state.json").read_text())
    assert "ahmedhhw/Orchestrator/2" in data
    assert "ahmedhhw/time-control-swift/2" in data
    v.deleteLater()


def test_persisted_state_roundtrips_composite_key(tmp_path):
    import json
    from worktree_manager.config_store import ConfigStore
    from worktree_manager.github_vm import GitHubViewModel
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")

    with patch("worktree_manager.github_vm.GitHubService"):
        v1 = GitHubViewModel(store=store)
        v1._total_timer.stop()
        v1._quick_timer.stop()

    c = PRComment(id=7, author="bob", body="hi", created_at="t")
    pr = _make_pr(2, owner="ahmedhhw", repo="Orchestrator", comments=[c])
    v1._emit_pr_events([pr])
    v1.deleteLater()

    with patch("worktree_manager.github_vm.GitHubService"):
        v2 = GitHubViewModel(store=store)
        v2._total_timer.stop()
        v2._quick_timer.stop()

    key = ("ahmedhhw", "Orchestrator", 2)
    assert key in v2._pr_state
    assert 7 in v2._pr_state[key]["comment_ids"]
    v2.deleteLater()
