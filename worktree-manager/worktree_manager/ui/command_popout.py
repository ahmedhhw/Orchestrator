from PySide6.QtWidgets import QDialog, QVBoxLayout

from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_pane import CommandPane


class CommandPopout(QDialog):
    def __init__(self, parent, handle: RunHandle, on_stop, on_restart, on_remove, on_send=None):
        super().__init__(parent)
        wt_name = handle.worktree_path.split("/")[-1]
        self.setWindowTitle(
            f"{handle.cmd_name} · {handle.repo_name} : {wt_name}"
        )
        self.resize(900, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._pane = CommandPane(
            parent=self, handle=handle,
            on_maximize=lambda p: None,
            on_stop=on_stop, on_restart=on_restart, on_remove=on_remove,
            show_popout_btn=False,
            on_send=on_send,
        )
        layout.addWidget(self._pane)

    def append_line(self, line: str) -> None:
        self._pane.append_line(line)

    def set_status(self, status: RunStatus) -> None:
        self._pane.set_status(status)

    def clear_output(self) -> None:
        self._pane.clear_output()
