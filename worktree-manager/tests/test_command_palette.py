import pytest
from unittest.mock import MagicMock
from worktree_manager.models import SavedCommand, WorktreeModel


@pytest.fixture(scope="module", autouse=True)
def require_display():
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
    except Exception:
        pytest.skip("no display available")


@pytest.fixture
def root():
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def vm():
    m = MagicMock()
    m.all_repos.return_value = {
        "/repos/proj": MagicMock(repo_path="/repos/proj"),
        "/repos/api":  MagicMock(repo_path="/repos/api"),
    }

    def _saved(repo_path):
        if repo_path == "/repos/proj":
            return [SavedCommand(name="frontend", command="npm run dev"),
                    SavedCommand(name="backend",  command="python manage.py runserver")]
        return [SavedCommand(name="server", command="go run ./cmd/server")]
    m.saved_commands.side_effect = _saved

    def _wts(repo_path):
        return [WorktreeModel(path=f"{repo_path}-wt/main", branch="main",
                              is_main=True, last_commit_ts=0, is_merged=False, is_stale=False)]
    m.list_worktrees.side_effect = _wts
    return m


@pytest.fixture
def palette(root, vm):
    from worktree_manager.ui.command_palette import CommandPalette
    return CommandPalette(root, vm=vm)


def test_palette_shows_all_commands_initially(palette):
    assert palette.result_count() == 3


def test_filter_narrows_results(palette):
    palette.set_query("front")
    assert palette.result_count() == 1


def test_filter_is_case_insensitive(palette):
    palette.set_query("FRONT")
    assert palette.result_count() == 1


def test_clear_filter_restores_all_results(palette):
    palette.set_query("front")
    palette.set_query("")
    assert palette.result_count() == 3


def test_enter_launches_selected_result(root, vm):
    from worktree_manager.ui.command_palette import CommandPalette
    p = CommandPalette(root, vm=vm)
    p.set_query("frontend")
    p.trigger_enter()
    vm.launch.assert_called_once()
    kwargs = vm.launch.call_args[1]
    assert kwargs["cmd_name"] == "frontend"
    assert kwargs["command_str"] == "npm run dev"


def test_esc_dismisses_palette(root, vm):
    from worktree_manager.ui.command_palette import CommandPalette
    p = CommandPalette(root, vm=vm)
    p.trigger_esc()
    # After destroy, winfo_exists returns False
    assert not p.winfo_exists()


def test_launch_passes_worktree_from_inline_dropdown(root, vm):
    from worktree_manager.ui.command_palette import CommandPalette
    p = CommandPalette(root, vm=vm)
    p.set_query("server")
    p.trigger_enter()
    kwargs = vm.launch.call_args[1]
    assert kwargs["repo_path"] == "/repos/api"
