"""Verify that legacy CTk test files and dependencies from the PySide6 migration are gone."""
import pathlib


def _tests_dir():
    return pathlib.Path(__file__).resolve().parent


def _project_root():
    return _tests_dir().parent


def test_legacy_ui_smoke_test_deleted():
    assert not (_tests_dir() / "test_ui_smoke.py").exists(), (
        "test_ui_smoke.py still exists — delete it; all tests are covered by Qt equivalents"
    )


def test_legacy_delete_dialog_window_warning_test_deleted():
    assert not (_tests_dir() / "test_delete_dialog_window_warning.py").exists(), (
        "test_delete_dialog_window_warning.py still exists — "
        "covered by test_delete_dialog_qt.py"
    )


def test_customtkinter_not_in_pyproject_dependencies():
    pyproject = (_project_root() / "pyproject.toml").read_text()
    assert "customtkinter" not in pyproject, (
        "customtkinter is still listed as a dependency in pyproject.toml — remove it"
    )
