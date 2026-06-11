# Context: Iteration 0 — Force light mode

## Goal
Force the application to render in light mode regardless of the OS dark-mode setting, so the app no longer picks up macOS dark backgrounds/borders.

## Tests to write
- Application color scheme is forced to light on startup: after the app is constructed, `QApplication.styleHints().colorScheme()` is `Qt.ColorScheme.Light`.

## Files to touch
- [cli.py](worktree_manager/cli.py) — set the color scheme right after the `QApplication` is created in `main()`.

## Design / pseudocode

#### `worktree_manager/cli.py`
```
main():
    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.styleHints().setColorScheme(Qt.ColorScheme.Light)   # force light
    window = App(repo_path=repo_path)
    ...
```
For testability, prefer a tiny helper so the test doesn't need to spin the full window:
```
def force_light_mode(app):
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
```
Call `force_light_mode(qt_app)` in `main()`. The test constructs a `QApplication`, calls `force_light_mode(app)`, asserts `app.styleHints().colorScheme() == Qt.ColorScheme.Light`.

## Relevant existing code
[cli.py:1038](worktree_manager/cli.py#L1038):
```
qt_app = QApplication.instance() or QApplication(sys.argv)
window = App(repo_path=repo_path)
window.show()
sys.exit(qt_app.exec())
```
`Qt` is already imported in the Qt UI modules; ensure `from PySide6.QtCore import Qt` is available in cli.py (add if missing).

## Constraints / invariants
- API verified: PySide6 6.11.1 exposes `Qt.ColorScheme.Light` and `QStyleHints.setColorScheme` — no `QPalette` fallback needed.
- No silent exceptions.

## Done when (gate items)
- [ ] Launch the app on a Mac in OS dark mode — the app window renders with a light background/light controls.
- [ ] Toggling the OS appearance to light and back to dark while the app is open does not switch the app to dark.

## TDD mode: Autonomous
