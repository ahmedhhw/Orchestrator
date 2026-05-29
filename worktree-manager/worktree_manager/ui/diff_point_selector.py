from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QLineEdit, QPushButton,
)
from PySide6.QtCore import Qt


class DiffPointSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []
        self._compare_cb = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("FROM (base — restore destination)"))
        self._from_filter = QLineEdit()
        self._from_filter.setPlaceholderText("🔍 Search...")
        layout.addWidget(self._from_filter)
        self._from_list = QListWidget()
        layout.addWidget(self._from_list)

        layout.addWidget(QLabel("TO (target — what to diff against)"))
        self._to_filter = QLineEdit()
        self._to_filter.setPlaceholderText("🔍 Search...")
        layout.addWidget(self._to_filter)
        self._to_list = QListWidget()
        layout.addWidget(self._to_list)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._compare_btn = QPushButton("Compare →")
        btn_row.addWidget(self._compare_btn)
        layout.addLayout(btn_row)

        self._from_filter.textChanged.connect(lambda text: self._apply_filter(self._from_list, text))
        self._to_filter.textChanged.connect(lambda text: self._apply_filter(self._to_list, text))
        self._compare_btn.clicked.connect(self._on_compare_clicked)

    def set_repo(self, repo_path: str, points: list) -> None:
        self._points = points
        self._populate_list(self._from_list, points)
        self._populate_list(self._to_list, points)
        self._from_filter.clear()
        self._to_filter.clear()

    def on_compare(self, callback) -> None:
        self._compare_cb = callback

    def _populate_list(self, lst: QListWidget, points: list) -> None:
        lst.clear()
        for pt in points:
            if pt.short_sha:
                text = f"{pt.label}  {pt.short_sha}  \"{pt.message}\""
            else:
                text = pt.label
            item = QListWidgetItem(text)
            ref = pt.kind if pt.kind.startswith("working_tree") else pt.label
            item.setData(Qt.UserRole, ref)
            lst.addItem(item)

    def _apply_filter(self, lst: QListWidget, text: str) -> None:
        lower = text.lower()
        for i in range(lst.count()):
            item = lst.item(i)
            item.setHidden(bool(lower) and lower not in item.text().lower())

    def pre_select(self, from_ref: str | None, to_ref: str | None) -> None:
        self._from_list.clearSelection()
        self._from_list.setCurrentItem(None)
        self._to_list.clearSelection()
        self._to_list.setCurrentItem(None)
        if to_ref is not None:
            self._select_by_ref(self._to_list, to_ref)
        if from_ref is not None:
            self._select_by_ref(self._from_list, from_ref)

    def _select_by_ref(self, lst: QListWidget, ref: str) -> None:
        from PySide6.QtCore import Qt
        for i in range(lst.count()):
            item = lst.item(i)
            if item.data(Qt.UserRole) == ref:
                lst.setCurrentItem(item)
                return

    def _on_compare_clicked(self) -> None:
        from_item = self._from_list.currentItem()
        to_item = self._to_list.currentItem()
        if from_item is None or to_item is None:
            return
        if self._compare_cb:
            self._compare_cb(from_item.data(Qt.UserRole), to_item.data(Qt.UserRole))
