import pytest
from unittest.mock import MagicMock


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
    m.all_runs.return_value = []
    m.all_repos.return_value = {"/repos/proj": MagicMock(repo_path="/repos/proj")}
    return m


@pytest.fixture
def panel(root, vm):
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    on_close = MagicMock()
    p = CommandCenterPanel(root, vm=vm, on_close=on_close)
    return p, on_close


def test_panel_registers_vm_callbacks(vm, panel):
    assert vm.on_run_added is not None
    assert vm.on_output is not None
    assert vm.on_status_changed is not None


def test_close_button_calls_on_close(panel):
    p, on_close = panel
    p.trigger_close()
    on_close.assert_called_once()


def test_add_pane_creates_widget(panel):
    from worktree_manager.command_runner import RunHandle, RunStatus
    p, _ = panel
    handle = RunHandle(
        run_id="r1", cmd_name="frontend", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/repos/proj-wt/feat",
        command=["npm", "run", "dev"], status=RunStatus.RUNNING,
    )
    p.add_pane(handle)
    assert p.pane_count() == 1


def test_route_output_appends_to_correct_pane(panel):
    from worktree_manager.command_runner import RunHandle, RunStatus
    p, _ = panel
    handle = RunHandle(
        run_id="r2", cmd_name="backend", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/repos/proj-wt/feat",
        command=["python"], status=RunStatus.RUNNING,
    )
    p.add_pane(handle)
    p.route_output("r2", "hello from backend")
    text = p.get_pane("r2").get_output_text()
    assert "hello from backend" in text


def test_route_status_updates_pane_dot(panel):
    from worktree_manager.command_runner import RunHandle, RunStatus
    p, _ = panel
    handle = RunHandle(
        run_id="r3", cmd_name="server", repo_path="/repos/proj",
        repo_name="proj", worktree_path="/repos/proj-wt/main",
        command=["go", "run"], status=RunStatus.RUNNING,
    )
    p.add_pane(handle)
    p.route_status("r3", RunStatus.STOPPED)
    assert p.get_pane("r3").status_dot_color() == "gray"


def test_maximize_hides_other_panes(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    p = CommandCenterPanel(root, vm=vm, on_close=MagicMock())
    h1 = RunHandle(run_id="m1", cmd_name="a", repo_path="/repos/proj",
                   repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    h2 = RunHandle(run_id="m2", cmd_name="b", repo_path="/repos/proj",
                   repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    p.add_pane(h1)
    p.add_pane(h2)
    root.update_idletasks()
    p.maximize_pane("m1")
    root.update_idletasks()
    assert p.is_maximized("m1")
    assert not p.is_visible("m2")


def test_restore_shows_all_panes(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    p = CommandCenterPanel(root, vm=vm, on_close=MagicMock())
    h1 = RunHandle(run_id="v1", cmd_name="a", repo_path="/repos/proj",
                   repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    h2 = RunHandle(run_id="v2", cmd_name="b", repo_path="/repos/proj",
                   repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    p.add_pane(h1)
    p.add_pane(h2)
    root.update_idletasks()
    p.maximize_pane("v1")
    root.update_idletasks()
    p.restore_tiled()
    root.update_idletasks()
    assert p.is_visible("v1")
    assert p.is_visible("v2")
    assert not p.is_maximized("v1")


def test_empty_state_label_shown_when_no_panes(root, vm):
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    p = CommandCenterPanel(root, vm=vm, on_close=MagicMock())
    root.update_idletasks()
    assert p.empty_state_visible()


def test_remove_pane_destroys_it_and_restores_empty_state(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    p = CommandCenterPanel(root, vm=vm, on_close=MagicMock())
    handle = RunHandle(run_id="del1", cmd_name="x", repo_path="/repos/proj",
                       repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    p.add_pane(handle)
    root.update_idletasks()
    p.remove_pane("del1")
    root.update_idletasks()
    assert p.pane_count() == 0
    assert p.empty_state_visible()


def test_empty_state_hidden_when_pane_added(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    p = CommandCenterPanel(root, vm=vm, on_close=MagicMock())
    handle = RunHandle(run_id="e1", cmd_name="x", repo_path="/repos/proj",
                       repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    p.add_pane(handle)
    root.update_idletasks()
    assert not p.empty_state_visible()


def test_run_id_changed_remaps_pane(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    p = CommandCenterPanel(root, vm=vm, on_close=MagicMock())
    handle = RunHandle(run_id="old", cmd_name="frontend", repo_path="/repos/proj",
                       repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    p.add_pane(handle)
    root.update_idletasks()
    p._on_run_id_changed("old", "new")
    assert p.get_pane("new") is not None
    assert p.get_pane("old") is None


def test_run_id_changed_updates_pane_run_id(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    p = CommandCenterPanel(root, vm=vm, on_close=MagicMock())
    handle = RunHandle(run_id="old2", cmd_name="backend", repo_path="/repos/proj",
                       repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    p.add_pane(handle)
    root.update_idletasks()
    p._on_run_id_changed("old2", "new2")
    assert p.get_pane("new2")._run_id == "new2"


def test_remove_pane_calls_vm_remove_run(root, vm):
    from worktree_manager.command_runner import RunHandle, RunStatus
    from worktree_manager.ui.command_center_panel import CommandCenterPanel
    p = CommandCenterPanel(root, vm=vm, on_close=MagicMock())
    handle = RunHandle(run_id="del2", cmd_name="svc", repo_path="/repos/proj",
                       repo_name="proj", worktree_path="/wt", command=[], status=RunStatus.RUNNING)
    p.add_pane(handle)
    root.update_idletasks()
    p.remove_pane("del2")
    vm.remove_run.assert_called_with("del2")
