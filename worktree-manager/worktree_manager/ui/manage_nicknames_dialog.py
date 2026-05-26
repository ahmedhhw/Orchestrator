from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)


class ManageNicknamesDialog(QDialog):
    def __init__(self, parent, nickname_store):
        super().__init__(parent)
        self.setWindowTitle("Manage Nicknames")
        self.setModal(True)
        self._store = nickname_store
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        outer.addWidget(QLabel("Saved nicknames:"))

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll, 1)

        self._empty_label = QLabel("No nicknames saved.")
        self._empty_label.setStyleSheet("color: gray;")
        outer.addWidget(self._empty_label)

        btns = QHBoxLayout()
        btns.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        outer.addLayout(btns)

        self._refresh()

    def _refresh(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        entries = self._store.all()
        self._empty_label.setVisible(len(entries) == 0)
        self._scroll.setVisible(len(entries) > 0)

        for nick, entry in sorted(entries.items()):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            label = QLabel(f"<b>{nick}</b>  →  {entry.action_name}  {' '.join(str(v) for v in entry.args.values())}")
            label.setObjectName(f"nick_label_{nick}")
            row_layout.addWidget(label, 1)

            del_btn = QPushButton("Delete")
            del_btn.setObjectName(f"del_btn_{nick}")
            del_btn.setStyleSheet("background-color: #c0392b; color: white;")
            del_btn.clicked.connect(lambda _=False, n=nick: self._delete(n))
            row_layout.addWidget(del_btn)

            self._list_layout.addWidget(row)

        self._list_layout.addStretch(1)

    def _delete(self, nickname: str) -> None:
        self._store.delete(nickname)
        self._refresh()

    def nickname_count(self) -> int:
        return len(self._store.all())
