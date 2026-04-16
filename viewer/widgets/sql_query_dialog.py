import csv
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPlainTextEdit, QPushButton, QListWidget, QListWidgetItem, QTableView,
    QComboBox, QMessageBox, QFileDialog, QSizePolicy, QWidget
)
from PyQt6.QtSql import QSqlDatabase, QSqlQueryModel
from PyQt6.QtGui import QFont, QColor, QKeySequence, QShortcut
from PyQt6.QtCore import Qt
from ..utils.i18n import _

logger = logging.getLogger(__name__)


class SqlQueryDialog(QDialog):
    def __init__(self, parent, db_path: str, connection_name: str, column_names: list):
        super().__init__(parent)
        self.db_path = db_path
        self.connection_name = connection_name
        self.column_names = column_names
        self._current_model = None

        self.setWindowTitle(_("SQLクエリ実行"))
        self.setMinimumSize(900, 600)

        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 水平スプリッター（左: スキーマ / 右: エディタ＋結果）
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- 左パネル: スキーマ情報 ----
        left_widget = QVBoxLayout()
        left_widget_container = self._make_widget(left_widget)
        left_widget_container.setFixedWidth(200)

        left_widget.addWidget(QLabel(_("ダブルクリックで挿入")))

        self.column_list = QListWidget()

        # テーブル名アイテム
        tbl_item = QListWidgetItem("csv_data")
        tbl_font = QFont()
        tbl_font.setBold(True)
        tbl_item.setFont(tbl_font)
        tbl_item.setForeground(QColor("#1a6bb5"))
        tbl_item.setToolTip(_("テーブル名"))
        self.column_list.addItem(tbl_item)

        # 区切り線アイテム（選択不可）
        sep_item = QListWidgetItem(_("── 列 ──"))
        sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
        sep_item.setForeground(QColor("#999999"))
        self.column_list.addItem(sep_item)

        # 列名アイテム
        for col in self.column_names:
            self.column_list.addItem(QListWidgetItem(col))

        self.column_list.itemDoubleClicked.connect(self._insert_column_name)
        left_widget.addWidget(self.column_list)

        h_splitter.addWidget(left_widget_container)

        # ---- 右パネル: 垂直スプリッター ----
        v_splitter = QSplitter(Qt.Orientation.Vertical)

        # -- 上部: SQLエディタエリア --
        editor_container_layout = QVBoxLayout()
        editor_container = self._make_widget(editor_container_layout)

        # SQLラベル＋履歴コンボ＋クリアボタン
        editor_top_layout = QHBoxLayout()
        sql_label = QLabel("SQL")
        editor_top_layout.addWidget(sql_label)

        self.history_combo = QComboBox()
        self.history_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.history_combo.currentIndexChanged.connect(self._load_history)
        editor_top_layout.addWidget(self.history_combo)

        clear_button = QPushButton(_("クリア"))
        clear_button.clicked.connect(self._clear_editor)
        editor_top_layout.addWidget(clear_button)

        editor_container_layout.addLayout(editor_top_layout)

        # SQLエディタ
        self.sql_editor = QPlainTextEdit()
        mono_font = QFont("Courier New", 10)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.sql_editor.setFont(mono_font)
        self.sql_editor.setMinimumHeight(150)
        editor_container_layout.addWidget(self.sql_editor)

        v_splitter.addWidget(editor_container)

        # -- ツールバー行 --
        toolbar_layout = QHBoxLayout()
        toolbar_container = self._make_widget(toolbar_layout)

        execute_button = QPushButton(_("▶ 実行 (F5)"))
        execute_button.clicked.connect(self.execute_query)
        toolbar_layout.addWidget(execute_button)

        self.row_count_label = QLabel(_("0 行"))
        toolbar_layout.addWidget(self.row_count_label)

        toolbar_layout.addStretch()

        export_button = QPushButton(_("結果をCSVで保存"))
        export_button.clicked.connect(self._export_to_csv)
        toolbar_layout.addWidget(export_button)

        v_splitter.addWidget(toolbar_container)

        # -- 下部: 結果表示エリア --
        result_container_layout = QVBoxLayout()
        result_container = self._make_widget(result_container_layout)

        self.result_view = QTableView()
        self.result_view.setAlternatingRowColors(True)
        result_container_layout.addWidget(self.result_view)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setVisible(False)
        self.error_label.setWordWrap(True)
        result_container_layout.addWidget(self.error_label)

        v_splitter.addWidget(result_container)

        h_splitter.addWidget(v_splitter)

        main_layout.addWidget(h_splitter)

    def _make_widget(self, layout):
        """レイアウトをラップする QWidget を作成して返す"""
        w = QWidget()
        w.setLayout(layout)
        return w

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F5"), self).activated.connect(self.execute_query)

    def _clear_editor(self):
        self.sql_editor.clear()

    def execute_query(self):
        """SQLを実行して result_view に結果を表示する"""
        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            return

        db = QSqlDatabase.database(self.connection_name)
        if not db.isOpen():
            self.error_label.setText(_("データベース接続が開いていません。"))
            self.error_label.setVisible(True)
            return

        model = QSqlQueryModel()
        model.setQuery(sql, db)

        if model.lastError().isValid():
            error_text = model.lastError().text()
            logger.warning("SQL実行エラー: %s", error_text)
            self.error_label.setText(_("エラー: {msg}").format(msg=error_text))
            self.error_label.setVisible(True)
            return

        self.result_view.setModel(None)
        self._current_model = model
        self.result_view.setModel(model)

        # QSqlQueryModel は select() 完了まで rowCount が確定しないことがある
        # fetchMore を全部呼び出して件数を確定させる
        while model.canFetchMore():
            model.fetchMore()

        row_count = model.rowCount()
        self.row_count_label.setText(_("{n} 行").format(n=row_count))
        self.error_label.setVisible(False)

        # 履歴更新: 同じSQLが既にあれば先頭に移動、なければ先頭追加（最大10件）
        self.history_combo.blockSignals(True)
        existing_index = -1
        for i in range(self.history_combo.count()):
            if self.history_combo.itemText(i) == sql:
                existing_index = i
                break

        if existing_index >= 0:
            self.history_combo.removeItem(existing_index)

        self.history_combo.insertItem(0, sql)

        # 最大10件に制限
        while self.history_combo.count() > 10:
            self.history_combo.removeItem(self.history_combo.count() - 1)

        self.history_combo.setCurrentIndex(0)
        self.history_combo.blockSignals(False)

    def _insert_column_name(self, item):
        """テーブル名または列名をダブルクリックでSQLエディタのカーソル位置に挿入"""
        # 区切り線アイテムは無視
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        text = item.text()
        # テーブル名はそのまま、列名はダブルクォートで囲む
        insert_text = text if item.toolTip() == _("テーブル名") else f'"{text}"'
        cursor = self.sql_editor.textCursor()
        cursor.insertText(insert_text)
        self.sql_editor.setTextCursor(cursor)
        self.sql_editor.setFocus()

    def _load_history(self, index):
        """履歴コンボボックスから選択してエディタにセット"""
        if index < 0:
            return
        sql = self.history_combo.itemText(index)
        if sql:
            self.sql_editor.setPlainText(sql)

    def _export_to_csv(self):
        """result_view の現在モデルをCSVファイルに保存する"""
        if self._current_model is None:
            QMessageBox.warning(self, _("警告"), _("保存するデータがありません。先にSQLを実行してください。"))
            return

        file_path, _flt = QFileDialog.getSaveFileName(
            self,
            _("CSVファイルを保存"),
            "",
            _("CSV ファイル (*.csv);;すべてのファイル (*)")
        )
        if not file_path:
            return

        try:
            model = self._current_model

            # 全行をフェッチ
            while model.canFetchMore():
                model.fetchMore()

            col_count = model.columnCount()
            row_count = model.rowCount()

            headers = [
                model.headerData(col, Qt.Orientation.Horizontal)
                for col in range(col_count)
            ]

            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in range(row_count):
                    row_data = [
                        model.data(model.index(row, col))
                        for col in range(col_count)
                    ]
                    writer.writerow(row_data)

            QMessageBox.information(self, _("保存完了"), _("CSVファイルを保存しました:\n{path}").format(path=file_path))
            logger.info("SQLクエリ結果をCSVに保存しました: %s", file_path)

        except Exception as e:
            error_msg = f"CSV保存中にエラーが発生しました:\n{str(e)}"
            logger.error("CSV保存エラー: %s", error_msg)
            QMessageBox.critical(self, _("エラー"), error_msg)
