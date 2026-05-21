import customtkinter as ctk
from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_pane import CommandPane


class CommandCenterPanel(ctk.CTkFrame):
    def __init__(self, master, vm, on_close):
        super().__init__(master)
        self._vm = vm
        self._on_close = on_close
        self._panes: dict[str, CommandPane] = {}
        self._popouts: dict[str, object] = {}  # run_id -> CommandPopout
        self._maximized_id: str | None = None
        self._build()
        self._wire_vm()
        self._restore_existing_runs()

    def _build(self):
        toolbar = ctk.CTkFrame(self, corner_radius=0)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(
            toolbar,
            text="Command Center",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(toolbar, text="×", width=32, command=self.trigger_close).pack(side="right", padx=2)
        ctk.CTkButton(toolbar, text="+ Launch", command=self._open_launch_dialog).pack(side="right", padx=2)
        ctk.CTkButton(toolbar, text="+ Add Command", command=self._open_add_command_dialog).pack(side="right", padx=2)
        ctk.CTkButton(toolbar, text="⚙ Commands", command=self._open_manage_commands_dialog).pack(side="right", padx=2)

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=8, pady=4)

        self._empty_label = ctk.CTkLabel(
            self._scroll,
            text="No commands running.\nClick [+ Launch] to start one.",
            text_color="gray",
            justify="center",
        )
        self._empty_label.pack(pady=40)

    def _wire_vm(self):
        self._vm.on_run_added = self._on_run_added
        self._vm.on_output = self._on_output
        self._vm.on_status_changed = self._on_status_changed
        self._vm.on_run_id_changed = self._on_run_id_changed

    def _restore_existing_runs(self):
        for handle in self._vm.all_runs():
            self.add_pane(handle)
            for line in handle.output_lines:
                self._panes[handle.run_id].append_line(line)
            self._panes[handle.run_id].set_status(handle.status)

    def _on_run_added(self, handle: RunHandle) -> None:
        self.after(0, lambda: self.add_pane(handle))

    def _on_output(self, run_id: str, line: str) -> None:
        self.after(0, lambda: self.route_output(run_id, line))

    def _on_status_changed(self, run_id: str, status: RunStatus) -> None:
        self.after(0, lambda: self.route_status(run_id, status))

    def add_pane(self, handle: RunHandle) -> None:
        if handle.run_id in self._panes:
            return
        pane = CommandPane(
            self._scroll,
            handle=handle,
            on_maximize=lambda p: self._open_popout(p._handle.run_id),
            on_stop=lambda: self._vm.stop(handle.run_id),
            on_restart=lambda: self._do_restart(handle.run_id),
            on_remove=lambda: self.remove_pane(handle.run_id),
        )
        pane.pack(fill="x", pady=4)
        self._panes[handle.run_id] = pane
        self._empty_label.pack_forget()

    def remove_pane(self, run_id: str) -> None:
        self._vm.stop(run_id)
        popout = self._popouts.pop(run_id, None)
        if popout and popout.winfo_exists():
            popout.destroy()
        pane = self._panes.pop(run_id, None)
        if pane:
            pane.destroy()
        if self._maximized_id == run_id:
            self._maximized_id = None
        if not self._panes:
            self._empty_label.pack(pady=40)

    def _on_run_id_changed(self, old_id: str, new_id: str) -> None:
        pane = self._panes.pop(old_id, None)
        if pane:
            self._panes[new_id] = pane
        popout = self._popouts.pop(old_id, None)
        if popout:
            self._popouts[new_id] = popout

    def _do_restart(self, run_id: str) -> None:
        pane = self._panes.get(run_id)
        if pane:
            pane.clear_output()
        popout = self._popouts.get(run_id)
        if popout and popout.winfo_exists():
            popout.clear_output()
        self._vm.restart(run_id)

    def route_output(self, run_id: str, line: str) -> None:
        pane = self._panes.get(run_id)
        if pane:
            pane.append_line(line)
        popout = self._popouts.get(run_id)
        if popout and popout.winfo_exists():
            popout.append_line(line)

    def route_status(self, run_id: str, status: RunStatus) -> None:
        pane = self._panes.get(run_id)
        if pane:
            pane.set_status(status)
        popout = self._popouts.get(run_id)
        if popout and popout.winfo_exists():
            popout.set_status(status)

    def _open_popout(self, run_id: str) -> None:
        from worktree_manager.ui.command_popout import CommandPopout
        existing = self._popouts.get(run_id)
        if existing and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        handle = self._vm.get_run(run_id)
        if not handle:
            return
        popout = CommandPopout(
            self,
            handle=handle,
            on_stop=lambda: self._vm.stop(run_id),
            on_restart=lambda: self._do_restart(run_id),
            on_remove=lambda: self.remove_pane(run_id),
        )
        for line in handle.output_lines:
            popout.append_line(line)
        popout.set_status(handle.status)
        self._popouts[run_id] = popout

    def trigger_close(self) -> None:
        self._on_close()

    def pane_count(self) -> int:
        return len(self._panes)

    def get_pane(self, run_id: str) -> CommandPane | None:
        return self._panes.get(run_id)

    def maximize_pane(self, run_id: str) -> None:
        self._maximized_id = run_id
        for rid, pane in self._panes.items():
            if rid != run_id:
                pane.pack_forget()
            else:
                pane.pack(fill="both", expand=True, pady=4)

    def restore_tiled(self) -> None:
        self._maximized_id = None
        for pane in self._panes.values():
            pane.pack(fill="x", expand=False, pady=4)

    def is_maximized(self, run_id: str) -> bool:
        return self._maximized_id == run_id

    def is_visible(self, run_id: str) -> bool:
        pane = self._panes.get(run_id)
        if pane is None:
            return False
        return pane.winfo_ismapped()

    def empty_state_visible(self) -> bool:
        return self._empty_label.winfo_ismapped()

    def _open_add_command_dialog(self) -> None:
        from worktree_manager.ui.add_command_dialog import AddCommandDialog
        AddCommandDialog(self, vm=self._vm)

    def _open_launch_dialog(self) -> None:
        from worktree_manager.ui.launch_dialog import LaunchDialog
        LaunchDialog(self, vm=self._vm)

    def _open_manage_commands_dialog(self) -> None:
        from worktree_manager.ui.manage_commands_dialog import ManageCommandsDialog
        ManageCommandsDialog(self, vm=self._vm)
