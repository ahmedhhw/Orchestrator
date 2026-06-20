"""Tests for PR list cache: _save_pr_cache / _load_pr_cache / startup wiring."""
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worktree_manager.github_models import CICheck, PullRequest
from worktree_manager.github_vm import GitHubViewModel


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_pr(number=1, owner="org", repo="repo", checks=None, reviews=None, comments=None):
    from worktree_manager.github_models import PRComment, Review
    return PullRequest(
        number=number,
        title=f"PR {number}",
        body="some body",
        html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
        head_branch="feat",
        base_branch="main",
        state="open",
        draft=False,
        mergeable=True,
        mergeable_state="clean",
        checks=checks or [],
        reviews=reviews or [],
        comments=comments or [],
        owner=owner,
        repo=repo,
    )


def _make_vm(store):
    """Return a VM with timers stopped and the startup fetch suppressed."""
    import time
    from PySide6.QtWidgets import QApplication

    svc = MagicMock()
    svc.get_authenticated_user.return_value = "me"
    svc.discover_open_prs.return_value = []
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = svc
        vm = GitHubViewModel(store=store)
        vm._total_timer.stop()
        vm._quick_timer.stop()

    deadline = time.monotonic() + 3.0
    while (not vm._initial_load_done or vm._total_fetch_running) and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    QApplication.processEvents()
    return vm


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


# ── Test 1: saving the PR cache writes versioned envelope ─────────────────────


def test_save_pr_cache_writes_versioned_envelope(store, qtbot):
    vm = _make_vm(store)
    pr = _make_pr(
        number=42,
        checks=[CICheck(name="ci", status="completed", conclusion="success", check_suite_id="suite1")],
    )
    vm.prs = [pr]

    vm._save_pr_cache()

    assert vm._pr_cache_path.exists()
    data = json.loads(vm._pr_cache_path.read_text())
    # new format: versioned envelope
    assert isinstance(data, dict), "Cache must be a dict, not a list"
    assert "version" in data, "Cache must have a 'version' key"
    assert "prs" in data, "Cache must have a 'prs' key"
    assert data["version"] == 1
    assert len(data["prs"]) == 1
    row = data["prs"][0]
    assert row["number"] == 42
    assert row["title"] == "PR 42"
    assert row["head_branch"] == "feat"
    assert row["base_branch"] == "main"
    assert row["state"] == "open"
    assert row["draft"] is False
    assert row["mergeable"] is True
    assert row["mergeable_state"] == "clean"
    assert row["owner"] == "org"
    assert row["repo"] == "repo"
    assert row["html_url"] == "https://github.com/org/repo/pull/42"
    assert len(row["checks"]) == 1
    assert row["checks"][0]["name"] == "ci"
    assert row["checks"][0]["status"] == "completed"
    assert row["checks"][0]["conclusion"] == "success"
    assert row["checks"][0]["check_suite_id"] == "suite1"

    vm.deleteLater()


# ── Test 2: loading the cache reconstructs PullRequest objects with checks ────


def test_load_pr_cache_round_trip(store, qtbot):
    vm = _make_vm(store)
    pr = _make_pr(
        number=7,
        owner="acme",
        repo="backend",
        checks=[
            CICheck(name="lint", status="completed", conclusion="success", check_suite_id="s1"),
            CICheck(name="build", status="completed", conclusion="failure", check_suite_id=None),
        ],
    )
    pr.mergeable = False
    pr.mergeable_state = "dirty"
    vm.prs = [pr]
    vm._save_pr_cache()

    loaded = vm._load_pr_cache()

    assert len(loaded) == 1
    p = loaded[0]
    assert p.number == 7
    assert p.title == "PR 7"
    assert p.head_branch == "feat"
    assert p.base_branch == "main"
    assert p.mergeable is False
    assert p.mergeable_state == "dirty"
    assert p.owner == "acme"
    assert p.repo == "backend"
    assert p.html_url == "https://github.com/acme/backend/pull/7"
    assert len(p.checks) == 2
    assert p.checks[0].name == "lint"
    assert p.checks[0].conclusion == "success"
    assert p.checks[0].check_suite_id == "s1"
    assert p.checks[1].name == "build"
    assert p.checks[1].conclusion == "failure"
    assert p.checks[1].check_suite_id is None

    vm.deleteLater()


# ── Test 3: missing cache file returns [] ─────────────────────────────────────


def test_load_pr_cache_missing_file_returns_empty(store, qtbot):
    vm = _make_vm(store)
    # ensure no cache file exists
    assert not vm._pr_cache_path.exists()

    result = vm._load_pr_cache()

    assert result == []
    vm.deleteLater()


# ── Test 4: corrupt cache file returns [] and logs a warning ─────────────────


def test_load_pr_cache_corrupt_file_returns_empty_and_logs(store, qtbot, caplog):
    vm = _make_vm(store)
    vm._pr_cache_path.write_text("not valid json {{{{")

    with caplog.at_level(logging.WARNING, logger="worktree_manager.github_vm"):
        result = vm._load_pr_cache()

    assert result == []
    assert any("PR cache" in r.message for r in caplog.records), (
        "Expected a warning mentioning PR cache; got: " + str([r.message for r in caplog.records])
    )
    vm.deleteLater()


# ── Test 5: reviews and comments ARE cached and round-trip correctly ──────────


def test_reviews_and_comments_round_trip(store, qtbot):
    from worktree_manager.github_models import PRComment, Review

    vm = _make_vm(store)
    pr = _make_pr(number=3)
    pr.reviews = [Review(author="alice", state="APPROVED")]
    pr.comments = [PRComment(id=1, author="bob", body="lgtm", created_at="2024-01-01")]
    vm.prs = [pr]
    vm._save_pr_cache()

    loaded = vm._load_pr_cache()

    assert len(loaded) == 1
    assert len(loaded[0].reviews) == 1
    assert loaded[0].reviews[0].author == "alice"
    assert loaded[0].reviews[0].state == "APPROVED"
    assert len(loaded[0].comments) == 1
    assert loaded[0].comments[0].id == 1
    assert loaded[0].comments[0].author == "bob"
    assert loaded[0].comments[0].body == "lgtm"
    assert loaded[0].comments[0].created_at == "2024-01-01"
    vm.deleteLater()


# ── Test 6: check run_id survives the save/load round-trip ───────────────────


def test_check_run_id_round_trips(store, qtbot):
    """run_id must survive cache so Re-try CIs works after a cold start."""
    vm = _make_vm(store)
    pr = _make_pr(
        number=5,
        checks=[
            CICheck(
                name="build",
                status="completed",
                conclusion="failure",
                check_suite_id="suite99",
                run_id="26702825172",
            )
        ],
    )
    vm.prs = [pr]
    vm._save_pr_cache()

    loaded = vm._load_pr_cache()

    assert len(loaded) == 1
    assert len(loaded[0].checks) == 1
    c = loaded[0].checks[0]
    assert c.run_id == "26702825172"
    assert c.check_suite_id == "suite99"
    vm.deleteLater()


# ── Test 7: head_sha survives the save/load round-trip ────────────────────────


def test_head_sha_round_trips(store, qtbot):
    vm = _make_vm(store)
    pr = _make_pr(number=8)
    pr.head_sha = "abc123def456"
    vm.prs = [pr]
    vm._save_pr_cache()

    loaded = vm._load_pr_cache()

    assert len(loaded) == 1
    assert loaded[0].head_sha == "abc123def456"
    vm.deleteLater()


# ── Test 8: old flat-list cache returns empty without raising ─────────────────


def test_load_old_flat_list_cache_returns_empty(store, qtbot):
    """An old (pre-versioned) cache file must not crash — just start empty."""
    vm = _make_vm(store)
    old_format = [
        {
            "number": 1,
            "title": "PR 1",
            "html_url": "https://github.com/org/repo/pull/1",
            "head_branch": "feat",
            "base_branch": "main",
            "state": "open",
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "owner": "org",
            "repo": "repo",
            "checks": [],
        }
    ]
    vm._pr_cache_path.parent.mkdir(parents=True, exist_ok=True)
    vm._pr_cache_path.write_text(json.dumps(old_format))

    result = vm._load_pr_cache()

    assert result == [], f"Expected empty list for old format; got {result}"
    vm.deleteLater()


# ── Test 9: startup populates prs from cache before first live fetch ──────────


def test_startup_populates_prs_from_cache_before_live_fetch(store, qtbot):
    """VM.prs is non-empty immediately after __init__ when a cache exists."""
    cached_pr = _make_pr(number=99)

    prs_updated_count = []

    def _make_counted_vm():
        """Build a VM, counting prs_updated signals emitted synchronously during init."""
        with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
            svc = MagicMock()
            svc.get_authenticated_user.return_value = "me"
            svc.discover_open_prs.return_value = []
            MockSvc.return_value = svc
            # Patch _load_pr_cache at the class level before instantiation
            with patch.object(
                GitHubViewModel, "_load_pr_cache", return_value=[cached_pr]
            ):
                vm = GitHubViewModel(store=store)
                # Count prs_updated emissions that happened before timers fire
                vm._total_timer.stop()
                vm._quick_timer.stop()
        return vm, svc

    vm, svc = _make_counted_vm()

    # prs must be populated synchronously — no network needed
    assert len(vm.prs) == 1, f"Expected 1 cached PR immediately; got {vm.prs}"
    assert vm.prs[0].number == 99
    # _initial_load_done must be True so the spinner hides immediately
    assert vm._initial_load_done is True

    vm.deleteLater()
