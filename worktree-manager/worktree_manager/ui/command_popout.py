import customtkinter as ctk
from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_pane import CommandPane


class CommandPopout(ctk.CTkToplevel):
    def __init__(self, master, handle: RunHandle, on_stop, on_restart, on_remove):
        super().__init__(master)
        wt_name = handle.worktree_path.split("/")[-1]
        self.title(f"{handle.cmd_name} · {handle.repo_name} : {wt_name}")
        self.geometry("900x600")
        self._pane = CommandPane(
            self,
            handle=handle,
            on_maximize=lambda p: None,
            on_stop=on_stop,
            on_restart=on_restart,
            on_remove=on_remove,
            show_popout_btn=False,
        )
        self._pane.pack(fill="both", expand=True, padx=8, pady=8)

    def append_line(self, line: str) -> None:
        self._pane.append_line(line)

    def set_status(self, status: RunStatus) -> None:
        self._pane.set_status(status)

    def clear_output(self) -> None:
        self._pane.clear_output()
