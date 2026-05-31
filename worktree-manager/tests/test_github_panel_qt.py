import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel, TokenState
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, head="feat", base="main", checks=None, reviews=None, comments=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="", html_url=f"http://x/{number}",
        head_branch=head, base_branch=base, state="open", draft=False, mergeable=True,
        checks=checks or [], reviews=reviews or [], comments=comments or [],
    )


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    with patch("worktree_manager.github_vm.GitHubService"), \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        v = GitHubViewModel(store=store, repo_path="/tmp/repo")
    return v


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    return p


# ── token missing state ────────────────────────────────────────────────────────


def test_token_missing_shows_token_setup(panel, qtbot):
    assert panel._token_input is not None
    assert panel._save_token_btn is not None


def test_token_missing_hides_header_controls(panel, qtbot):
    assert not panel._header_controls_widget.isVisible()


def test_save_token_button_calls_vm(panel, vm, qtbot):
    panel._token_input.setText("ghp_abc")
    with patch.object(vm, "save_token") as mock_save, \
         patch.object(vm, "refresh_prs"):
        panel._save_token_btn.click()
    mock_save.assert_called_once_with("ghp_abc")


# ── tab layout ─────────────────────────────────────────────────────────────────


def test_panel_has_two_tabs(panel, qtbot):
    assert panel._tabs.count() == 2


def test_tabs_visible_when_token_configured(vm, qtbot, tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "configured.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"), \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        configured_vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
    p = GitHubPanel(vm=configured_vm)
    qtbot.addWidget(p)
    p.show()
    assert p._tabs.isVisible()
    assert not p._token_setup_widget.isVisible()


# ── My PRs tab — list ─────────────────────────────────────────────────────────


def test_prs_updated_signal_refreshes_list(panel, vm, qtbot):
    vm.prs = [_make_pr(10), _make_pr(11)]
    vm.prs_updated.emit()
    assert panel._pr_list.count() == 2


def test_pr_row_shows_number_and_title(panel, vm, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    item_text = panel._pr_list.item(0).text()
    assert "#42" in item_text
    assert "PR 42" in item_text


def test_current_branch_pr_shows_label(panel, vm, qtbot, monkeypatch):
    import subprocess
    monkeypatch.setattr(
        "worktree_manager.ui.github_panel.subprocess.run",
        lambda *a, **kw: MagicMock(returncode=0, stdout="feat\n"),
    )
    vm.prs = [_make_pr(1, head="feat")]
    vm.prs_updated.emit()
    item_text = panel._pr_list.item(0).text()
    assert "current branch" in item_text


# ── My PRs tab — detail ────────────────────────────────────────────────────────


def test_clicking_pr_row_calls_vm_select(panel, vm, qtbot):
    vm.prs = [_make_pr(7)]
    vm.prs_updated.emit()
    with patch.object(vm, "select_pr") as mock_select:
        panel._pr_list.item(0).setSelected(True)
        panel._on_pr_row_activated(panel._pr_list.item(0))
    mock_select.assert_called_once_with(7)


def test_detail_view_shows_back_button(panel, vm, qtbot):
    vm.selected_pr = _make_pr(5, checks=[CICheck("build", "completed", "success")])
    vm.pr_detail_updated.emit()
    assert panel._my_prs_stack.currentWidget() is panel._pr_detail_widget


def test_detail_view_shows_ci_checks(panel, vm, qtbot):
    vm.selected_pr = _make_pr(5, checks=[
        CICheck("build", "completed", "success"),
        CICheck("lint", "completed", "failure"),
    ])
    vm.pr_detail_updated.emit()
    assert panel._checks_list.count() == 2


def test_back_button_returns_to_list(panel, vm, qtbot):
    vm.selected_pr = _make_pr(5)
    vm.pr_detail_updated.emit()
    panel._back_btn.click()
    assert vm.selected_pr is None
    assert panel._my_prs_stack.currentWidget() is panel._pr_list_widget


# ── poll toggle ───────────────────────────────────────────────────────────────


def test_poll_toggle_shows_pause_when_active(panel, vm, qtbot, tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "tog.json")
    store.save_github_token("ghp_x")
    with patch("worktree_manager.github_vm.GitHubService"), \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        v = GitHubViewModel(store=store, repo_path="/tmp/repo")
    p = GitHubPanel(vm=v)
    qtbot.addWidget(p)
    p.show()
    assert "30s" in p._poll_btn.text()
    p._poll_btn.click()
    assert v.polling_active is False
    assert "⏸" in p._poll_btn.text()
    p._poll_btn.click()
    assert v.polling_active is True
    assert "↻" in p._poll_btn.text()


# ── token rotation inline dropdown ────────────────────────────────────────────


def test_token_btn_shows_inline_form_when_clicked(panel, vm, qtbot, tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "rot.json")
    store.save_github_token("ghp_x")
    with patch("worktree_manager.github_vm.GitHubService"), \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        v = GitHubViewModel(store=store, repo_path="/tmp/repo")
    p = GitHubPanel(vm=v)
    qtbot.addWidget(p)
    p.show()
    p._token_rotate_btn.click()
    assert p._token_rotate_widget.isVisible()


# ── Open PR tab ───────────────────────────────────────────────────────────────


def test_open_pr_tab_has_title_field(panel, qtbot):
    panel._tabs.setCurrentIndex(1)
    assert panel._pr_title_edit is not None


def test_open_pr_tab_has_base_branch_dropdown(panel, qtbot):
    panel._tabs.setCurrentIndex(1)
    assert panel._base_branch_combo is not None


def test_open_pr_tab_has_draft_checkbox(panel, qtbot):
    panel._tabs.setCurrentIndex(1)
    assert panel._draft_checkbox is not None
