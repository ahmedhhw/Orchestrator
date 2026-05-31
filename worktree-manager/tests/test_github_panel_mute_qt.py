import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.ui.github_panel import GitHubPanel
from worktree_manager.github_vm import GitHubViewModel


@pytest.fixture
def configured_panel(tmp_path, qtbot):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc, \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        MockSvc.from_remote_url.return_value = MagicMock()
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    return p, vm._store


def test_mute_button_exists_in_header(configured_panel, qtbot):
    panel, store = configured_panel
    assert hasattr(panel, "_notif_btn")


def test_mute_button_initial_state_is_on(configured_panel, qtbot):
    panel, store = configured_panel
    assert "🔔" in panel._notif_btn.text() or panel._notif_btn.isChecked()


def test_mute_button_toggle_saves_pref(configured_panel, qtbot):
    panel, store = configured_panel
    initial = store.get_ui_pref("github_notifications_enabled", True)
    panel._notif_btn.click()
    after = store.get_ui_pref("github_notifications_enabled", True)
    assert after != initial


def test_mute_button_text_updates_on_toggle(configured_panel, qtbot):
    panel, store = configured_panel
    panel._notif_btn.setChecked(True)
    panel._update_notif_btn()
    assert "🔔" in panel._notif_btn.text()
    panel._notif_btn.setChecked(False)
    panel._update_notif_btn()
    assert "🔕" in panel._notif_btn.text()
