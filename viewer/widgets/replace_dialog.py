from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QMessageBox
)
from ..utils.i18n import _


class ReplaceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("置換"))
        self.setModal(True)
        self.setFixedSize(450, 200)

        # UI部品の作成
        self.search_label = QLabel(_("検索文字列:"))
        self.search_input = QLineEdit()

        self.replace_label = QLabel(_("置換文字列:"))
        self.replace_input = QLineEdit()

        # オプション
        self.case_sensitive_check = QCheckBox(_("大文字・小文字を区別する"))
        self.whole_word_check = QCheckBox(_("単語単位で検索"))

        # ボタン
        self.replace_all_button = QPushButton(_("すべて置換"))
        self.preview_button = QPushButton(_("プレビュー"))
        self.cancel_button = QPushButton(_("キャンセル"))

        # イベント接続
        self.replace_all_button.clicked.connect(self.accept_replace_all)
        self.preview_button.clicked.connect(self.accept_preview)
        self.cancel_button.clicked.connect(self.reject)

        # レイアウト設定
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input)

        replace_layout = QHBoxLayout()
        replace_layout.addWidget(self.replace_label)
        replace_layout.addWidget(self.replace_input)

        options_layout = QVBoxLayout()
        options_layout.addWidget(self.case_sensitive_check)
        options_layout.addWidget(self.whole_word_check)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.preview_button)
        button_layout.addWidget(self.replace_all_button)
        button_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addLayout(search_layout)
        layout.addLayout(replace_layout)
        layout.addLayout(options_layout)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 結果を保存する変数
        self.result_type = None  # 'replace_all' または 'preview'

    def accept_replace_all(self):
        if not self.search_input.text().strip():
            QMessageBox.warning(self, _("入力エラー"), _("検索文字列を入力してください。"))
            return
        self.result_type = 'replace_all'
        self.accept()

    def accept_preview(self):
        if not self.search_input.text().strip():
            QMessageBox.warning(self, _("入力エラー"), _("検索文字列を入力してください。"))
            return
        self.result_type = 'preview'
        self.accept()

    def get_search_text(self):
        return self.search_input.text().strip()

    def get_replace_text(self):
        return self.replace_input.text()

    def is_case_sensitive(self):
        return self.case_sensitive_check.isChecked()

    def is_whole_word(self):
        return self.whole_word_check.isChecked()

    def get_result_type(self):
        return self.result_type

    def set_search_text(self, text: str):
        self.search_input.setText(text)

    def set_replace_text(self, text: str):
        self.replace_input.setText(text)
