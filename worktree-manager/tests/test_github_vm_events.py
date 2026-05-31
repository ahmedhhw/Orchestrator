import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment
from worktree_manager.github_vm import GitHubViewModel, TokenState


def _make_pr(number=1, head="feat", base="main", checks=None, reviews=None, comments=None):
    return PullRequest(
        number=number, title="My Work", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch=head, base_branch=base, state="open", draft=False, mergeable=True,
        checks=checks or [], reviews=reviews or [], comments=comments or [],
    )


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    return v


def test_ci_failed_event_emitted_when_checks_transition_to_failed(vm, qtbot):
    pr_before = _make_pr(1, checks=[CICheck("build", "in_progress", None)])
    pr_after  = _make_pr(1, checks=[CICheck("build", "completed", "failure")])
    vm._emit_pr_events([pr_before])  # seed baseline

    events = []
    vm.pr_event.connect(lambda key, evt, msg: events.append((key, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "ci_failed" for e in events)
    assert any("My Work" in e[2] for e in events)


def test_ci_passed_event_emitted_when_all_checks_pass(vm, qtbot):
    pr_before = _make_pr(1, checks=[CICheck("build", "in_progress", None)])
    pr_after  = _make_pr(1, checks=[CICheck("build", "completed", "success")])
    vm._emit_pr_events([pr_before])

    events = []
    vm.pr_event.connect(lambda key, evt, msg: events.append((key, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "ci_passed" for e in events)


def test_new_comment_event_emitted_when_comment_count_grows(vm, qtbot):
    pr_before = _make_pr(1, comments=[PRComment(id=1, author="alice", body="hi", created_at="2024-01-01")])
    pr_after  = _make_pr(1, comments=[
        PRComment(id=1, author="alice", body="hi", created_at="2024-01-01"),
        PRComment(id=2, author="bob",   body="yo", created_at="2024-01-02"),
    ])
    vm._emit_pr_events([pr_before])

    events = []
    vm.pr_event.connect(lambda key, evt, msg: events.append((key, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "new_comment" for e in events)
    assert any("bob" in e[2] for e in events)


def test_review_approved_event_emitted(vm, qtbot):
    pr_before = _make_pr(1, reviews=[])
    pr_after  = _make_pr(1, reviews=[Review(author="alice", state="APPROVED")])
    vm._emit_pr_events([pr_before])

    events = []
    vm.pr_event.connect(lambda key, evt, msg: events.append((key, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "review_approved" for e in events)
    assert any("alice" in e[2] for e in events)


def test_review_changes_requested_event_emitted(vm, qtbot):
    pr_before = _make_pr(1, reviews=[])
    pr_after  = _make_pr(1, reviews=[Review(author="bob", state="CHANGES_REQUESTED")])
    vm._emit_pr_events([pr_before])

    events = []
    vm.pr_event.connect(lambda key, evt, msg: events.append((key, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "review_changes_requested" for e in events)


def test_no_events_when_nothing_changed(vm, qtbot):
    pr = _make_pr(1, checks=[CICheck("build", "completed", "success")])
    vm._emit_pr_events([pr])  # seed

    events = []
    vm.pr_event.connect(lambda key, evt, msg: events.append((key, evt, msg)))
    vm._emit_pr_events([pr])  # same state

    assert events == []


def test_new_pr_does_not_emit_events_on_first_seen(vm, qtbot):
    pr = _make_pr(1, checks=[CICheck("build", "completed", "failure")])

    events = []
    vm.pr_event.connect(lambda key, evt, msg: events.append((key, evt, msg)))
    vm._emit_pr_events([pr])  # first sighting

    assert events == []


def test_pr_state_seeded_after_first_emit(vm, qtbot):
    pr = _make_pr(1, checks=[CICheck("build", "completed", "success")])
    vm._emit_pr_events([pr])
    assert pr.pr_key in vm._pr_state


# ── persistence ───────────────────────────────────────────────────────────────

def _make_vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    return v


def test_pr_state_saved_to_disk_after_emit(tmp_path, qtbot):
    import json
    v = _make_vm(tmp_path)
    pr = _make_pr(1, comments=[PRComment(id=7, author="bob", body="hi", created_at="t")])
    v._emit_pr_events([pr])
    state_file = tmp_path / "github_pr_state.json"
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    key = f"{pr.owner}/{pr.repo}/{pr.number}"
    assert key in data
    assert 7 in data[key]["comment_ids"]
    v.deleteLater()


def test_pr_state_loaded_from_disk_on_init(tmp_path, qtbot):
    import json
    # Write a pre-existing state file using composite key format
    state_file = tmp_path / "github_pr_state.json"
    state_file.write_text(json.dumps({
        "myorg/myrepo/1": {
            "ci": "passed",
            "mergeable_state": "clean",
            "comment_ids": [7],
            "review_keys": [],
        }
    }))
    v = _make_vm(tmp_path)
    # Comment id 7 should already be in state — no new_comment event
    events = []
    v.pr_event.connect(lambda k, t, m: events.append(t))
    v._emit_pr_events([_make_pr(1, comments=[PRComment(id=7, author="bob", body="hi", created_at="t")])])
    assert "new_comment" not in events
    v.deleteLater()


def test_new_vm_does_not_re_notify_already_seen_comment(tmp_path, qtbot):
    # Simulate app restart: first VM sees comment, second VM should not re-notify
    v1 = _make_vm(tmp_path)
    v1._emit_pr_events([_make_pr(1, comments=[PRComment(id=42, author="al", body="x", created_at="t")])])
    v1.deleteLater()

    v2 = _make_vm(tmp_path)
    events = []
    v2.pr_event.connect(lambda k, t, m: events.append(t))
    # Second VM seeds from disk — comment 42 already known, then sees same comment
    v2._emit_pr_events([_make_pr(1, comments=[PRComment(id=42, author="al", body="x", created_at="t")])])
    assert "new_comment" not in events
    v2.deleteLater()


def test_closed_pr_state_pruned_on_save(tmp_path, qtbot):
    import json
    v = _make_vm(tmp_path)
    pr1 = _make_pr(1)
    pr2 = _make_pr(2)
    v._emit_pr_events([pr1, pr2])
    # PR 2 is closed — only PR 1 remains known
    v._known_prs = [(pr1.owner, pr1.repo, pr1.number)]
    v._emit_pr_events([pr1])
    data = json.loads((tmp_path / "github_pr_state.json").read_text())
    assert f"{pr1.owner}/{pr1.repo}/1" in data
    assert f"{pr2.owner}/{pr2.repo}/2" not in data
    v.deleteLater()


def test_sets_survive_json_roundtrip(tmp_path, qtbot):
    v = _make_vm(tmp_path)
    pr = _make_pr(1,
                  comments=[PRComment(id=5, author="a", body="", created_at="t")],
                  reviews=[Review(author="bob", state="APPROVED")])
    v._emit_pr_events([pr])
    v2 = _make_vm(tmp_path)
    assert 5 in v2._pr_state[pr.pr_key]["comment_ids"]
    assert ("bob", "APPROVED") in v2._pr_state[pr.pr_key]["review_keys"]
    v.deleteLater()
    v2.deleteLater()
