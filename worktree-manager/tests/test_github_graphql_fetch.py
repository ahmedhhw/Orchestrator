"""TDD tests for Iteration 4: GraphQL poll consolidation.

Tests are written in strict red/green/refactor order — each test was
written to fail first, then the implementation was added to make it pass.
"""
import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_service import GitHubService, GRAPHQL_QUERY, _pr_from_graphql_node
from worktree_manager.github_models import CICheck, PRComment, PullRequest, Review


TOKEN = "ghp_test"


@pytest.fixture
def service():
    return GitHubService(token=TOKEN)


# ---------------------------------------------------------------------------
# Test 1: GraphQL query string contains the required fields
# ---------------------------------------------------------------------------

def test_graphql_query_contains_required_fields():
    """The GRAPHQL_QUERY constant must request all fields that the mapper needs."""
    q = GRAPHQL_QUERY
    # PR meta
    assert "number" in q
    assert "title" in q
    assert "headRefOid" in q
    assert "headRefName" in q
    assert "baseRefName" in q
    assert "isDraft" in q
    assert "url" in q
    assert "state" in q
    # Mergeability
    assert "mergeable" in q
    assert "mergeStateStatus" in q
    # Rollup contexts
    assert "statusCheckRollup" in q
    assert "__typename" in q
    assert "CheckRun" in q
    assert "StatusContext" in q
    assert "workflowRun" in q
    assert "databaseId" in q
    # Reviews and comments
    assert "reviews" in q
    assert "comments" in q
    # Rate limit
    assert "rateLimit" in q
    assert "remaining" in q


# ---------------------------------------------------------------------------
# Helpers for building GraphQL node dicts (used in tests 2-5)
# ---------------------------------------------------------------------------

def _make_graphql_node(
    number=1,
    title="Test PR",
    url="https://github.com/myorg/myrepo/pull/1",
    state="OPEN",
    is_draft=False,
    head_ref_name="feat",
    base_ref_name="main",
    head_ref_oid="abc123",
    mergeable="MERGEABLE",
    merge_state_status="CLEAN",
    name_with_owner="myorg/myrepo",
    check_contexts=None,
    review_nodes=None,
    comment_nodes=None,
):
    """Build a minimal GraphQL PR node dict."""
    return {
        "number": number,
        "title": title,
        "body": "desc",
        "url": url,
        "state": state,
        "isDraft": is_draft,
        "headRefName": head_ref_name,
        "baseRefName": base_ref_name,
        "headRefOid": head_ref_oid,
        "mergeable": mergeable,
        "mergeStateStatus": merge_state_status,
        "repository": {"nameWithOwner": name_with_owner},
        "reviews": {"nodes": review_nodes or []},
        "comments": {"nodes": comment_nodes or []},
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "statusCheckRollup": {
                            "contexts": {
                                "nodes": check_contexts or []
                            }
                        }
                    }
                }
            ]
        },
    }


def _checkrun_node(
    name="build",
    status="COMPLETED",
    conclusion="FAILURE",
    suite_db_id=99,
    workflow_run_db_id=12345,
):
    node = {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "checkSuite": {
            "databaseId": suite_db_id,
            "workflowRun": {"databaseId": workflow_run_db_id},
        },
    }
    return node


def _status_context_node(context="lint", state="SUCCESS"):
    return {
        "__typename": "StatusContext",
        "context": context,
        "state": state,
    }


# ---------------------------------------------------------------------------
# Test 2: _pr_from_graphql_node maps CheckRun → CICheck
# ---------------------------------------------------------------------------

def test_pr_from_graphql_node_maps_checkrun_to_cicheck():
    """CheckRun status/conclusion must be lowercased; run_id from workflowRun.databaseId."""
    node = _make_graphql_node(
        check_contexts=[
            _checkrun_node(
                name="build",
                status="COMPLETED",
                conclusion="FAILURE",
                suite_db_id=99,
                workflow_run_db_id=26702825172,
            )
        ]
    )
    pr = _pr_from_graphql_node(node)

    assert len(pr.checks) == 1
    check = pr.checks[0]
    assert check.name == "build"
    assert check.status == "completed"        # must be lowercase
    assert check.conclusion == "failure"      # must be lowercase
    assert check.check_suite_id == "99"       # str(databaseId)
    assert check.run_id == "26702825172"      # str(workflowRun.databaseId)


# ---------------------------------------------------------------------------
# Test 3: _pr_from_graphql_node maps mergeable enum and lowercases mergeStateStatus
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("MERGEABLE", True),
    ("CONFLICTING", False),
    ("UNKNOWN", None),
])
def test_pr_from_graphql_node_maps_mergeable_enum(raw, expected):
    node = _make_graphql_node(mergeable=raw, merge_state_status="CLEAN")
    pr = _pr_from_graphql_node(node)
    assert pr.mergeable is expected


def test_pr_from_graphql_node_lowercases_merge_state_status():
    node = _make_graphql_node(merge_state_status="DIRTY")
    pr = _pr_from_graphql_node(node)
    assert pr.mergeable_state == "dirty"


# ---------------------------------------------------------------------------
# Test 4: _pr_from_graphql_node maps reviews and comments into model objects
# ---------------------------------------------------------------------------

def test_pr_from_graphql_node_maps_reviews_and_comments():
    """Reviews keep state UPPERCASE; comments map databaseId → id and createdAt → created_at."""
    review_nodes = [
        {"author": {"login": "alice"}, "state": "APPROVED"},
        {"author": {"login": "bob"}, "state": "CHANGES_REQUESTED"},
    ]
    comment_nodes = [
        {"databaseId": 42, "author": {"login": "carol"}, "body": "LGTM", "createdAt": "2024-01-01T00:00:00Z"},
    ]
    node = _make_graphql_node(review_nodes=review_nodes, comment_nodes=comment_nodes)
    pr = _pr_from_graphql_node(node)

    assert len(pr.reviews) == 2
    assert pr.reviews[0].author == "alice"
    assert pr.reviews[0].state == "APPROVED"       # must stay UPPERCASE
    assert pr.reviews[1].author == "bob"
    assert pr.reviews[1].state == "CHANGES_REQUESTED"

    assert len(pr.comments) == 1
    assert pr.comments[0].id == 42
    assert pr.comments[0].author == "carol"
    assert pr.comments[0].body == "LGTM"
    assert pr.comments[0].created_at == "2024-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Test 5: _pr_from_graphql_node handles StatusContext rollup nodes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state,expected_conclusion", [
    ("SUCCESS", "success"),
    ("FAILURE", "failure"),
    ("ERROR", "failure"),
    ("PENDING", None),
    ("EXPECTED", None),
])
def test_pr_from_graphql_node_maps_status_context(state, expected_conclusion):
    """StatusContext nodes: status fixed as 'completed', conclusion mapped from state enum."""
    node = _make_graphql_node(
        check_contexts=[_status_context_node(context="lint", state=state)]
    )
    pr = _pr_from_graphql_node(node)

    assert len(pr.checks) == 1
    check = pr.checks[0]
    assert check.name == "lint"
    assert check.status == "completed"
    assert check.conclusion == expected_conclusion
    assert check.run_id is None
    assert check.check_suite_id is None


# ---------------------------------------------------------------------------
# Test 6: fetch_all_open_prs issues exactly one POST to the GraphQL endpoint
# ---------------------------------------------------------------------------

def _graphql_response(nodes):
    """Build a minimal GraphQL API response dict."""
    return {
        "data": {
            "viewer": {"login": "me"},
            "search": {"nodes": nodes},
            "rateLimit": {"cost": 1, "remaining": 4999},
        }
    }


def test_fetch_all_open_prs_issues_one_post(service):
    """One POST to https://api.github.com/graphql, returns list of PullRequest."""
    node = _make_graphql_node(number=7, title="My PR")
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = _graphql_response([node])
    fake_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=fake_resp) as mock_post:
        prs = service.fetch_all_open_prs()

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.github.com/graphql"
    assert len(prs) == 1
    assert prs[0].number == 7
    assert prs[0].title == "My PR"


def test_fetch_all_open_prs_skips_null_nodes(service):
    """Null entries in nodes list (non-PR types from fragment) must be skipped."""
    node = _make_graphql_node(number=3)
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = _graphql_response([None, node, None])
    fake_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=fake_resp):
        prs = service.fetch_all_open_prs()

    assert len(prs) == 1
    assert prs[0].number == 3


def test_fetch_all_open_prs_raises_permission_error_on_401(service):
    """HTTP 401 → PermissionError."""
    fake_resp = MagicMock(status_code=401)
    fake_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=fake_resp):
        with pytest.raises(PermissionError):
            service.fetch_all_open_prs()


def test_fetch_all_open_prs_raises_runtime_on_graphql_errors(service):
    """GraphQL errors key in response body → RuntimeError with first error message."""
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = {
        "errors": [{"message": "Field 'foo' doesn't exist", "type": "FIELD_ERROR"}]
    }
    fake_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=fake_resp):
        with pytest.raises(RuntimeError, match="Field 'foo' doesn't exist"):
            service.fetch_all_open_prs()


# ---------------------------------------------------------------------------
# Test 7: VM _run_total_fetch uses fetch_all_open_prs (not discover_open_prs)
# ---------------------------------------------------------------------------

def _make_pr_for_vm(number=1):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
    )


def _vm_with_graphql(svc, store):
    """Create a VM with fetch_all_open_prs stubbed; timers stopped; startup fetch drained."""
    from PySide6.QtWidgets import QApplication
    import time

    svc.fetch_all_open_prs.return_value = []
    # discover_open_prs should NOT be called; set it to blow up if it is
    svc.discover_open_prs.side_effect = AssertionError("discover_open_prs must not be called")

    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = svc
        from worktree_manager.github_vm import GitHubViewModel
        vm = GitHubViewModel(store=store)
        vm._total_timer.stop()
        vm._quick_timer.stop()

    # Drain the startup total_fetch thread
    deadline = time.monotonic() + 3.0
    while (not vm._initial_load_done or vm._total_fetch_running) and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    QApplication.processEvents()

    # Reset to clean state
    vm.prs = []
    vm._pr_state = {}
    svc.fetch_all_open_prs.reset_mock()
    svc.fetch_all_open_prs.return_value = []
    return vm


def test_run_total_fetch_calls_fetch_all_open_prs(qtbot):
    """_run_total_fetch must call fetch_all_open_prs — not discover_open_prs."""
    from worktree_manager.config_store import ConfigStore
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmpdir:
        store = ConfigStore(path=pathlib.Path(tmpdir) / "config.json")
        store.save_github_token("ghp_test")

        svc = MagicMock()
        vm = _vm_with_graphql(svc, store)

        pr = _make_pr_for_vm(42)
        svc.fetch_all_open_prs.return_value = [pr]

        # Run the total fetch synchronously (same technique as test_github_vm.py)
        from PySide6.QtWidgets import QApplication
        vm._run_total_fetch()
        QApplication.processEvents()

        svc.fetch_all_open_prs.assert_called_once()
        assert any(p.number == 42 for p in vm.prs)
        vm.deleteLater()


def test_run_quick_fetch_calls_fetch_all_open_prs(qtbot):
    """_run_quick_fetch must also use fetch_all_open_prs directly."""
    from worktree_manager.config_store import ConfigStore
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmpdir:
        store = ConfigStore(path=pathlib.Path(tmpdir) / "config.json")
        store.save_github_token("ghp_test")

        svc = MagicMock()
        vm = _vm_with_graphql(svc, store)

        pr = _make_pr_for_vm(5)
        svc.fetch_all_open_prs.return_value = [pr]

        from PySide6.QtWidgets import QApplication
        vm._run_quick_fetch()
        QApplication.processEvents()

        svc.fetch_all_open_prs.assert_called_once()
        assert any(p.number == 5 for p in vm.prs)
        vm.deleteLater()
