"""Tests for BackgroundJob — generic async worker with Qt signals."""
import threading
from unittest.mock import MagicMock

import pytest


def test_background_job_emits_finished_with_return_value(qtbot):
    from worktree_manager.ui.background_job import BackgroundJob

    job = BackgroundJob()
    with qtbot.waitSignal(job.finished, timeout=2000) as blocker:
        job.start(lambda: 42)
    assert blocker.args == [42]


def test_background_job_emits_failed_on_exception(qtbot):
    from worktree_manager.ui.background_job import BackgroundJob

    job = BackgroundJob()
    exc = ValueError("boom")
    with qtbot.waitSignal(job.failed, timeout=2000) as blocker:
        job.start(lambda: (_ for _ in ()).throw(exc))
    assert isinstance(blocker.args[0], ValueError)


def test_background_job_runs_on_non_main_thread(qtbot):
    from worktree_manager.ui.background_job import BackgroundJob

    main_thread = threading.current_thread()
    captured = []

    def fn():
        captured.append(threading.current_thread())
        return None

    job = BackgroundJob()
    with qtbot.waitSignal(job.finished, timeout=2000):
        job.start(fn)

    assert captured[0] is not main_thread


def test_background_job_injects_on_progress_when_accepted(qtbot):
    from worktree_manager.ui.background_job import BackgroundJob

    progress_calls = []

    def fn(on_progress=None):
        on_progress(1, 3, "step-a")
        on_progress(2, 3, "step-b")
        on_progress(3, 3, "step-c")
        return "done"

    job = BackgroundJob()
    job.progress.connect(lambda cur, tot, lbl: progress_calls.append((cur, tot, lbl)))
    with qtbot.waitSignal(job.finished, timeout=2000):
        job.start(fn)

    assert progress_calls == [(1, 3, "step-a"), (2, 3, "step-b"), (3, 3, "step-c")]


def test_background_job_does_not_inject_on_progress_when_not_accepted(qtbot):
    from worktree_manager.ui.background_job import BackgroundJob

    def fn():
        return "no-progress"

    job = BackgroundJob()
    with qtbot.waitSignal(job.finished, timeout=2000) as blocker:
        job.start(fn)

    assert blocker.args == ["no-progress"]
