"""
save_options_dialog.py - 保存時のエンコーディング・フォーマット選択ダイアログ

単独保存・分割保存の両方から呼び出される共通ダイアログ。
列詳細設定（任意）は headers を渡した場合のみ有効になる。
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDialogButtonBox, QGroupBox, QPushButton
)
from PyQt6.QtCore import Qt
from ..utils.i18n import _


# CSV / TSV / Excel / 各ロケール向けに使われうる文字コードを網羅したリスト
# (表示名, Pythonエンコーディング名, デフォルト区切り文字)
ENCODING_OPTIONS = [
    ("UTF-8 (BOMなし)",       "utf-8",        ","),
    ("UTF-8 BOM付き",         "utf-8-sig",    ","),
    ("Shift-JIS / CP932",     "cp932",        ","),
    ("EUC-JP",                "euc_jp",       ","),
    ("ISO-2022-JP (JIS)",     "iso2022_jp",   ","),
    ("UTF-16 (BOM付き)",      "utf-16",       ","),
    ("UTF-16 LE",             "utf-16-le",    ","),
    ("UTF-16 BE",             "utf-16-be",    ","),
    ("Windows-1252",          "cp1252",       ","),
    ("Latin-1",               "latin-1",      ","),
    ("GBK（中国語簡体字）",    "gbk",          ","),
    ("Big5（中国語繁体字）",   "big5",         ","),
    ("CP949（韓国語）",        "cp949",        ","),
]

FORMAT_OPTIONS = [
    ("CSV (.csv)  カンマ区切り", ".csv",  ","),
    ("TSV (.tsv)  タブ区切り",  ".tsv",  "\t"),
]

# Pythonエンコーディング名 → 表示名の逆引き辞書（翻訳済みラベルで引く）
def get_encoding_display(enc: str) -> str:
    for label, e, _bom in ENCODING_OPTIONS:
        if e == enc:
            return _(label)
    return enc


class SaveOptionsDialog(QDialog):
    """
    保存形式（文字コード・ファイル形式）を選択するダイアログ。

    Usage:
        dlg = SaveOptionsDialog(parent, default_encoding="utf-8-sig", headers=headers)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            enc   = dlg.encoding()         # e.g. "utf-8-sig"
            ext   = dlg.extension()        # e.g. ".csv"
            delim = dlg.delimiter()        # e.g. ","
            cols  = dlg.column_settings()  # list[dict] | None
    """

    def __init__(self, parent=None, default_encoding: str = "utf-8-sig",
                 headers: list[str] | None = None):
        super().__init__(parent)
        self._headers = headers or []
        self._column_settings: list[dict] | None = None  # 詳細設定結果（未設定は None）

        self.setWindowTitle(_("保存オプション"))
        self.setMinimumWidth(440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)

        # --- フォーマット選択 ---
        fmt_group = QGroupBox(_("ファイル形式"))
        fmt_layout = QHBoxLayout(fmt_group)
        self._format_combo = QComboBox()
        for label, ext, _delim in FORMAT_OPTIONS:
            self._format_combo.addItem(_(label), (ext, _delim))
        fmt_layout.addWidget(self._format_combo)
        layout.addWidget(fmt_group)

        # --- エンコーディング選択 ---
        enc_group = QGroupBox(_("文字コード（エンコーディング）"))
        enc_layout = QVBoxLayout(enc_group)
        enc_note = QLabel(_("※ 通常は「UTF-8 BOM付き」を推奨"))
        enc_note.setStyleSheet("color: #555; font-size: 11px;")
        enc_layout.addWidget(enc_note)
        self._enc_combo = QComboBox()
        default_idx = 0
        for i, (label, enc, _bom) in enumerate(ENCODING_OPTIONS):
            self._enc_combo.addItem(_(label), enc)
            if enc == default_encoding:
                default_idx = i
        self._enc_combo.setCurrentIndex(default_idx)
        enc_layout.addWidget(self._enc_combo)
        layout.addWidget(enc_group)

        # --- 列の詳細設定（任意・headers がある場合のみ表示）---
        if self._headers:
            detail_group = QGroupBox(_("列の詳細設定（任意）"))
            detail_layout = QHBoxLayout(detail_group)
            self._detail_status = QLabel(_("未設定（全列・元の列名・テキスト型で出力）"))
            self._detail_status.setStyleSheet("color: #777; font-size: 11px;")
            detail_btn = QPushButton(_("設定する..."))
            detail_btn.setFixedWidth(100)
            detail_btn.clicked.connect(self._open_column_settings)
            detail_layout.addWidget(self._detail_status, stretch=1)
            detail_layout.addWidget(detail_btn)
            layout.addWidget(detail_group)

        # --- OK / キャンセル ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # スロット
    # ------------------------------------------------------------------

    def _open_column_settings(self) -> None:
        from .column_settings_dialog import ColumnSettingsDialog
        dlg = ColumnSettingsDialog(self, headers=self._headers,
                                   initial_settings=self._column_settings)
        if dlg.exec() == ColumnSettingsDialog.DialogCode.Accepted:
            self._column_settings = dlg.get_settings()
            included = sum(1 for s in self._column_settings if s["include"])
            renamed = sum(
                1 for s, h in zip(self._column_settings, self._headers)
                if s["include"] and s["output_name"] != h
            )
            typed = sum(
                1 for s in self._column_settings
                if s["include"] and s["dtype"] != "text"
            )
            parts = [_("{included}/{total} 列を出力").format(included=included, total=len(self._headers))]
            if renamed:
                parts.append(_("{count} 列を列名変更").format(count=renamed))
            if typed:
                parts.append(_("{count} 列に型指定").format(count=typed))
            self._detail_status.setText(_("、").join(parts))
            self._detail_status.setStyleSheet("color: #1a6bb5; font-size: 11px; font-weight: bold;")

    # ------------------------------------------------------------------
    # 結果取得
    # ------------------------------------------------------------------

    def encoding(self) -> str:
        return self._enc_combo.currentData()

    def extension(self) -> str:
        return self._format_combo.currentData()[0]

    def delimiter(self) -> str:
        ext, delim = self._format_combo.currentData()
        return delim

    def column_settings(self) -> list[dict] | None:
        """列詳細設定を返す。「設定する」を開いていない場合は None。"""
        return self._column_settings
