"""Verify that legacy CTk test files for the command-center components are gone."""
import os


def _tests_dir():
    return os.path.join(os.path.dirname(__file__))


def test_legacy_command_center_panel_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_command_center_panel.py"))


def test_legacy_command_pane_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_command_pane.py"))


def test_legacy_launch_dialog_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_launch_dialog.py"))


def test_legacy_manage_commands_dialog_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_manage_commands_dialog.py"))


def test_legacy_add_command_dialog_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_add_command_dialog.py"))
