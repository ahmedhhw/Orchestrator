# PySide6 Migration

## Overview

Migrate the worktree-manager GUI from CustomTkinter (a Tkinter wrapper) to PySide6 (Qt6 bindings for Python). The app is an MVVM-structured desktop tool for managing git worktrees, a command center for running shell commands, and a workspace projects panel. The migration replaces every UI file while keeping all ViewModels, services, models, and business logic untouched. The goal is a native-feeling Qt app that is easier to style, theme, and maintain long-term than the CTk layer.

## UI / Flow

The app has a persistent sidebar on the left and a swappable main content area on the right. Three top-level views can be loaded into the main area: the worktree list, the command center, and the workspace projects panel.

### Main window skeleton

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌──────────────┐  ┌──────────────────────────────────────────┐ │
│  │ Sidebar      │  │ Main Content Area                        │ │
│  │              │  │                                          │ │
│  │ [⊞ Command   │  │  Git Worktree Manager — <repo>           │ │
│  │   Center   ] │  │  ─────────────────────────────           │ │
│  │ [⊞ Workspace │  │  Worktrees          [+ New]  [⚙] [🧹]   │ │
│  │   Projects ] │  │                                          │ │
│  │ ▼ REPOS      │  │  ● (main)   14d ago                      │ │
│  │  ● my-repo   │  │  ○ feature  2h ago   [branch ▾] [✕]     │ │
│  │  ○ other     │  │  ○ fix/bug  3d ago ⚠ stale ...          │ │
│  │  ✕           │  │                                          │ │
│  │              │  │                                          │ │
│  │ [+ Add Repo] │  │                                          │ │
│  │ [↻ Refresh ] │  │                                          │ │
│  └──────────────┘  └──────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Command Center panel

```
┌──────────────────────────────────────────────────────────────┐
│  Command Center                     [⚙ Commands] [+ Launch] [×]│
│  ┌────────────────────────────────────────────────────────┐   │
│  │ Filter running commands by name or repo…               │   │
│  └────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ ● my-server  (my-repo / main)    [▶] [■] [⧉] [✕]       │  │
│  │ ┌───────────────────────────────────────────────────┐   │  │
│  │ │ stdout output scrollable text area                │   │  │
│  │ └───────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Cleanup Wizard (modal dialog)

```
┌────────────────────────────────────┐
│  Cleanup Wizard                    │
│  ┌──────────────────────────────┐  │
│  │ Merged:                      │  │
│  │   → into main  [Select all]  │  │
│  │   ☑ feature/foo (merged…)    │  │
│  │ ────────────────────────────  │  │
│  │ Stale:         [Select all]  │  │
│  │   ☑ fix/bar   (30d, stale)   │  │
│  │ ────────────────────────────  │  │
│  │ Healthy:                     │  │
│  │   ☐ main/baz  (2h ago)       │  │
│  └──────────────────────────────┘  │
│  ☐ Admin Mode ⚠                    │
│  [Select All] [Cancel]   [Delete]  │
└────────────────────────────────────┘
```

## Architecture

```mermaid
graph TD
    subgraph "UNCHANGED (business logic)"
        VM1[MainWindowViewModel]
        VM2[CommandCenterViewModel]
        VM3[WorkspaceProjectsViewModel]
        VM4[RepoSetupViewModel / SettingsViewModel]
        SVC[GitService / ConfigStore / WorkspaceService / CommandRunner]
        MOD[Models]
        VM1 --> SVC
        VM2 --> SVC
        VM3 --> SVC
        VM4 --> SVC
        SVC --> MOD
    end

    subgraph "REPLACED (UI layer)"
        CLI[cli.py — App class]
        MW[main_window.py — QWidget]
        CCP[command_center_panel.py — QWidget]
        WPP[workspace_projects_panel.py — QWidget]
        CP[command_pane.py — QWidget]
        CWZ[cleanup_wizard.py — QDialog]
        DLG[*_dialog.py — QDialog subclasses]
        SP[settings_panel.py — QDialog]
        LS[landing_screen.py — QWidget]
        SCR[scroll_fix.py — DELETE]
    end

    CLI --> VM1
    CLI --> VM2
    CLI --> VM3
    MW --> VM1
    CCP --> VM2
    WPP --> VM3
    DLG --> VM4

    style SCR fill:#c0392b,color:#fff
```

**Key Qt mapping decisions:**

| CTk concept | Qt6 equivalent |
|---|---|
| `ctk.CTk()` | `QApplication` + `QMainWindow` |
| `ctk.CTkFrame` | `QWidget` or `QFrame` |
| `ctk.CTkToplevel` | `QDialog` (modal) or `QWidget` (floating) |
| `ctk.CTkScrollableFrame` | `QScrollArea` with a `QWidget` container |
| `ctk.CTkLabel` | `QLabel` |
| `ctk.CTkButton` | `QPushButton` |
| `ctk.CTkOptionMenu` | `QComboBox` |
| `ctk.CTkEntry` | `QLineEdit` |
| `ctk.CTkCheckBox` | `QCheckBox` |
| `ctk.CTkSegmentedButton` | `QButtonGroup` with radio buttons or a `QTabBar` |
| `ctk.CTkProgressBar` | `QProgressBar` |
| `ctk.StringVar` / `ctk.BooleanVar` | plain Python state + signal/slot wiring |
| `tkinter.messagebox` | `QMessageBox` |
| `tkinter.filedialog` | `QFileDialog` |
| `attach_scroll_fix()` | DELETE — Qt handles scroll natively |
| `.after(0, fn)` | `QTimer.singleShot(0, fn)` |
| `.pack()` / `.place()` | `QVBoxLayout` / `QHBoxLayout` / `QGridLayout` |
| `widget.trace_add("write", cb)` | Connect `QLineEdit.textChanged` etc. |
| `.configure(...)` | Direct property setters or stylesheets |

**Styling:** Use a single `QSS` stylesheet (Qt's CSS-like system) applied at app startup to replicate the dark/light appearance that CTk provided. The `appearance_mode = "system"` behavior maps to `QApplication.setStyle()` + palette.

## Iteration Plan

### Iteration 0 — Walking Skeleton
**Delivers:** The app launches with PySide6, shows the sidebar and the empty-state placeholder in the main area, and a repo can be added, saved, and switched between via the sidebar — no CTk imports survive.

**Scope:**
- Install PySide6, remove customtkinter from dependencies
- Delete `scroll_fix.py`
- Rewrite `cli.py` (`App` class + `main()`) using `QApplication` + `QMainWindow`
- Rewrite sidebar: repo list (collapsible), Add Repo button (via `QFileDialog`), Refresh button, Command Center button, Workspace Projects button
- Rewrite landing screen (empty state placeholder widget)
- Rewrite `main_window.py` (worktree list panel with branch switcher, New/Delete/Settings/Cleanup buttons — no dialogs wired yet, just stubs that print/pass)
- OS light/dark theme: apply `QApplication` palette from system at startup
- Add one `pytest-qt` smoke test: app launches without crashing

**Explicitly out of scope:** All dialogs (Create, Delete, Settings, RepoSetup, Cleanup, CommandCenter, WorkspaceProjects, AddCommand, ManageCommands, Launch) — those are wired in later iterations.

---

### Iteration 1 — Core Worktree Dialogs
**Delivers:** A user can create a new worktree, delete an existing one, and configure a newly-added repo — all from within the running Qt app.

**Scope:**
- `create_dialog.py` → `QDialog` (new branch / existing branch modes, copy-button helpers)
- `delete_dialog.py` → `QDialog` (also-delete-branch checkbox, uncommitted-changes warning)
- `repo_setup_dialog.py` → `QDialog` (worktree storage path picker)
- `settings_panel.py` → `QDialog` (storage path + stale days)
- Wire all four into `App` / `MainWindow`
- `pytest-qt` smoke tests for each dialog: opens without crash, cancel closes it, confirm calls the right VM method

**Builds on:** Iteration 0

---

### Iteration 2 — Command Center
**Delivers:** The Command Center panel is fully functional: users can manage saved commands, launch them against any repo/worktree, see live output, stop/restart/remove runs, and pop-out individual panes.

**Scope:**
- `command_center_panel.py` → `QWidget` (search filter, pane list, Launch + Manage Commands buttons)
- `command_pane.py` → `QWidget` (status dot, header buttons, scrollable output text, find bar)
- `command_popout.py` → `QDialog` (detached pane window)
- `manage_commands_dialog.py` → `QDialog` (per-repo command list, edit/delete inline)
- `add_command_dialog.py` → `QDialog` (repo picker, name, command text)
- `launch_dialog.py` → `QDialog` (repo/worktree/command picker with filter)
- Wire into `App._show_command_center()`
- `pytest-qt` smoke tests: panel loads, launch dialog opens/cancels, add-command dialog saves

**Builds on:** Iteration 1

---

### Iteration 3 — Cleanup Wizard & Workspace Projects
**Delivers:** The Cleanup Wizard correctly lists and deletes merged/stale branches with admin-mode support, and the Workspace Projects panel lets users create, open, and manage projects — completing the full feature set.

**Scope:**
- `cleanup_wizard.py` → `QDialog` (grouped branch list, checkboxes, admin mode toggle, progress loading state, select-all/subgroup buttons)
- `workspace_projects_panel.py` → `QWidget` (project list with collapsible groups, editor radio buttons, New dialog)
- `new_project_dialog.py` → `QDialog`
- `project_operations_dialog.py` → `QDialog`
- `landing_screen.py` → finalize (already stubbed in Iteration 0)
- Wire Cleanup Wizard into `App._show_cleanup()`
- Wire Workspace Projects into `App._show_workspace_projects()`
- `pytest-qt` smoke tests: cleanup wizard loads with candidates, workspace panel loads projects
- Full regression pass confirming Iterations 0–2 behaviour still works

**Builds on:** Iteration 2

---

## Iteration 0 — Walking Skeleton

### Phase 0.1 — PySide6 Dependencies & pytest-qt Wiring

**What it covers:** Install PySide6 + pytest-qt, configure pytest to use the PySide6 backend, verify the fixtures work end-to-end. No production widgets yet — just the foundation everything else builds on.

**Tests (Red) — write these first:**

```python
# tests/test_pyside6_setup.py
def test_pyside6_importable():
    """PySide6 is installed and importable."""
    import PySide6.QtWidgets  # noqa: F401


def test_qapplication_can_be_created(qapp):
    """pytest-qt's qapp fixture provides a real QApplication backed by PySide6."""
    from PySide6.QtWidgets import QApplication
    assert isinstance(qapp, QApplication)


def test_qtbot_can_add_widget(qtbot):
    """qtbot fixture works and can manage a QWidget lifecycle."""
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    qtbot.addWidget(w)
    assert w.isHidden() or w.isVisible() or True  # smoke
```

**Production code (Green):**

Update `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "worktree-manager"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = ["customtkinter>=5.2", "PySide6>=6.6"]

[project.optional-dependencies]
dev = ["pytest>=7", "pytest-qt>=4.2"]

[project.scripts]
worktree-manager = "worktree_manager.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["worktree_manager*"]

[tool.pytest.ini_options]
qt_api = "pyside6"
```

Install:

```
python3.14 -m pip install "PySide6>=6.6" "pytest-qt>=4.2"
```

**Done when:** `python3.14 -m pytest tests/test_pyside6_setup.py` passes with all three tests green, and `python3.14 -c "import PySide6.QtWidgets"` works.

---

### Phase 0.2 — LandingScreen Widget (Qt)

**What it covers:** Replace the CTk `LandingScreen` widget with a Qt `QWidget` that shows the empty-state message. Same behaviour as the current inline `_show_empty_main()` placeholder.

**Tests (Red) — write these first:**

```python
# tests/test_landing_screen_qt.py
from PySide6.QtWidgets import QLabel
from worktree_manager.ui.landing_screen import LandingScreen


def test_landing_screen_is_a_qwidget(qtbot):
    from PySide6.QtWidgets import QWidget
    w = LandingScreen()
    qtbot.addWidget(w)
    assert isinstance(w, QWidget)


def test_landing_screen_shows_empty_message(qtbot):
    w = LandingScreen()
    qtbot.addWidget(w)
    texts = [lbl.text() for lbl in w.findChildren(QLabel)]
    combined = "\n".join(texts)
    assert "No repo selected" in combined
    assert "Add Repo" in combined
```

**Production code (Green):**

Replace `worktree_manager/ui/landing_screen.py`:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LandingScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(
            "No repo selected.\n"
            "Pick one from the sidebar or click + Add Repo."
        )
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: gray;")
        layout.addWidget(label)
```

**Done when:** `python3.14 -m pytest tests/test_landing_screen_qt.py` is green, and the file no longer imports `customtkinter` or `tkinter`.

---

### Phase 0.3 — Sidebar Widget (Qt)

**What it covers:** Replace the CTk sidebar (currently inline in `cli.py`) with a self-contained `Sidebar` Qt widget. Lists repos from the store, supports collapse, exposes click callbacks for every action.

**Tests (Red) — write these first:**

```python
# tests/test_sidebar_qt.py
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.sidebar import Sidebar


def _make_store(repos=None, collapsed=None):
    store = MagicMock()
    store.all_repos.return_value = repos or {}
    store.get_ui_pref.side_effect = lambda key, default=None: (
        collapsed if key == "repos_collapsed" else default
    )
    return store


def _make_sidebar(qtbot, store, **overrides):
    callbacks = {
        "on_command_center": lambda: None,
        "on_workspace_projects": lambda: None,
        "on_add_repo": lambda: None,
        "on_refresh": lambda: None,
        "on_repo_selected": lambda path: None,
        "on_repo_delete": lambda path: None,
    }
    callbacks.update(overrides)
    sb = Sidebar(store=store, active_repo_path=None, **callbacks)
    qtbot.addWidget(sb)
    return sb


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def test_sidebar_has_top_action_buttons(qtbot):
    sb = _make_sidebar(qtbot, _make_store())
    texts = _button_texts(sb)
    assert any("Command Center" in t for t in texts)
    assert any("Workspace Projects" in t for t in texts)
    assert any("Add Repo" in t for t in texts)
    assert any("Refresh" in t for t in texts)


def test_sidebar_lists_configured_repos(qtbot, tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    sb = _make_sidebar(qtbot, _make_store({str(repo_a): {}, str(repo_b): {}}))
    texts = _button_texts(sb)
    assert any("repo-a" in t for t in texts)
    assert any("repo-b" in t for t in texts)


def test_sidebar_marks_active_repo_with_filled_dot(qtbot, tmp_path):
    repo = tmp_path / "repo-a"
    store = _make_store({str(repo): {}})
    sb = Sidebar(
        store=store,
        on_command_center=lambda: None,
        on_workspace_projects=lambda: None,
        on_add_repo=lambda: None,
        on_refresh=lambda: None,
        on_repo_selected=lambda p: None,
        on_repo_delete=lambda p: None,
        active_repo_path=str(repo),
    )
    qtbot.addWidget(sb)
    texts = _button_texts(sb)
    assert any(t.startswith("● ") and "repo-a" in t for t in texts)


def test_sidebar_repo_button_invokes_on_repo_selected(qtbot, tmp_path):
    repo = tmp_path / "repo-a"
    clicked: list = []
    sb = _make_sidebar(
        qtbot, _make_store({str(repo): {}}),
        on_repo_selected=lambda p: clicked.append(p),
    )
    btn = next(b for b in sb.findChildren(QPushButton) if "repo-a" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert clicked == [str(repo)]


def test_sidebar_delete_button_invokes_on_repo_delete(qtbot, tmp_path):
    repo = tmp_path / "repo-a"
    deleted: list = []
    sb = _make_sidebar(
        qtbot, _make_store({str(repo): {}}),
        on_repo_delete=lambda p: deleted.append(p),
    )
    del_btn = next(b for b in sb.findChildren(QPushButton) if b.text() == "✕")
    qtbot.mouseClick(del_btn, Qt.LeftButton)
    assert deleted == [str(repo)]


def test_sidebar_top_action_button_invokes_callback(qtbot):
    triggered: list = []
    sb = _make_sidebar(
        qtbot, _make_store(),
        on_command_center=lambda: triggered.append("cc"),
    )
    btn = next(b for b in sb.findChildren(QPushButton) if "Command Center" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == ["cc"]


def test_sidebar_toggle_collapse_persists_to_store(qtbot):
    store = _make_store(collapsed=False)
    sb = _make_sidebar(qtbot, store)
    assert sb.repos_visible() is True
    sb.toggle_repos_section()
    assert sb.repos_visible() is False
    store.set_ui_pref.assert_called_with("repos_collapsed", True)


def test_sidebar_starts_collapsed_when_store_pref_is_true(qtbot):
    store = _make_store(collapsed=True)
    sb = _make_sidebar(qtbot, store)
    assert sb.repos_visible() is False


def test_sidebar_set_active_repo_updates_dot_marker(qtbot, tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    sb = _make_sidebar(qtbot, _make_store({str(repo_a): {}, str(repo_b): {}}))
    sb.set_active_repo(str(repo_b))
    texts = _button_texts(sb)
    assert any(t.startswith("● ") and "repo-b" in t for t in texts)
    assert any(t.startswith("○ ") and "repo-a" in t for t in texts)
```

**Production code (Green):**

New file `worktree_manager/ui/sidebar.py`:

```python
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class Sidebar(QWidget):
    def __init__(
        self,
        store,
        on_command_center,
        on_workspace_projects,
        on_add_repo,
        on_refresh,
        on_repo_selected,
        on_repo_delete,
        active_repo_path=None,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._on_repo_selected = on_repo_selected
        self._on_repo_delete = on_repo_delete
        self._active_repo_path = active_repo_path
        self._repo_buttons: dict = {}

        self.setFixedWidth(220)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 8, 4, 12)
        outer.setSpacing(4)

        cc_btn = QPushButton("⊞ Command Center")
        cc_btn.clicked.connect(on_command_center)
        outer.addWidget(cc_btn)

        wp_btn = QPushButton("⊞ Workspace Projects")
        wp_btn.clicked.connect(on_workspace_projects)
        outer.addWidget(wp_btn)

        self._collapsed = bool(store.get_ui_pref("repos_collapsed", False))
        arrow = "▶" if self._collapsed else "▼"
        self._header_btn = QPushButton(f"{arrow} REPOS")
        self._header_btn.setFlat(True)
        self._header_btn.setStyleSheet(
            "text-align: left; color: gray; font-weight: bold;"
        )
        self._header_btn.clicked.connect(self.toggle_repos_section)
        outer.addWidget(self._header_btn)

        self._repo_scroll = QScrollArea()
        self._repo_scroll.setWidgetResizable(True)
        self._repo_scroll.setFixedHeight(220)
        self._repo_container = QWidget()
        self._repo_layout = QVBoxLayout(self._repo_container)
        self._repo_layout.setContentsMargins(0, 0, 0, 0)
        self._repo_layout.setSpacing(2)
        self._repo_layout.addStretch(1)
        self._repo_scroll.setWidget(self._repo_container)
        outer.addWidget(self._repo_scroll)
        self._repo_scroll.setVisible(not self._collapsed)

        outer.addStretch(1)

        add_btn = QPushButton("+ Add Repo")
        add_btn.clicked.connect(on_add_repo)
        outer.addWidget(add_btn)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(on_refresh)
        outer.addWidget(refresh_btn)

        self.populate_repo_rows()

    def populate_repo_rows(self):
        while self._repo_layout.count():
            item = self._repo_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._repo_buttons.clear()

        for path in self._store.all_repos().keys():
            name = Path(path).name
            is_active = (path == self._active_repo_path)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            label = ("● " if is_active else "○ ") + name
            btn = QPushButton(label)
            btn.setStyleSheet("text-align: left;")
            btn.clicked.connect(
                lambda _checked=False, p=path: self._on_repo_selected(p)
            )
            row_layout.addWidget(btn, 1)

            del_btn = QPushButton("✕")
            del_btn.setFixedWidth(28)
            del_btn.setStyleSheet(
                "background-color: #c0392b; color: white; border: none;"
            )
            del_btn.clicked.connect(
                lambda _checked=False, p=path: self._on_repo_delete(p)
            )
            row_layout.addWidget(del_btn)

            self._repo_layout.addWidget(row)
            self._repo_buttons[path] = btn

        self._repo_layout.addStretch(1)

    def set_active_repo(self, repo_path):
        self._active_repo_path = repo_path
        self.populate_repo_rows()

    def repos_visible(self):
        return self._repo_scroll.isVisible()

    def toggle_repos_section(self):
        self._collapsed = not self._collapsed
        self._store.set_ui_pref("repos_collapsed", self._collapsed)
        arrow = "▶" if self._collapsed else "▼"
        self._header_btn.setText(f"{arrow} REPOS")
        self._repo_scroll.setVisible(not self._collapsed)
```

**Done when:** All sidebar tests pass and the widget renders the expected button labels for an empty store, a single-repo store, and a multi-repo store.

---

### Phase 0.4 — MainWindow Widget (Qt — worktree list)

**What it covers:** Replace the CTk `MainWindow` with a Qt `QWidget` that lists worktrees, supports branch switching via `QComboBox`, and exposes header buttons for + New, ⚙ Settings, and 🧹 Cleanup. The dialog launches themselves are stubbed in this iteration (they just call the provided callback or `print()`); real dialogs arrive in Iteration 1.

**Tests (Red) — write these first:**

```python
# tests/test_main_window_qt.py
import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.main_window import MainWindow


def _make_vm():
    now = int(time.time())
    vm = MagicMock(spec=MainWindowViewModel)
    vm.load_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
    ]
    vm.list_branches_with_checkout_status.return_value = [
        ("main", True), ("fix/auth", True), ("hotfix/2.1", False),
    ]
    return vm


def _make_window(qtbot, vm=None, on_settings=None, on_cleanup=None, on_new=None):
    win = MainWindow(
        vm=vm or _make_vm(),
        repo_name="proj",
        on_settings=on_settings or (lambda: None),
        on_cleanup=on_cleanup or (lambda: None),
        on_new=on_new or (lambda: None),
    )
    qtbot.addWidget(win)
    return win


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def _buttons(widget):
    return widget.findChildren(QPushButton)


def test_main_window_header_shows_repo_name(qtbot):
    win = _make_window(qtbot)
    assert any("proj" in t for t in _label_texts(win))


def test_main_window_has_new_settings_cleanup_buttons(qtbot):
    win = _make_window(qtbot)
    btn_texts = [b.text() for b in _buttons(win)]
    assert any("New" in t for t in btn_texts)
    assert any("⚙" in t for t in btn_texts)
    assert any("🧹" in t for t in btn_texts)


def test_main_window_lists_non_main_worktree_folder_names(qtbot):
    win = _make_window(qtbot)
    texts = _label_texts(win)
    assert any("fix-auth" in t for t in texts)
    assert any("(main)" in t for t in texts)


def test_main_window_shows_branch_dropdown_per_worktree(qtbot):
    win = _make_window(qtbot)
    combos = win.findChildren(QComboBox)
    # one per worktree (2 in the fixture)
    assert len(combos) == 2


def test_main_window_branch_dropdown_lists_all_branches(qtbot):
    win = _make_window(qtbot)
    combo = win.findChildren(QComboBox)[0]
    values = [combo.itemText(i) for i in range(combo.count())]
    assert "main" in values
    assert "fix/auth" in values
    assert "hotfix/2.1" in values


def test_main_window_switch_branch_calls_vm(qtbot):
    vm = _make_vm()
    win = _make_window(qtbot, vm=vm)
    win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    vm.switch_branch.assert_called_once_with("/repos/proj-wt/fix-auth", "hotfix/2.1")


def test_main_window_switch_branch_shows_error_on_uncommitted(qtbot):
    vm = _make_vm()
    vm.switch_branch.side_effect = ValueError("uncommitted changes")
    win = _make_window(qtbot, vm=vm)
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_err:
        result = win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    mock_err.assert_called_once()
    assert result is False


def test_main_window_switch_branch_refreshes_on_success(qtbot):
    vm = _make_vm()
    win = _make_window(qtbot, vm=vm)
    initial = vm.load_worktrees.call_count
    win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    assert vm.load_worktrees.call_count > initial


def test_main_window_new_button_invokes_callback(qtbot):
    called: list = []
    win = _make_window(qtbot, on_new=lambda: called.append("new"))
    btn = next(b for b in _buttons(win) if "New" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert called == ["new"]


def test_main_window_settings_button_invokes_callback(qtbot):
    called: list = []
    win = _make_window(qtbot, on_settings=lambda: called.append("settings"))
    btn = next(b for b in _buttons(win) if "⚙" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert called == ["settings"]


def test_main_window_cleanup_button_invokes_callback(qtbot):
    called: list = []
    win = _make_window(qtbot, on_cleanup=lambda: called.append("cleanup"))
    btn = next(b for b in _buttons(win) if "🧹" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert called == ["cleanup"]


def test_main_window_stale_worktree_shows_warning(qtbot):
    vm = _make_vm()
    vm.load_worktrees.return_value = [
        WorktreeModel("/repos/proj-wt/old", "old", False, 0, True, False),
    ]
    win = _make_window(qtbot, vm=vm)
    texts = _label_texts(win)
    assert any("stale" in t for t in texts)
```

**Production code (Green):**

Replace `worktree_manager/ui/main_window.py`:

```python
import os
import time

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel


def _fmt_age(ts):
    if ts == 0:
        return "no commits"
    diff = int(time.time()) - ts
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


class MainWindow(QWidget):
    def __init__(self, vm: MainWindowViewModel, repo_name: str,
                 on_settings, on_cleanup, on_new, parent=None):
        super().__init__(parent)
        self._vm = vm
        self._repo_name = repo_name
        self._on_settings = on_settings
        self._on_cleanup = on_cleanup
        self._on_new = on_new

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 8)
        outer.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(f"Git Worktree Manager — {self._repo_name}")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        header.addWidget(title)
        header.addStretch(1)
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedWidth(36)
        settings_btn.clicked.connect(self._on_settings)
        cleanup_btn = QPushButton("🧹")
        cleanup_btn.setFixedWidth(36)
        cleanup_btn.clicked.connect(self._on_cleanup)
        header.addWidget(cleanup_btn)
        header.addWidget(settings_btn)
        outer.addLayout(header)

        sub = QHBoxLayout()
        sub_label = QLabel("Worktrees")
        sub_label.setStyleSheet("font-weight: bold;")
        sub.addWidget(sub_label)
        sub.addStretch(1)
        new_btn = QPushButton("+ New")
        new_btn.setFixedWidth(70)
        new_btn.clicked.connect(self._on_new)
        sub.addWidget(new_btn)
        outer.addLayout(sub)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch(1)
        self._list_scroll.setWidget(self._list_container)
        outer.addWidget(self._list_scroll, 1)

        self.refresh()

    def refresh(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        worktrees = self._vm.load_worktrees()
        branch_status = self._vm.list_branches_with_checkout_status()
        for wt in worktrees:
            self._add_row(wt, branch_status)
        self._list_layout.addStretch(1)

    def _add_row(self, wt: WorktreeModel, branch_status):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)

        dot = QLabel("●" if wt.is_main else "○")
        dot.setFixedWidth(20)
        layout.addWidget(dot)

        wt_name = os.path.basename(wt.path) if not wt.is_main else "(main)"
        name_label = QLabel(wt_name)
        name_label.setFixedWidth(200)
        layout.addWidget(name_label)

        age = QLabel(_fmt_age(wt.last_commit_ts))
        age.setStyleSheet("color: gray;")
        age.setFixedWidth(80)
        layout.addWidget(age)

        if wt.is_stale:
            stale = QLabel("⚠ stale")
            stale.setStyleSheet("color: orange;")
            stale.setFixedWidth(70)
            layout.addWidget(stale)
        else:
            spacer = QLabel("")
            spacer.setFixedWidth(70)
            layout.addWidget(spacer)

        layout.addStretch(1)

        all_branches = [b for b, _ in branch_status]
        checked_out_set = {b for b, co in branch_status if co and b != wt.branch}

        combo = QComboBox()
        combo.addItems(all_branches)
        if wt.branch in all_branches:
            combo.setCurrentText(wt.branch)
        combo.setFixedWidth(160)

        def _on_change(new_branch, path=wt.path, c=combo, orig=wt.branch):
            if new_branch == orig:
                return
            if new_branch in checked_out_set:
                QMessageBox.critical(
                    self, "Cannot switch",
                    f"'{new_branch}' is already checked out in another worktree.",
                )
                c.blockSignals(True)
                c.setCurrentText(orig)
                c.blockSignals(False)
                return
            if not self._switch_branch(path, new_branch):
                c.blockSignals(True)
                c.setCurrentText(orig)
                c.blockSignals(False)

        combo.currentTextChanged.connect(_on_change)
        layout.addWidget(combo)

        if not wt.is_main:
            del_btn = QPushButton("✕")
            del_btn.setFixedWidth(28)
            del_btn.setStyleSheet("background-color: #c0392b; color: white; border: none;")
            del_btn.clicked.connect(lambda _checked=False, w=wt: self._open_delete(w))
            layout.addWidget(del_btn)

        self._list_layout.addWidget(row)

    def _switch_branch(self, worktree_path, new_branch):
        try:
            self._vm.switch_branch(worktree_path, new_branch)
            self.refresh()
            return True
        except ValueError as e:
            QMessageBox.critical(self, "Cannot switch branch", str(e))
            return False

    def _open_delete(self, wt: WorktreeModel):
        # Stubbed in Iteration 0 — real DeleteDialog arrives in Iteration 1.
        print(f"[stub] delete worktree: {wt.path}")
```

**Done when:** All `test_main_window_qt.py` tests pass; the widget renders without any tkinter/customtkinter imports; clicking + New / ⚙ / 🧹 invokes the right callback; branch dropdown switching invokes `vm.switch_branch`.

---

### Phase 0.5 — App (QMainWindow) Wiring

**What it covers:** Replace the procedural `App` class in `cli.py` with a Qt `QMainWindow` that hosts the sidebar on the left and a swappable content area on the right. Wires up Add-Repo via `QFileDialog`, repo deletion via `QMessageBox.question`, and stubs the Settings / Cleanup / Command Center / Workspace Projects show-methods. System theme is whatever Qt's default native style provides (which on macOS already follows OS appearance).

**Tests (Red) — write these first:**

```python
# tests/test_cli_qt.py
import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QMainWindow

from worktree_manager.cli import App, parse_args, resolve_repo_path
from worktree_manager.git_service import GitService


# ── parse_args / resolve_repo_path: unchanged, copy of existing coverage ─────

def test_parse_args_no_argument():
    args = parse_args([])
    assert args.repo_path is None


def test_parse_args_with_path():
    args = parse_args(["/repos/proj"])
    assert args.repo_path == "/repos/proj"


def test_resolve_repo_path_valid(tmp_path):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = True
    repo = tmp_path / "myrepo"
    repo.mkdir()
    assert resolve_repo_path(str(repo), git) == str(repo)


def test_resolve_repo_path_invalid(tmp_path, capsys):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = False
    with pytest.raises(SystemExit):
        resolve_repo_path(str(tmp_path / "no"), git)
    assert "not a git repository" in capsys.readouterr().err.lower()


def test_resolve_repo_path_none_returns_none():
    assert resolve_repo_path(None, MagicMock(spec=GitService)) is None


# ── App: QMainWindow wiring ─────────────────────────────────────────────────

@pytest.fixture
def empty_store(tmp_path, monkeypatch):
    """Patch ConfigStore so all_repos returns empty and no file IO happens."""
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.side_effect = lambda key, default=None: default
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    return store


def test_app_is_qmainwindow(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert isinstance(app, QMainWindow)


def test_app_window_title_set(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert "Worktree Manager" in app.windowTitle()


def test_app_shows_landing_when_no_repo(qtbot, empty_store):
    from worktree_manager.ui.landing_screen import LandingScreen
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert isinstance(app._current_panel, LandingScreen)


def test_app_sidebar_present_when_no_repo(qtbot, empty_store):
    from worktree_manager.ui.sidebar import Sidebar
    app = App(repo_path=None)
    qtbot.addWidget(app)
    assert isinstance(app._sidebar, Sidebar)


def test_app_loads_main_window_when_repo_configured(qtbot, empty_store):
    from worktree_manager.models import RepoConfig
    from worktree_manager.ui.main_window import MainWindow

    cfg = RepoConfig(
        repo_path="/repos/proj", worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    empty_store.get_repo.return_value = cfg
    empty_store.all_repos.return_value = {"/repos/proj": cfg}

    with patch("worktree_manager.main_window_vm.MainWindowViewModel") as MockVM:
        MockVM.return_value.load_worktrees.return_value = []
        MockVM.return_value.list_branches_with_checkout_status.return_value = []
        app = App(repo_path="/repos/proj")
        qtbot.addWidget(app)
        assert isinstance(app._current_panel, MainWindow)


def test_app_pick_repo_uses_qfiledialog(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
               return_value="") as mock_dlg:
        app._pick_and_add_repo()
    mock_dlg.assert_called_once()


def test_app_pick_repo_rejects_non_git_with_messagebox(qtbot, empty_store, tmp_path):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    app._git.is_valid_repo = MagicMock(return_value=False)
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
               return_value=str(tmp_path)):
        with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_err:
            app._pick_and_add_repo()
    mock_err.assert_called_once()


def test_app_confirm_delete_repo_yes_removes_from_store(qtbot, empty_store):
    from worktree_manager.models import RepoConfig
    cfg = RepoConfig(
        repo_path="/repos/proj", worktree_storage="/repos/proj-wt",
        stale_days=30, last_editor="cursor", last_editor_mode="reuse",
        last_opened="2026-05-19T10:00:00",
    )
    empty_store.all_repos.return_value = {"/repos/proj": cfg}
    app = App(repo_path=None)
    qtbot.addWidget(app)
    from PySide6.QtWidgets import QMessageBox
    with patch("PySide6.QtWidgets.QMessageBox.question",
               return_value=QMessageBox.Yes):
        app._confirm_delete_repo("/repos/proj", is_active=False)
    empty_store.delete_repo.assert_called_once_with("/repos/proj")


def test_app_confirm_delete_repo_no_keeps_store_intact(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    from PySide6.QtWidgets import QMessageBox
    with patch("PySide6.QtWidgets.QMessageBox.question",
               return_value=QMessageBox.No):
        app._confirm_delete_repo("/repos/proj", is_active=False)
    empty_store.delete_repo.assert_not_called()


def test_app_show_command_center_is_stubbed_no_crash(qtbot, empty_store):
    """Iteration 0: real Command Center arrives in Iteration 2; method must exist
    and either no-op or show a 'coming soon' message without raising."""
    app = App(repo_path=None)
    qtbot.addWidget(app)
    app._show_command_center()  # must not raise


def test_app_show_workspace_projects_is_stubbed_no_crash(qtbot, empty_store):
    app = App(repo_path=None)
    qtbot.addWidget(app)
    app._show_workspace_projects()  # must not raise
```

**Production code (Green):**

Replace `worktree_manager/cli.py`:

```python
import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox,
    QWidget,
)

from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Git Worktree Manager")
    parser.add_argument("repo_path", nargs="?", default=None,
                        help="Path to the main git worktree")
    return parser.parse_args(argv)


def resolve_repo_path(path, git):
    if path is None:
        return None
    if not git.is_valid_repo(path):
        print(f"Error: '{path}' is not a git repository.", file=sys.stderr)
        sys.exit(1)
    return path


class App(QMainWindow):
    def __init__(self, repo_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git Worktree Manager")
        self.resize(900, 520)
        self.setMinimumSize(700, 400)

        self._store = ConfigStore()
        self._git = GitService()
        self._active_repo_path = None
        self._current_panel = None

        central = QWidget()
        self._central_layout = QHBoxLayout(central)
        self._central_layout.setContentsMargins(0, 0, 0, 0)
        self._central_layout.setSpacing(0)
        self.setCentralWidget(central)

        from worktree_manager.ui.sidebar import Sidebar
        self._sidebar = Sidebar(
            store=self._store,
            on_command_center=self._show_command_center,
            on_workspace_projects=self._show_workspace_projects,
            on_add_repo=self._pick_and_add_repo,
            on_refresh=self._refresh,
            on_repo_selected=self._switch_repo,
            on_repo_delete=lambda p: self._confirm_delete_repo(
                p, is_active=(p == self._active_repo_path),
            ),
            active_repo_path=None,
        )
        self._central_layout.addWidget(self._sidebar)

        if repo_path:
            self._load_repo(repo_path)
        else:
            self._show_empty_main()

    # ── panel swap helpers ──────────────────────────────────────────────────

    def _set_panel(self, widget):
        if self._current_panel is not None:
            self._central_layout.removeWidget(self._current_panel)
            self._current_panel.deleteLater()
        self._current_panel = widget
        self._central_layout.addWidget(widget, 1)

    def _show_empty_main(self):
        from worktree_manager.ui.landing_screen import LandingScreen
        self._set_panel(LandingScreen())

    # ── repo lifecycle ──────────────────────────────────────────────────────

    def _pick_and_add_repo(self):
        path = QFileDialog.getExistingDirectory(self, "Select git repo")
        if not path:
            return
        if not self._git.is_valid_repo(path):
            QMessageBox.critical(self, "Error", f"'{path}' is not a git repository.")
            return
        self._load_repo(path)

    def _switch_repo(self, repo_path):
        self._load_repo(repo_path)

    def _load_repo(self, repo_path):
        cfg = self._store.get_repo(repo_path)
        if cfg is None:
            # RepoSetupDialog arrives in Iteration 1; for now just refuse silently
            QMessageBox.information(
                self, "Setup required",
                f"'{Path(repo_path).name}' is not configured yet. "
                "Setup dialog ships in Iteration 1.",
            )
            return
        self._show_main(repo_path)

    def _show_main(self, repo_path):
        from worktree_manager.main_window_vm import MainWindowViewModel
        from worktree_manager.ui.main_window import MainWindow

        self._active_repo_path = repo_path
        self._sidebar.set_active_repo(repo_path)

        vm = MainWindowViewModel(
            repo_path=repo_path,
            config_store=self._store,
            git_service=self._git,
        )
        repo_name = Path(repo_path).name
        self._set_panel(MainWindow(
            vm=vm, repo_name=repo_name,
            on_settings=lambda: self._show_settings(repo_path),
            on_cleanup=lambda: self._show_cleanup(vm),
            on_new=lambda: self._show_new_worktree(vm),
        ))

    def _confirm_delete_repo(self, repo_path, is_active):
        name = Path(repo_path).name
        extra = (
            "\n\nThis is the currently open repo. Removing it will return you to the empty screen."
            if is_active else ""
        )
        ans = QMessageBox.question(
            self, "Remove repo",
            f'Remove "{name}" from the app?\n\n{repo_path}{extra}\n\nFiles on disk are not affected.',
        )
        if ans != QMessageBox.Yes:
            return
        self._store.delete_repo(repo_path)
        if is_active:
            self._active_repo_path = None
            self._sidebar.set_active_repo(None)
            self._show_empty_main()
        else:
            self._sidebar.populate_repo_rows()

    def _refresh(self):
        self._sidebar.populate_repo_rows()
        if self._current_panel is not None and hasattr(self._current_panel, "refresh"):
            self._current_panel.refresh()

    # ── stubs for dialogs/panels arriving in later iterations ───────────────

    def _show_settings(self, repo_path):
        QMessageBox.information(self, "Settings", "Ships in Iteration 1.")

    def _show_cleanup(self, vm):
        QMessageBox.information(self, "Cleanup Wizard", "Ships in Iteration 3.")

    def _show_new_worktree(self, vm):
        QMessageBox.information(self, "New Worktree", "Ships in Iteration 1.")

    def _show_command_center(self):
        QMessageBox.information(self, "Command Center", "Ships in Iteration 2.")

    def _show_workspace_projects(self):
        QMessageBox.information(self, "Workspace Projects", "Ships in Iteration 3.")


def main():
    args = parse_args(sys.argv[1:])
    git = GitService()
    repo_path = resolve_repo_path(args.repo_path, git)

    qt_app = QApplication.instance() or QApplication(sys.argv)
    window = App(repo_path=repo_path)
    window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    main()
```

**Done when:** All `test_cli_qt.py` tests pass; `python3.14 -m worktree_manager.cli` launches a real window with the sidebar visible and the landing screen in the content area.

---

### Phase 0.6 — Cleanup: Delete `scroll_fix.py` + Broken Legacy Tests

**What it covers:** Remove the dead `scroll_fix.py` module (Qt handles scroll natively) and delete the CTk-based legacy tests for the files we just rewrote. These tests assert against CTk widget trees and instantiate the now-Qt `App`/`MainWindow` with CTk patterns — they cannot be salvaged in place.

**Tests (Red) — write these first:**

```python
# tests/test_iteration_0_cleanup.py
"""Iteration 0 cleanup: assert that dead modules and obsolete tests are gone."""
import importlib
import os
import pathlib

import pytest


def test_scroll_fix_module_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("worktree_manager.ui.scroll_fix")


@pytest.mark.parametrize("relpath", [
    "tests/test_hover_scoped_scroll.py",
    "tests/test_main_window_iter0.py",
    "tests/test_sidebar_redesign.py",
    "tests/test_sidebar_stable_repo_list.py",
    "tests/test_workspace_projects_sidebar_wiring.py",
])
def test_legacy_ctk_test_file_removed(relpath):
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    assert not (repo_root / relpath).exists(), \
        f"{relpath} still exists — delete it as part of Iteration 0 cleanup"


def test_no_ui_file_imports_customtkinter():
    """Iteration 0's rewritten UI files must not import customtkinter."""
    import worktree_manager.cli as cli_mod
    import worktree_manager.ui.landing_screen as ls_mod
    import worktree_manager.ui.main_window as mw_mod
    import worktree_manager.ui.sidebar as sb_mod
    for mod in (cli_mod, ls_mod, mw_mod, sb_mod):
        src = pathlib.Path(mod.__file__).read_text()
        assert "customtkinter" not in src, f"{mod.__name__} still imports customtkinter"
        assert "import tkinter" not in src, f"{mod.__name__} still imports tkinter"


def test_app_can_be_constructed_and_destroyed_cleanly(qtbot, monkeypatch):
    """End-to-end smoke: App constructs, shows, and tears down without raising."""
    from unittest.mock import MagicMock
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.side_effect = lambda key, default=None: default
    monkeypatch.setattr("worktree_manager.cli.ConfigStore", lambda *a, **kw: store)
    monkeypatch.setattr("worktree_manager.cli.GitService", lambda *a, **kw: MagicMock())
    from worktree_manager.cli import App
    app = App(repo_path=None)
    qtbot.addWidget(app)
    app.show()
    qtbot.waitExposed(app)
    app.close()
```

**Production code (Green):**

Delete these files:

```
worktree_manager/ui/scroll_fix.py
tests/test_hover_scoped_scroll.py
tests/test_main_window_iter0.py
tests/test_sidebar_redesign.py
tests/test_sidebar_stable_repo_list.py
tests/test_workspace_projects_sidebar_wiring.py
```

Also: scan `worktree_manager/ui/cli.py` (already rewritten in Phase 0.5) and all other rewritten Iter 0 UI files to confirm there are no leftover `from worktree_manager.ui.scroll_fix import attach_scroll_fix` lines. (Untouched UI files like `command_center_panel.py` keep their existing `attach_scroll_fix` imports — they will be deleted when those files are rewritten in Iterations 1–3. They still need to import successfully *if* something imports them; nothing in Iteration 0 imports them, so this is fine.)

Update `tests/test_cli.py`: rename to `tests/test_cli_legacy.py.bak` is NOT desirable — instead, **delete `tests/test_cli.py` entirely**, since `tests/test_cli_qt.py` (from Phase 0.5) now covers `parse_args`, `resolve_repo_path`, and the App lifecycle.

**Done when:** `python3.14 -m pytest tests/test_iteration_0_cleanup.py` passes; deleted test files are gone; `python3.14 -m pytest tests/` runs cleanly with no `ImportError`s related to `scroll_fix`. (Other unrelated test failures unrelated to Iter 0 work are acceptable to surface here.)

---

## ✋ Manual Testing Gate — Iteration 0

> STOP. Do not proceed to Iteration 1 until every item below is checked off by the user.

- [ ] Run `python3.14 -m worktree_manager.cli` from the `worktree-manager/` directory. A native Qt window titled "Git Worktree Manager" appears, sized roughly 900×520.
- [ ] The window has a fixed-width sidebar on the left containing: ⊞ Command Center, ⊞ Workspace Projects, a ▼ REPOS section header, + Add Repo, ↻ Refresh.
- [ ] The right side shows the landing message: "No repo selected. Pick one from the sidebar or click + Add Repo." in gray, centered.
- [ ] Click "▼ REPOS" — the arrow changes to ▶ and the (empty) repo scroll area collapses. Click again — it expands. Close and re-open the app — the collapse state was persisted.
- [ ] Click "+ Add Repo". A native folder picker opens. Cancel it — nothing happens. Pick a non-git folder — a red error dialog says "'<path>' is not a git repository."
- [ ] Pick a real git repo for the first time. An info dialog says "Setup dialog ships in Iteration 1." (RepoSetupDialog isn't wired yet — that's expected.)
- [ ] Manually configure a repo by editing `~/.config/worktree-manager/config.json` (or whatever path `ConfigStore` writes to) so that the repo has a worktree storage entry, then restart the app. The repo now appears in the sidebar with a ○ next to its name.
- [ ] Click the repo button in the sidebar. The landing screen disappears and the right side shows the Worktree Manager panel with header "Git Worktree Manager — <repo-name>", a + New button, a ⚙ Settings button, a 🧹 Cleanup button, and the worktree list.
- [ ] The worktree list shows one row per worktree with: dot (● for main, ○ for others), folder name (or "(main)"), age label, optional "⚠ stale", a branch dropdown, and (for non-main) a red ✕ button.
- [ ] Open the branch dropdown for a non-main worktree, select a different branch that is NOT checked out elsewhere — the branch is switched, the list refreshes, the row now reflects the new branch.
- [ ] Open the branch dropdown and select a branch that IS already checked out in another worktree — an error message appears and the dropdown reverts to the original branch.
- [ ] Click + New / ⚙ / 🧹 — each shows an info dialog saying "Ships in Iteration N" (no crashes).
- [ ] Click the red ✕ next to a repo in the sidebar — a Yes/No confirmation appears. Click No — nothing happens. Click Yes — the repo disappears from the sidebar; if it was the active one, the landing screen returns.
- [ ] Switch your OS appearance between Light and Dark mode while the app is open — the app's colors update to match (Qt's native style handles this on macOS).

**How to confirm:** Run the app, perform each action above, and check off each item manually.
Reply "Iteration 0 confirmed" (or describe any failures) before I write the plan for Iteration 1.

---

## Decisions

- **Theme:** Follow OS light/dark preference automatically via `QApplication` palette.
- **`scroll_fix.py`:** Delete entirely — Qt handles scroll natively, no replacement needed.
- **UI tests:** Add `pytest-qt` smoke tests alongside the existing VM/service tests.
- **Segmented button:** Replace `CTkSegmentedButton` with two plain `QRadioButton`s in a row.
