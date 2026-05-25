from unittest.mock import MagicMock, patch

from worktree_manager.cli import App


def _make_app(qtbot):
    with (
        patch("worktree_manager.cli.ConfigStore") as MockStore,
        patch("worktree_manager.cli.GitService"),
    ):
        MockStore.return_value.get_repo.return_value = None
        app = App(repo_path=None)
        qtbot.addWidget(app)
    return app


def test_show_cleanup_creates_wizard_dialog(qtbot):
    app = _make_app(qtbot)
    vm = MagicMock()
    vm.all_cleanup_candidates.return_value = []
    with (
        patch("worktree_manager.cli.CleanupWizard") as MockWiz,
        patch("worktree_manager.cli.threading.Thread") as MockThread,
    ):
        MockThread.return_value.start = MagicMock()
        app._show_cleanup(vm)
    MockWiz.assert_called_once()
    kwargs = MockWiz.call_args.kwargs
    assert kwargs.get("candidates") is None  # deferred load
    assert callable(kwargs.get("on_delete_selected"))


def test_show_cleanup_spawns_background_thread(qtbot):
    app = _make_app(qtbot)
    vm = MagicMock()
    with (
        patch("worktree_manager.cli.CleanupWizard"),
        patch("worktree_manager.cli.threading.Thread") as MockThread,
    ):
        thread_instance = MagicMock()
        MockThread.return_value = thread_instance
        app._show_cleanup(vm)
    MockThread.assert_called_once()
    assert MockThread.call_args.kwargs.get("daemon") is True
    thread_instance.start.assert_called_once()


def test_cleanup_delete_callback_invokes_vm(qtbot):
    app = _make_app(qtbot)
    vm = MagicMock()
    with (
        patch("worktree_manager.cli.CleanupWizard") as MockWiz,
        patch("worktree_manager.cli.threading.Thread"),
    ):
        app._show_cleanup(vm)
        on_delete = MockWiz.call_args.kwargs["on_delete_selected"]
        candidates = [MagicMock(), MagicMock()]
        on_delete(candidates)
    vm.delete_cleanup_candidates.assert_called_once_with(
        candidates, also_delete_branches=True,
    )
