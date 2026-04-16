"""
column_settings_dialog.py — 保存時の列詳細設定ダイアログ

出力する列の選択・出力時の列名変更・データ型の指定ができる。
SaveOptionsDialog から呼び出される任意オプション。
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLabel,
    QDialogButtonBox, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt


TYPE_OPTIONS = [
    ("テキスト（変換なし）", "text"),
    ("整数",               "int"),
    ("小数",               "float"),
]


class ColumnSettingsDialog(QDialog):
    """列ごとの出力設定を編集するダイアログ。

    Attributes:
        headers: 元のカラム名リスト（表示順）
    """

    def __init__(self, parent=None, headers: list[str] | None = None,
                 initial_settings: list[dict] | None = None):
        super().__init__(parent)
        self._headers = headers or []
        self._initial = initial_settings  # 前回設定の引き継ぎ用
        self.setWindowTitle("列の詳細設定")
        self.setMinimumSize(640, 460)
        self.resize(700, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._combos: list[QComboBox] = []
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        note = QLabel(
            "保存する列の選択・列名の変更・データ型の指定ができます（任意）。\n"
            "型を指定すると保存時に変換を試みます。変換できない値はそのまま出力されます。"
        )
        note.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(note)

        # 一括操作ボタン
        btn_row = QHBoxLayout()
        btn_all = QPushButton("全列選択")
        btn_none = QPushButton("全列解除")
        btn_reset = QPushButton("列名をリセット")
        btn_all.clicked.connect(self._select_all)
        btn_none.clicked.connect(self._deselect_all)
        btn_reset.clicked.connect(self._reset_names)
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # カラム設定テーブル
        self._table = QTableWidget(len(self._headers), 4)
        self._table.setHorizontalHeaderLabels(["出力", "元の列名", "出力列名", "型"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._table.setColumnWidth(1, 160)

        init = self._initial or [{}] * len(self._headers)

        for row, name in enumerate(self._headers):
            prev = init[row] if row < len(init) else {}

            # 出力チェック
            chk = QTableWidgetItem()
            chk.setCheckState(
                Qt.CheckState.Checked if prev.get("include", True) else Qt.CheckState.Unchecked
            )
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, chk)

            # 元の列名（読み取り専用・グレー）
            orig = QTableWidgetItem(name)
            orig.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            orig.setForeground(Qt.GlobalColor.gray)
            self._table.setItem(row, 1, orig)

            # 出力列名（編集可）
            out_item = QTableWidgetItem(prev.get("output_name", name))
            self._table.setItem(row, 2, out_item)

            # 型コンボ
            combo = QComboBox()
            for label, val in TYPE_OPTIONS:
                combo.addItem(label, val)
            prev_dtype = prev.get("dtype", "text")
            for i, (_, val) in enumerate(TYPE_OPTIONS):
                if val == prev_dtype:
                    combo.setCurrentIndex(i)
                    break
            self._table.setCellWidget(row, 3, combo)
            self._combos.append(combo)

        layout.addWidget(self._table)

        # OK / キャンセル
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ------------------------------------------------------------------
    # スロット
    # ------------------------------------------------------------------

    def _select_all(self) -> None:
        for row in range(self._table.rowCount()):
            self._table.item(row, 0).setCheckState(Qt.CheckState.Checked)

    def _deselect_all(self) -> None:
        for row in range(self._table.rowCount()):
            self._table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)

    def _reset_names(self) -> None:
        for row, name in enumerate(self._headers):
            self._table.item(row, 2).setText(name)

    def _on_accept(self) -> None:
        # 出力列が 0 件の場合は警告
        included = sum(
            1 for row in range(self._table.rowCount())
            if self._table.item(row, 0).checkState() == Qt.CheckState.Checked
        )
        if included == 0:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "入力エラー", "出力する列を1つ以上選択してください。")
            return
        self.accept()

    # ------------------------------------------------------------------
    # 結果取得
    # ------------------------------------------------------------------

    def get_settings(self) -> list[dict]:
        """各列の設定を返す。

        Returns:
            [{"include": bool, "output_name": str, "dtype": str}, ...]
            元の列インデックスと対応している。
        """
        result = []
        for row in range(self._table.rowCount()):
            include = self._table.item(row, 0).checkState() == Qt.CheckState.Checked
            output_name = self._table.item(row, 2).text().strip() or self._headers[row]
            dtype = self._combos[row].currentData()
            result.append({"include": include, "output_name": output_name, "dtype": dtype})
        return result
