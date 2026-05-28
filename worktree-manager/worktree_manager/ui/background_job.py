import inspect
import threading

from PySide6.QtCore import QObject, Signal


class BackgroundJob(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(Exception)

    def start(self, fn, *args, **kwargs):
        accepts_progress = "on_progress" in inspect.signature(fn).parameters

        def _run():
            try:
                if accepts_progress:
                    kwargs["on_progress"] = lambda cur, tot, lbl: self.progress.emit(cur, tot, lbl)
                result = fn(*args, **kwargs)
                self.finished.emit(result)
            except Exception as exc:
                self.failed.emit(exc)

        threading.Thread(target=_run, daemon=True).start()
