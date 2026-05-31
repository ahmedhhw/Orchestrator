import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from worktree_manager.github_models import PullRequest, CICheck, PRComment
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, comments=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/o/r/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        checks=[], reviews=[], comments=comments or [],
    )


def _make_comment(cid, author="alice"):
    return PRComment(id=cid, author=author, body="hi", created_at="2024-01-01")


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
    return v


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    return p


def test_unread_count_zero_initially(vm):
    assert vm.unread_comment_count(1) == 0


def test_unread_count_increases_on_new_comments(vm):
    old_pr = _make_pr(1, comments=[_make_comment(1)])
    new_pr = _make_pr(1, comments=[_make_comment(1), _make_comment(2)])
    vm._pr_snapshots = {1: old_pr}
    vm._seen_comment_ids = {1}
    vm._emit_pr_events([new_pr])
    assert vm.unread_comment_count(1) == 1


def test_mark_pr_comments_seen_clears_unread(vm):
    vm._unseen_comment_ids_by_pr = {1: {10, 11}}
    vm.mark_pr_comments_seen(1)
    assert vm.unread_comment_count(1) == 0


def _pr_list_label_texts(panel) -> list[str]:
    from PySide6.QtWidgets import QLabel
    texts = []
    for i in range(panel._pr_list.count()):
        item = panel._pr_list.item(i)
        widget = panel._pr_list.itemWidget(item)
        label = widget.findChild(QLabel) if widget else None
        texts.append(label.text() if label else "")
    return texts


def test_list_row_shows_badge_for_unread_comments(vm, panel, qtbot):
    pr = _make_pr(1, comments=[_make_comment(1), _make_comment(2)])
    vm._unseen_comment_ids_by_pr = {1: {2}}
    vm.prs = [pr]
    vm.prs_updated.emit()

    items = _pr_list_label_texts(panel)
    assert any("🔴" in text and "new" in text for text in items)


def test_list_row_no_badge_when_no_unread(vm, panel, qtbot):
    pr = _make_pr(1, comments=[_make_comment(1)])
    vm._unseen_comment_ids_by_pr = {}
    vm.prs = [pr]
    vm.prs_updated.emit()

    items = _pr_list_label_texts(panel)
    assert not any("🔴" in text for text in items)


def test_opening_detail_clears_badge(vm, panel, qtbot):
    pr = _make_pr(1, comments=[_make_comment(1)])
    vm._unseen_comment_ids_by_pr = {1: {1}}
    vm.selected_pr = pr
    vm.pr_detail_updated.emit()
    assert vm.unread_comment_count(1) == 0
