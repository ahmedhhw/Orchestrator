from worktree_manager.ui.create_dialog import CreateDialog
from worktree_manager.ui.filterable_combo import FilterableComboBox


def _make_dialog(qtbot, branches=None):
    d = CreateDialog(
        parent=None,
        branches=branches or ["main", "feature/login", "feature/search"],
        existing_branches=["existing/one"],
        on_create=lambda *a: None,
    )
    qtbot.addWidget(d)
    return d


def test_base_combo_is_filterable(qtbot):
    d = _make_dialog(qtbot)
    assert isinstance(d._base_combo, FilterableComboBox)


def test_base_combo_is_editable(qtbot):
    d = _make_dialog(qtbot)
    assert d._base_combo.isEditable()


def test_base_var_reflects_committed_selection(qtbot):
    d = _make_dialog(qtbot)
    d._base_combo._on_popup_chosen("feature/login")
    assert d._base_var.get() == "feature/login"


def test_base_var_does_not_update_while_typing(qtbot):
    d = _make_dialog(qtbot)
    initial = d._base_var.get()
    d._base_combo.lineEdit().textEdited.emit("feat")
    assert d._base_var.get() == initial


def test_base_var_set_updates_combo_text(qtbot):
    d = _make_dialog(qtbot)
    d._base_var.set("feature/search")
    assert d._base_combo.currentText() == "feature/search"
