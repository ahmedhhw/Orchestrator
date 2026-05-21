from pathlib import Path
import customtkinter as ctk
from worktree_manager.models import SavedCommand, WorktreeModel


class _ResultRow(ctk.CTkFrame):
    def __init__(self, master, cmd: SavedCommand, repo_path: str, worktrees: list[WorktreeModel]):
        super().__init__(master, corner_radius=4)
        self._cmd = cmd
        self._repo_path = repo_path
        self._worktrees = worktrees
        wt_labels = [f"{wt.branch}  ({wt.path})" for wt in worktrees]
        ctk.CTkLabel(
            self, text=f"{cmd.name}  ·  {Path(repo_path).name}", anchor="w"
        ).pack(side="left", padx=8, fill="x", expand=True)
        self._wt_var = ctk.StringVar(value=wt_labels[0] if wt_labels else "")
        if wt_labels:
            ctk.CTkOptionMenu(
                self, variable=self._wt_var, values=wt_labels, width=180
            ).pack(side="right", padx=4, pady=2)

    def selected_worktree_path(self) -> str:
        label = self._wt_var.get()
        for wt in self._worktrees:
            if wt.path in label:
                return wt.path
        return label

    def cmd(self) -> SavedCommand:
        return self._cmd

    def repo_path(self) -> str:
        return self._repo_path


class CommandPalette(ctk.CTkToplevel):
    def __init__(self, master, vm):
        super().__init__(master)
        self.title("")
        self.resizable(False, False)
        self._vm = vm
        self._all_results: list[tuple[SavedCommand, str, list[WorktreeModel]]] = []
        self._rows: list[_ResultRow] = []
        self._selected_idx = 0
        self._build()
        self._load_all()
        self._render_rows(self._all_results)
        self.grab_set()

    def _build(self):
        self._search_entry = ctk.CTkEntry(self, placeholder_text="🔍 search commands...", width=440)
        self._search_entry.pack(padx=16, pady=(16, 4))
        self._search_entry.bind("<KeyRelease>", lambda e: self._on_query_change())
        self._search_entry.bind("<Return>", lambda e: self.trigger_enter())
        self._search_entry.bind("<Escape>", lambda e: self.trigger_esc())
        self._search_entry.bind("<Down>", lambda e: self._move_selection(1))
        self._search_entry.bind("<Up>", lambda e: self._move_selection(-1))
        self._search_entry.focus_set()

        self._results_frame = ctk.CTkScrollableFrame(self, height=220, width=460)
        self._results_frame.pack(padx=16, pady=(4, 8))

        ctk.CTkLabel(self, text="↑↓ navigate   Enter launch   Esc dismiss",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(0, 8))

    def _load_all(self):
        self._all_results = []
        for repo_path in self._vm.all_repos():
            cmds = self._vm.saved_commands(repo_path)
            wts = self._vm.list_worktrees(repo_path)
            for cmd in cmds:
                self._all_results.append((cmd, repo_path, wts))

    def _render_rows(self, results: list) -> None:
        for row in self._rows:
            row.destroy()
        self._rows = []
        self._selected_idx = 0
        for cmd, repo_path, wts in results:
            row = _ResultRow(self._results_frame, cmd=cmd, repo_path=repo_path, worktrees=wts)
            row.pack(fill="x", pady=1)
            self._rows.append(row)
        self._highlight_selected()

    def _on_query_change(self) -> None:
        query = self._search_entry.get().lower()
        filtered = [
            (cmd, rp, wts) for cmd, rp, wts in self._all_results
            if query in cmd.name.lower() or query in Path(rp).name.lower()
        ]
        self._render_rows(filtered)

    def _highlight_selected(self) -> None:
        for i, row in enumerate(self._rows):
            row.configure(fg_color=("gray25" if i == self._selected_idx else "transparent"))

    def _move_selection(self, delta: int) -> None:
        if not self._rows:
            return
        self._selected_idx = (self._selected_idx + delta) % len(self._rows)
        self._highlight_selected()

    # --- public API for tests ---

    def result_count(self) -> int:
        return len(self._rows)

    def set_query(self, query: str) -> None:
        self._search_entry.delete(0, "end")
        self._search_entry.insert(0, query)
        self._on_query_change()

    def trigger_enter(self) -> None:
        if not self._rows:
            return
        row = self._rows[self._selected_idx]
        cmd = row.cmd()
        repo_path = row.repo_path()
        worktree_path = row.selected_worktree_path()
        self._vm.launch(
            repo_path=repo_path,
            repo_name=Path(repo_path).name,
            cmd_name=cmd.name,
            command_str=cmd.command,
            worktree_path=worktree_path,
        )
        self.destroy()

    def trigger_esc(self) -> None:
        self.destroy()
