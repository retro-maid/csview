from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton
)
from ..utils.i18n import _


class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("検索"))
        self.setModal(True)
        self.setFixedSize(400, 120)

        # 検索用UI部品の作成
        self.label = QLabel(_("検索ワード:"))
        self.search_input = QLineEdit()
        self.search_button = QPushButton(_("検索"))
        self.cancel_button = QPushButton(_("キャンセル"))

        # イベント接続
        self.search_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        # レイアウト設定
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.label)
        input_layout.addWidget(self.search_input)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.search_button)
        button_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addLayout(input_layout)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def get_search_text(self):
        return self.search_input.text().strip()

    def set_search_text(self, text: str):
        self.search_input.setText(text)
