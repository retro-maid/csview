from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QMessageBox, QFileDialog, QHBoxLayout, QStatusBar, QProgressDialog,
    QLabel, QLineEdit, QGroupBox, QHeaderView, QStackedLayout, QTabWidget,
    QProgressBar, QPushButton, QAbstractItemView, QInputDialog, QTableView, QStyle
)
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QIcon
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel, QSqlQueryModel, QSqlQuery
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from converter.convert_csv import convert_csv_to_sqlite, build_fts5_index, detect_encoding as detect_csv_encoding, estimate_row_count, PROGRESSIVE_ROWS
from .widgets.save_current_view import save_current_view
from .widgets.split_current_view import split_current_view
from .widgets.search_dialog import SearchDialog
from .widgets.replace_dialog import ReplaceDialog
from .widgets.filter_dialog import FilterDialog
from .widgets.highlight_delegate import HighlightDelegate
from .widgets.settings_dialog import SettingsDialog, load_config, save_config
from .widgets.merge_csv import merge_zip_csv_to_database
from .widgets.sql_query_dialog import SqlQueryDialog
from .utils.config import load_app_info, load_previous_version, save_current_version, resource_path
from .utils.i18n import _, set_lang
import sys, os, tempfile, time, re, logging, sqlite3 as _sqlite3, glob, atexit, csv as _csv_module
import unicodedata
from pathlib import Path
import traceback
from collections import deque

logger = logging.getLogger(__name__)

# セッション内で作成した一時DBパスを追跡する。
# クラッシュ・強制終了時に atexit で削除を試みる。
_session_dbs: set[str] = set()


def _remove_db_files(path: str, retries: int = 3, delay: float = 0.1) -> None:
    """DB本体・WAL・SHMを最大 retries 回リトライして削除する。"""
    for suffix in ("", "-wal", "-shm"):
        target = path + suffix
        for _ in range(retries):
            try:
                if os.path.exists(target):
                    os.remove(target)
                break
            except OSError:
                time.sleep(delay)


def _atexit_cleanup_dbs() -> None:
    for path in list(_session_dbs):
        _remove_db_files(path)

atexit.register(_atexit_cleanup_dbs)


class CsvLoadThread(QThread):
    progress = pyqtSignal(int)
    total_rows_ready = pyqtSignal(int)    # 変換開始前に総行数推定値を通知
    partial_ready = pyqtSignal()          # PROGRESSIVE_ROWS 挿入後に emit
    finished = pyqtSignal(str, str)       # db_path, csv_path
    failed = pyqtSignal(str)

    def __init__(self, csv_path, db_path):
        super().__init__()
        self.csv_path = csv_path
        self.db_path = db_path

    def run(self):
        try:
            if not Path(self.csv_path).exists():
                self.failed.emit(f"ファイルが見つかりません: {self.csv_path}")
                return

            # 変換前に総行数を推定してUIへ通知（瞬時完了）
            estimated = estimate_row_count(self.csv_path)
            if estimated > 0:
                self.total_rows_ready.emit(estimated)

            convert_csv_to_sqlite(
                self.csv_path,
                self.db_path,
                self.progress,
                partial_ready_callback=lambda: self.partial_ready.emit(),
            )
            self.finished.emit(self.db_path, self.csv_path)

        except UnicodeDecodeError as e:
            self.failed.emit(f"文字エンコーディングエラー: {str(e)}\nファイルのエンコーディングを確認してください。")
        except PermissionError as e:
            self.failed.emit(f"ファイルアクセス権限エラー: {str(e)}\nファイルが他のアプリケーションで使用されていないか確認してください。")
        except Exception as e:
            error_msg = f"CSV変換エラー: {str(e)}"
            logger.error("CsvLoadThread error: %s", error_msg)
            self.failed.emit(error_msg)


class Fts5BuildThread(QThread):
    """FTS5インデックスをバックグラウンドで構築するスレッド"""
    finished = pyqtSignal(bool)   # 構築成功なら True
    progress = pyqtSignal(int)    # 進捗 0〜100

    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        success = build_fts5_index(
            self.db_path,
            progress_callback=lambda pct: self.progress.emit(pct),
            cancelled_flag=lambda: self._cancelled,
        )
        self.finished.emit(success)


def launch_editor():
    _cfg = load_config()
    set_lang(_cfg.get("language", "ja"))
    try:
        app = QApplication(sys.argv)

        icon_path = resource_path("assets/app_icon.ico")
        app.setWindowIcon(QIcon(icon_path))

        window = CsvEditor()

        # コマンドライン引数でCSVファイルを受け取っていたら開く
        if len(sys.argv) > 1:
            csv_path = sys.argv[1]
            if os.path.exists(csv_path) and csv_path.lower().endswith((".csv", ".tsv")):
                window.load_csv_file(csv_path)

        window.show()
        sys.exit(app.exec())
    except Exception as e:
        log_dir = Path.home() / ".csview"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "error_log.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())


class TabData:
    """タブごとのデータを管理するクラス"""
    def __init__(self, csv_path, db_path, connection_name):
        self.csv_path = csv_path
        self.db_path = db_path
        self.connection_name = connection_name
        self.db = None
        self.model = None
        self.view = None
        self.total_csv_rows = 0
        self.csv_encoding = None
        self.start_time = 0
        self.load_elapsed_time = 0
        self.in_search_mode = False
        self.last_search_keyword = ""
        self.current_condition = _("なし")
        self.actual_row_count = None   # 検索・フィルター結果の件数（None = 全件表示）
        self.undo_stack = deque(maxlen=20)
        self.view_stack = deque(maxlen=10)
        self.highlight_delegate = None
        self.replaced_cells = []  # 置換されたセルの位置を記録
        self.fts_enabled = False     # FTS5構築完了後に True になる
        self.file_size = 0           # 元CSVのファイルサイズ (bytes)
        self.edited_cells: set = set()  # 編集済みセル (row, col) のセット
        self.user_renamed_tab = False  # ユーザーがタブ名を手動変更した場合は True

    def set_search_state(self, condition: str, count) -> None:
        """検索・フィルター後の状態を一括設定する。3フィールドの同期漏れを防ぐ。"""
        self.in_search_mode = True
        self.current_condition = condition
        self.actual_row_count = count

    def clear_search_state(self, condition: str = None) -> None:
        """全件表示に戻す際の状態をリセットする。"""
        self.in_search_mode = False
        self.current_condition = condition if condition is not None else _("なし")
        self.actual_row_count = None


class CsvEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSView")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        # 起動時: 前回クラッシュ・強制終了で残留した一時DBを削除する。
        # 別インスタンスが使用中のファイルは Windows がロックするため PermissionError になり
        # スキップされる（安全）。
        for _stale in glob.glob(os.path.join(tempfile.gettempdir(), "csv_editor_*.db")):
            try:
                os.remove(_stale)
            except OSError:
                pass

        self.settings = load_config()
        self.tabs_data = []  # TabDataのリスト
        self._shortcuts: dict = {}  # キー: action名, 値: QShortcut

        # 読み込み中フラグ
        self.is_loading = False
        self.progress_dialog = None
        self.csv_thread = None
        self.fts_thread = None
        self._orphan_fts_threads: list = []  # タブ削除後も動き続けるFTS5スレッドを保持
        self._pending_tab_data = None  # partial_ready で追加されたタブを追跡
        self._loading_refresh_timer = None  # 変換中の定期リフレッシュタイマー
        self._progressive_start_time = 0.0   # プログレッシブ表示開始時刻（ETA計算用）
        self._progressive_start_rows = 0     # プログレッシブ表示開始時の行数（ETA計算用）

        # タブウィジェット
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)   # ドラッグによる並び替えを有効化
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.tabBar().tabMoved.connect(self._on_tab_moved)
        self.tab_widget.tabBar().tabBarDoubleClicked.connect(self._on_tab_double_clicked)

        # 上部情報バーと条件表示
        top_layout = QVBoxLayout()
        top_layout.addWidget(self._create_info_bar())
        self.query_label = QLabel(_("現在の条件: なし"))
        self.query_label.setStyleSheet("padding: 4px; font-weight: bold; color: #333;")
        top_layout.addWidget(self.query_label)

        # ドロップ用のラベル（初期表示）
        self.drop_label = QLabel(_("ここに CSV / TSV ファイルをドラッグ＆ドロップしてください"))
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("font-size: 18px; color: #999;")

        self.drop_widget = QWidget()
        drop_layout = QVBoxLayout(self.drop_widget)
        drop_layout.addStretch()
        drop_layout.addWidget(self.drop_label, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addStretch()

        # スタックレイアウト（初期表示用ドロップエリアとタブウィジェット）
        self.stack_layout = QStackedLayout()
        self.stack_layout.addWidget(self.drop_widget)  # index 0
        self.stack_layout.addWidget(self.tab_widget)   # index 1

        # 全体レイアウトをまとめる
        full_layout = QVBoxLayout()
        full_layout.addLayout(top_layout)
        full_layout.addLayout(self.stack_layout)

        container = QWidget()
        container.setLayout(full_layout)
        self.setCentralWidget(container)

        self._setup_menu()
        self._setup_shortcuts()

        # フッタープログレスバー（プログレッシブ表示中のみ表示）
        self._footer_progress_label = QLabel()
        self._footer_progress_label.setVisible(False)
        self._footer_progress_bar = QProgressBar()
        self._footer_progress_bar.setFixedWidth(220)
        self._footer_progress_bar.setFixedHeight(16)
        self._footer_progress_bar.setRange(0, 100)
        self._footer_progress_bar.setVisible(False)
        footer_status = QStatusBar()
        footer_status.addPermanentWidget(self._footer_progress_label)
        footer_status.addPermanentWidget(self._footer_progress_bar)
        self.setStatusBar(footer_status)

        self.apply_user_settings()

        try:
            from .utils._diag import check_session_health as _csh
            _m = _csh()
            if _m:
                QTimer.singleShot(1800, lambda m=_m: self.statusBar().showMessage(m, 14000))
        except Exception:
            pass

    def _create_info_bar(self):
        keys = [_("ファイル名"), _("容量"), _("エンコーディング"), _("全体行数"), _("読み込み時間")]
        self.info_fields = {k: QLineEdit(readOnly=True, maximumHeight=25) for k in keys}

        self.overwrite_btn = QPushButton()
        self.overwrite_btn.setIcon(
            QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        )
        self.overwrite_btn.setToolTip(_("上書き保存 (Ctrl+S)"))
        self.overwrite_btn.setFixedSize(36, 28)
        self.overwrite_btn.setEnabled(False)
        self.overwrite_btn.clicked.connect(self.overwrite_csv)

        hl = QHBoxLayout()
        hl.addWidget(self.overwrite_btn)
        for label, field in self.info_fields.items():
            hl.addWidget(QLabel(label))
            hl.addWidget(field)
        group = QGroupBox(_("ファイル情報"))
        group.setLayout(hl)
        return group

    def _setup_menu(self):
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu(_("ファイル"))
        file_menu.addAction(QAction(_("開く"), self, triggered=self.open_file))
        self.recent_menu = file_menu.addMenu(_("最近使ったファイル"))
        self._rebuild_recent_files_menu()
        self.save_action = QAction(_("名前を付けて保存"), self, triggered=self.save_current_view_triggered)
        self.split_save_action = QAction(_("名前を付けて分割して保存"), self, triggered=self.split_current_view_triggered)
        self.merge_zip_action  = QAction(_("csvを結合して開く"), self, triggered=self.merge_zip_csv_triggered)

        file_menu.addAction(self.save_action)
        file_menu.addAction(self.split_save_action)
        file_menu.addAction(self.merge_zip_action)
        file_menu.addAction(QAction(_("設定"), self, triggered=self.show_settings_dialog))

        # ツールメニュー
        tool_menu = menubar.addMenu(_("ツール"))
        self.search_action = QAction(_("検索"), self, triggered=self.open_search_dialog)
        self.replace_action = QAction(_("置換"), self, triggered=self.open_replace_dialog)
        self.filter_action = QAction(_("条件抽出"), self, triggered=self.open_filter_dialog)
        self.reset_action = QAction(_("元に戻す（全件表示）"), self, triggered=self.reset_to_full_view)

        tool_menu.addAction(self.search_action)
        tool_menu.addAction(self.replace_action)
        tool_menu.addAction(self.filter_action)
        tool_menu.addAction(self.reset_action)
        tool_menu.addSeparator()
        self.sql_query_action = QAction(_("SQLクエリ実行"), self, triggered=self.open_sql_query_dialog)
        tool_menu.addAction(self.sql_query_action)

        #  初期状態でデータ依存メニューを無効化
        self.update_menu_state()
    
    def update_menu_state(self):
        """メニューアイテムの有効/無効状態を更新"""
        # プログレッシブ表示中（partial_ready 後）はメニューを有効化して警告ダイアログで案内する
        has_data = bool(self.tabs_data and (not self.is_loading or self._pending_tab_data is not None))
        
        # データが必要なアクションを制御
        data_dependent_actions = [
            self.save_action,
            self.split_save_action,
            self.search_action,
            self.replace_action,
            self.filter_action,
            self.reset_action,
            self.sql_query_action,
        ]

        for action in data_dependent_actions:
            action.setEnabled(has_data)

        # 上書き保存ボタンは全件表示（QSqlTableModel）かつCSVパスが有効な場合のみ有効
        tab_data = self.get_current_tab_data()
        overwrite_available = (
            has_data
            and tab_data is not None
            and isinstance(tab_data.model, QSqlTableModel)
            and bool(tab_data.csv_path)
            and os.path.exists(tab_data.csv_path)
        )
        self.overwrite_btn.setEnabled(overwrite_available)

    def _warn_if_converting(self) -> bool:
        """
        プログレッシブ変換継続中に警告ダイアログを表示する。
        ユーザーが「続行」を選んだ場合 True、「キャンセル」なら False を返す。
        変換中でなければ即 True を返す。
        """
        if self._pending_tab_data is None:
            return True
        result = QMessageBox.warning(
            self,
            _("変換処理が継続中です"),
            _("現在CSVの変換処理が継続中のため、表示されているデータは全件ではありません。\n"
              "この状態で操作を実行すると、不完全なデータが対象となり結果が不正確になる可能性があります。\n\n"
              "変換が完了してから実行することを推奨します。\n\n"
              "続行しますか？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _warn_if_converting_strong(self) -> bool:
        """
        分割保存など不可逆操作向けの強い警告ダイアログ。
        ユーザーが「続行」を選んだ場合 True、「キャンセル」なら False を返す。
        """
        if self._pending_tab_data is None:
            return True
        result = QMessageBox.critical(
            self,
            _("⚠ 警告: データが不完全な状態です"),
            _("【重要】現在CSVの変換処理が継続中のため、データは不完全な状態です。\n\n"
              "この状態で分割保存を実行すると:\n"
              "  • 変換済みの行のみが保存されます\n"
              "  • 全データを含まない不完全なファイルが生成されます\n"
              "  • 後からデータを追加する手段はありません\n\n"
              "変換が完了するまで待ってから実行することを強く推奨します。\n\n"
              "本当に続行しますか？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _setup_shortcuts(self):
        self._rebuild_shortcuts()

    def _rebuild_shortcuts(self):
        """設定からショートカットキーを再構築する。設定変更後に呼び出す。"""
        for sc in self._shortcuts.values():
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts.clear()

        cfg = self.settings.get("shortcuts", {})

        _defs = [
            ("undo",          "Ctrl+Z",       self.undo_last_action),
            ("replace",       "Ctrl+H",       self.open_replace_dialog),
            ("copy",          "Ctrl+C",       self.copy_selection),
            ("sql_query",     "Ctrl+Shift+Q", self.open_sql_query_dialog),
            ("overwrite_save","Ctrl+S",       self.overwrite_csv),
        ]
        for key, default, slot in _defs:
            seq_str = cfg.get(key, default)
            if seq_str:
                sc = QShortcut(QKeySequence(seq_str), self)
                sc.activated.connect(slot)
                self._shortcuts[key] = sc


    def set_ui_enabled(self, enabled):
        """UI要素の有効/無効を切り替える"""
        self.menuBar().setEnabled(enabled)
        self.tab_widget.setEnabled(enabled)
        # ドラッグ&ドロップも制御
        self.setAcceptDrops(enabled)
        
        #  読み込み中でない場合のみメニュー状態を更新
        if enabled:
            self.update_menu_state()

    def get_current_tab_data(self):
        """現在アクティブなタブのTabDataを取得"""
        current_index = self.tab_widget.currentIndex()
        if current_index < 0 or current_index >= len(self.tabs_data):
            return None
        return self.tabs_data[current_index]

    def on_tab_changed(self, index):
        """タブが切り替わった時の処理"""
        if not self.is_loading:
            self.update_info_display()
            self.update_menu_state()

    def update_info_display(self):
        """情報バーと条件表示を更新（日本語ファイル名対応）"""
        tab_data = self.get_current_tab_data()
        if not tab_data:
            # タブがない場合は情報をクリア
            for field in self.info_fields.values():
                field.setText("")
            self.query_label.setText(_("現在の条件: なし"))
            return

        try:
            #  ファイルパス処理の安全化
            file_path = Path(tab_data.csv_path)

            # ファイル情報を更新
            self.info_fields[_("ファイル名")].setText(file_path.name)

            # ファイルサイズ計算（エラーハンドリング付き）
            try:
                file_size_gb = file_path.stat().st_size / (1024**3)
                self.info_fields[_("容量")].setText(f"{file_size_gb:.2f} GB")
            except Exception as e:
                self.info_fields[_("容量")].setText(_("計算不可"))
                logger.warning("ファイルサイズ計算エラー: %s", e)

            self.info_fields[_("エンコーディング")].setText(tab_data.csv_encoding or _("不明"))
            self.info_fields[_("全体行数")].setText(f"{tab_data.total_csv_rows:,}")
            self.info_fields[_("読み込み時間")].setText(_("{sec:.2f} 秒").format(sec=tab_data.load_elapsed_time))

            # 現在の条件表示を更新
            self.update_query_label()

        except Exception as e:
            logger.warning("情報表示更新エラー: %s", e)
            # エラー時は空の値を設定
            for field in self.info_fields.values():
                field.setText(_("エラー"))

    def update_query_label(self):
        """条件ラベルを更新する専用メソッド"""
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            self.query_label.setText(_("現在の条件: なし"))
            return

        # 保存された実際の件数がある場合はそれを使用
        if tab_data.actual_row_count is not None:
            row_count = tab_data.actual_row_count
        elif isinstance(tab_data.model, QSqlTableModel) and tab_data.total_csv_rows > 0:
            # 全件表示時はCSV変換時に記録した行数を使用（fetchMoreなしで正確な値）
            row_count = tab_data.total_csv_rows
        else:
            row_count = self.get_model_row_count(tab_data.model)
        
        # 条件テキストを構築
        condition_text = tab_data.current_condition
        self.query_label.setText(_("現在の条件: {condition}　｜　該当件数: {count:,} 件").format(condition=condition_text, count=row_count))

    def get_model_row_count(self, model):
        """モデルの現在ロード済み行数を取得"""
        if not model:
            return 0
        return model.rowCount()

    def normalize_file_path(self, file_path):
        """ファイルパスの正規化（日本語対応）"""
        try:
            # Pathlibを使用してパスを正規化
            path = Path(file_path).resolve()
            
            # Unicodeの正規化（NFCに統一）
            normalized_path = unicodedata.normalize('NFC', str(path))
            
            return normalized_path
        except Exception as e:
            logger.warning("パス正規化エラー: %s", e)
            return file_path
        
    def validate_csv_file(self, file_path):
        """CSVファイルの妥当性チェック"""
        try:
            path = Path(file_path)
            
            # ファイル存在チェック
            if not path.exists():
                return False, f"ファイルが存在しません: {file_path}"
            
            # ファイルサイズチェック（0バイトファイル）
            if path.stat().st_size == 0:
                return False, "ファイルが空です"
            
            # 読み取り権限チェック
            if not os.access(path, os.R_OK):
                return False, "ファイルの読み取り権限がありません"
            
            # ファイル拡張子チェック
            if path.suffix.lower() not in ['.csv', '.tsv']:
                return False, f"サポートされていないファイル形式: {path.suffix}"
            
            return True, "OK"
            
        except Exception as e:
            return False, f"ファイル検証エラー: {str(e)}"

    def create_safe_temp_path(self, original_path):
        """安全な一時ファイルパスを作成"""
        try:
            # ファイル名から日本語を含む安全な名前を生成
            path = Path(original_path)
            base_name = path.stem
            
            # ファイル名をASCII安全な形式に変換
            safe_name = unicodedata.normalize('NFKD', base_name)
            safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '-_').rstrip()
            
            # 空になった場合のフォールバック
            if not safe_name:
                safe_name = "csv_file"
            
            # タイムスタンプを追加して一意性を確保
            timestamp = int(time.time() * 1000)
            temp_name = f"csv_editor_{safe_name}_{timestamp}.db"
            
            path = os.path.join(tempfile.gettempdir(), temp_name)
            _session_dbs.add(path)
            return path

        except Exception as e:
            logger.warning("一時パス作成エラー: %s", e)
            path = os.path.join(tempfile.gettempdir(), f"csv_editor_temp_{int(time.time()*1000)}.db")
            _session_dbs.add(path)
            return path

    def open_file(self):
        """ファイルオープンダイアログ（日本語ファイル名対応）"""
        if self.is_loading:
            return
            
        try:
            #  ファイルダイアログのエンコーディング対応
            path, _flt = QFileDialog.getOpenFileName(
                self,
                _("CSVファイルを選択"),
                "",
                _("CSV Files (*.csv *.tsv);;All Files (*.*)")
            )
            
            if path:
                # ファイルパスの正規化と読み込み
                normalized_path = self.normalize_file_path(path)
                self.load_csv_file(normalized_path)
                
        except Exception as e:
            error_msg = f"ファイル選択中にエラーが発生しました:\n{str(e)}"
            QMessageBox.critical(self, _("エラー"), error_msg)
    
    def open_sql_query_dialog(self):
        """SQLクエリ実行ダイアログを開く"""
        if self.is_loading and self._pending_tab_data is None:
            return
        if not self._warn_if_converting():
            return
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            return
        column_names = [
            tab_data.model.headerData(i, Qt.Orientation.Horizontal)
            for i in range(tab_data.model.columnCount())
        ]
        dialog = SqlQueryDialog(self, tab_data.db_path, tab_data.connection_name, column_names)
        dialog.exec()

    def dragEnterEvent(self, event):
        """ドラッグ&ドロップ開始（日本語ファイル名対応）"""
        if self.is_loading:
            event.ignore()
            return
            
        if event.mimeData().hasUrls():
            valid_files = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                try:
                    #  ファイルパス正規化と検証
                    normalized_path = self.normalize_file_path(file_path)
                    is_valid, _msg = self.validate_csv_file(normalized_path)
                    if is_valid:
                        valid_files.append(normalized_path)
                except Exception as e:
                    logger.warning("ドラッグファイル検証エラー: %s", e)
                    continue
            
            if valid_files:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        """ドロップイベント（日本語ファイル名対応）"""
        if self.is_loading:
            return
            
        try:
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                try:
                    #  ファイルパス正規化と検証
                    normalized_path = self.normalize_file_path(file_path)
                    is_valid, error_msg = self.validate_csv_file(normalized_path)
                    
                    if is_valid:
                        self.load_csv_file(normalized_path)
                        break  # 最初の有効なファイルのみ処理
                    else:
                        logger.debug("無効なファイル: %s", error_msg)
                        
                except Exception as e:
                    logger.warning("ドロップファイル処理エラー: %s", e)
                    continue
                    
        except Exception as e:
            error_msg = f"ファイルドロップ処理中にエラーが発生しました:\n{str(e)}"
            QMessageBox.warning(self, _("警告"), error_msg)

    def load_csv_file(self, path):
        """CSVファイル読み込み（日本語ファイル名対応版）"""
        if self.is_loading:
            return

        try:
            #  ファイルパスの正規化
            normalized_path = self.normalize_file_path(path)
            
            #  ファイル妥当性チェック
            is_valid, error_msg = self.validate_csv_file(normalized_path)
            if not is_valid:
                QMessageBox.critical(self, _("ファイルエラー"), error_msg)
                return

            # 読み込み開始
            self.is_loading = True
            self.set_ui_enabled(False)
            
            #  安全な一時ファイルパス生成
            db_path = self.create_safe_temp_path(normalized_path)
            
            # TabDataを作成
            connection_name = f"conn_{int(time.time()*1000)}"
            tab_data = TabData(normalized_path, db_path, connection_name)
            
            tab_data.csv_encoding = detect_csv_encoding(normalized_path)
            tab_data.start_time = time.time()

            # 統一プログレスダイアログ
            self.progress_dialog = QProgressDialog(_("処理中..."), _("キャンセル"), 0, 100, self)
            self.progress_dialog.setWindowTitle(_("CSVファイル読み込み"))
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setAutoClose(False)
            self.progress_dialog.setAutoReset(False)
            self.progress_dialog.canceled.connect(self.cancel_loading)
            self.progress_dialog.show()

            # CSV→SQLite変換スレッド開始
            tab_data.file_size = os.path.getsize(normalized_path)
            self.csv_thread = CsvLoadThread(normalized_path, db_path)
            self.csv_thread.total_rows_ready.connect(lambda n, td=tab_data: setattr(td, 'total_csv_rows', n))
            self.csv_thread.progress.connect(self.update_csv_progress)
            self.csv_thread.partial_ready.connect(lambda: self._on_partial_ready(tab_data))
            self.csv_thread.finished.connect(lambda db, csv: self._on_csv_finished(tab_data))
            self.csv_thread.failed.connect(self.handle_loading_error)
            self.csv_thread.start()

        except Exception as e:
            error_msg = f"ファイル読み込み準備中にエラーが発生しました:\n{str(e)}"
            logger.error("load_csv_file error: %s", error_msg)
            QMessageBox.critical(self, _("エラー"), error_msg)
            
            # エラー時の状態リセット
            self.is_loading = False
            self.set_ui_enabled(True)

    def update_csv_progress(self, value):
        """CSV変換の進捗更新（初期ダイアログ表示中のみ）
        フッターバー表示中（プログレッシブ表示開始後）は _refresh_loading_model が担当するため更新しない。
        2つのソースが競合するとバーが飛び跳ねる原因になる。"""
        if self._footer_progress_bar.isVisible():
            return  # フッターバーは _refresh_loading_model 側が担当
        if self.progress_dialog is not None and not self.progress_dialog.wasCanceled():
            try:
                self.progress_dialog.setValue(min(95, value))
                self.progress_dialog.setLabelText(f"CSV変換中... ({value}%)\n(データが揃い次第、先行表示します)")
            except RuntimeError as e:
                logger.debug("プログレスダイアログ更新エラー（既に閉じられた可能性）: %s", e)

    def _on_partial_ready(self, tab_data):
        """
        PROGRESSIVE_ROWS 行の挿入が完了し WAL 切替が終わったら呼ばれる。
        まだ変換継続中だが、既存データを先行表示する。
        """
        if self.progress_dialog and self.progress_dialog.wasCanceled():
            return
        try:
            # DB 接続（メインスレッドで作成）
            tab_data.db = QSqlDatabase.addDatabase("QSQLITE", tab_data.connection_name)
            tab_data.db.setDatabaseName(tab_data.db_path)
            if not tab_data.db.open():
                logger.warning("_on_partial_ready: DB接続失敗")
                return

            tab_data.model = QSqlTableModel(None, tab_data.db)
            tab_data.model.setTable("csv_data")
            tab_data.model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
            if not tab_data.model.select():
                logger.warning("_on_partial_ready: model.select()失敗")
                tab_data.db.close()
                tab_data.db = None
                tab_data.model = None
                return

            self._connect_model_signals(tab_data.model, tab_data)

            # ビュー作成
            tab_data.view = QTableView()
            tab_data.view.setModel(tab_data.model)
            tab_data.view.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed
            )
            header = tab_data.view.horizontalHeader()
            header.setDefaultSectionSize(150)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            tab_data.view.setSortingEnabled(False)  # 変換中はソート無効
            self.setup_highlight_delegate(tab_data)
            self._connect_delegate_signals(tab_data)

            # タブ追加（「読み込み中」マーク付き）
            tab_name = os.path.basename(tab_data.csv_path) + " ⏳"
            self.tab_widget.addTab(tab_data.view, tab_name)
            self.tabs_data.append(tab_data)
            self._pending_tab_data = tab_data

            if len(self.tabs_data) == 1:
                self.stack_layout.setCurrentIndex(1)
            # 新しく追加されたタブへ自動切り替え
            self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)

            # canceled シグナルを切断してからダイアログを閉じる
            # （切断しないと close() が canceled を発火し cancel_loading() が走る）
            if self.progress_dialog:
                try:
                    self.progress_dialog.canceled.disconnect(self.cancel_loading)
                except TypeError:
                    pass
                self.progress_dialog.close()
                self.progress_dialog = None

            # フッタープログレスバーを表示（変換継続中の進捗をここで示す）
            self._footer_progress_bar.setValue(0)
            self._footer_progress_label.setText(_("変換中: 0%"))
            self._footer_progress_bar.setVisible(True)
            self._footer_progress_label.setVisible(True)

            # ユーザーがスクロール・閲覧・操作できるよう UI を有効化
            # メニューバーも再有効化し、データ操作は警告ダイアログで案内する
            self.tab_widget.setEnabled(True)
            self.menuBar().setEnabled(True)
            self.setAcceptDrops(False)
            self.update_menu_state()

            # ETA 計算用にプログレッシブ表示開始時点を記録
            self._progressive_start_time = time.time()
            self._progressive_start_rows = PROGRESSIVE_ROWS

            # ファイル情報を確定表示（total_csv_rows は total_rows_ready で設定済み）
            self.update_info_display()
            self.statusBar().showMessage(
                _("{filename} を変換中... (スクロール可)").format(filename=os.path.basename(tab_data.csv_path)), 0
            )

            # 500msごとにモデルをリフレッシュして追加行を表示する
            self._loading_refresh_timer = QTimer(self)
            self._loading_refresh_timer.setInterval(500)
            self._loading_refresh_timer.timeout.connect(
                lambda: self._refresh_loading_model(tab_data)
            )
            self._loading_refresh_timer.start()

            logger.info("プログレッシブ表示開始: %s", tab_data.csv_path)

        except Exception as e:
            logger.error("_on_partial_ready エラー: %s", e)

    def _refresh_loading_model(self, tab_data):
        """変換継続中に定期呼び出しされ、フッターの進捗表示を更新する。

        model.select() は呼ばない。
        select() が発する modelReset → QAbstractItemView::reset() → scrollToTop() は
        Qt 内部で QBasicTimer(0) による遅延実行のため、singleShot(0) との実行順が
        保証できず、スクロール位置が一番上に飛ぶ問題を完全には解消できない。
        そのため読み込み中はモデルを更新せず、完了時に _on_csv_finished で
        1回だけ全件リフレッシュする。
        """
        if tab_data.model is None or tab_data.db is None or not tab_data.db.isOpen():
            return
        try:
            # 進捗カウントを毎回新規の sqlite3 接続で取得する
            # （QSqlQuery(tab_data.db) は WAL スナップショットが固定されるため使わない）
            current_count = 0
            try:
                with _sqlite3.connect(tab_data.db_path, timeout=0.5) as _c:
                    row = _c.execute("SELECT COUNT(*) FROM csv_data").fetchone()
                    if row:
                        current_count = row[0]
            except Exception:
                pass
            if current_count > 0:
                total = tab_data.total_csv_rows  # total_rows_ready で設定済みの推定値

                # ETA 計算（プログレッシブ開始以降の速度で推定）
                elapsed = time.time() - self._progressive_start_time
                rows_since_start = max(0, current_count - self._progressive_start_rows)
                if elapsed > 1.0 and rows_since_start > 0:
                    rows_per_sec = rows_since_start / elapsed
                    remaining_rows = max(0, total - current_count)
                    remaining_sec = remaining_rows / rows_per_sec
                    if remaining_sec < 60:
                        eta_str = _("残り約{sec:.0f}秒").format(sec=remaining_sec)
                    else:
                        eta_str = _("残り約{min:.0f}分").format(min=remaining_sec / 60)
                else:
                    eta_str = _("残り時間計算中...")

                self.statusBar().showMessage(
                    _("{filename} を変換中... ({count:,} 行 読み込み済み)").format(
                        filename=os.path.basename(tab_data.csv_path),
                        count=current_count,
                    ),
                    0
                )
                # フッタープログレスバーを行数ベースで更新（行数・ETA付き）
                if self._footer_progress_bar.isVisible() and total > 0:
                    pct = min(99, int(current_count / total * 100))
                    self._footer_progress_bar.setValue(pct)
                    self._footer_progress_label.setText(
                        _("変換中: {pct}%  {count}行  {eta}").format(pct=pct, count=current_count, eta=eta_str)
                    )
        except Exception as e:
            logger.debug("_refresh_loading_model エラー: %s", e)

    def _on_csv_finished(self, tab_data):
        """CSV→SQLite 変換完了時の処理。モデル更新・プログレス解除・FTS5スレッド開始。"""
        try:
            # 定期リフレッシュタイマーを停止
            if self._loading_refresh_timer:
                self._loading_refresh_timer.stop()
                self._loading_refresh_timer = None

            # タブが既に追加されているか確認
            tab_already_added = tab_data in self.tabs_data

            if tab_data.model is None or tab_data.db is None:
                # partial_ready が来なかった場合（ファイルが PROGRESSIVE_ROWS 未満）
                tab_data.db = QSqlDatabase.addDatabase("QSQLITE", tab_data.connection_name)
                tab_data.db.setDatabaseName(tab_data.db_path)
                if not tab_data.db.open():
                    self.handle_loading_error("データベース接続に失敗しました")
                    return

                tab_data.model = QSqlTableModel(None, tab_data.db)
                tab_data.model.setTable("csv_data")
                tab_data.model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
                if not tab_data.model.select():
                    self.handle_loading_error("データの読み込みに失敗しました")
                    return

                self._connect_model_signals(tab_data.model, tab_data)

                tab_data.view = QTableView()
                tab_data.view.setModel(tab_data.model)
                tab_data.view.setEditTriggers(
                    QAbstractItemView.EditTrigger.DoubleClicked
                    | QAbstractItemView.EditTrigger.EditKeyPressed
                )
                header = tab_data.view.horizontalHeader()
                header.setDefaultSectionSize(150)
                header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
                self.setup_highlight_delegate(tab_data)
                self._connect_delegate_signals(tab_data)

            else:
                # partial_ready 済み: 変換完了後に全件リフレッシュ
                # スクロール位置を保持したまま select() する。
                # select() → modelReset → Qt 内部 delayedReset → scrollToTop() の
                # 遅延実行を singleShot(0) でさらに後から上書きして位置を復元する。
                _view = tab_data.view
                _vbar = _view.verticalScrollBar()
                _hbar = _view.horizontalScrollBar()
                _vpos = _vbar.value()
                _hpos = _hbar.value()

                _view.setUpdatesEnabled(False)
                tab_data.db.close()
                tab_data.db.open()
                tab_data.model.select()

                def _restore_on_finish(
                    view=_view, vbar=_vbar, hbar=_hbar,
                    vpos=_vpos, hpos=_hpos, td=tab_data
                ):
                    try:
                        if td.model is None:
                            return
                        for _i in range(30):
                            if vpos <= vbar.maximum() or not td.model.canFetchMore():
                                break
                            td.model.fetchMore()
                        vbar.setValue(vpos)
                        hbar.setValue(hpos)
                    except Exception:
                        pass
                    finally:
                        view.setUpdatesEnabled(True)

                QTimer.singleShot(0, _restore_on_finish)

            # 正確な行数取得
            if tab_data.db and tab_data.db.isOpen():
                q = QSqlQuery(tab_data.db)
                if q.exec("SELECT COUNT(*) FROM csv_data") and q.next():
                    tab_data.total_csv_rows = q.value(0)
                elif q.lastError().isValid():
                    logger.warning("行数取得クエリ失敗: %s", q.lastError().text())

            tab_data.load_elapsed_time = time.time() - tab_data.start_time
            tab_data.view.setSortingEnabled(True)

            # 設定の表示行数上限まで事前ロード
            row_limit = self.settings.get("display_row_limit", 1000)
            while tab_data.model and tab_data.model.rowCount() < row_limit and tab_data.model.canFetchMore():
                tab_data.model.fetchMore()

            if not tab_already_added:
                tab_name = os.path.basename(tab_data.csv_path)
                self.tab_widget.addTab(tab_data.view, tab_name)
                self.tabs_data.append(tab_data)
                self._pending_tab_data = None
                if len(self.tabs_data) == 1:
                    self.stack_layout.setCurrentIndex(1)
                # 新しく追加されたタブへ自動切り替え
                self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
            else:
                # タブ名から ⏳ を除去（ユーザーが手動でリネーム済みの場合は上書きしない）
                idx = self.tabs_data.index(tab_data)
                if not tab_data.user_renamed_tab:
                    self.tab_widget.setTabText(idx, os.path.basename(tab_data.csv_path))
                self._pending_tab_data = None

            # プログレスダイアログを閉じる（小ファイルで partial_ready が来なかった場合）
            if self.progress_dialog:
                try:
                    self.progress_dialog.canceled.disconnect(self.cancel_loading)
                except TypeError:
                    pass
                self.progress_dialog.close()
                self.progress_dialog = None

            # フッタープログレスバーを非表示にする
            # （直後に _start_fts_build が FTS5 進捗として再表示するため、
            #   ここで長時間表示するタイマーは仕掛けない）
            self._hide_footer_progress()

            self.is_loading = False
            self.csv_thread = None
            self.set_ui_enabled(True)

            self.apply_user_settings()
            self.update_info_display()
            self.update_menu_state()

            self.statusBar().showMessage(
                _("読み込み完了: {filename} ({rows:,} 行)").format(
                    filename=os.path.basename(tab_data.csv_path),
                    rows=tab_data.total_csv_rows,
                ),
                5000
            )

            self._add_to_recent_files(tab_data.csv_path)

            # FTS5 をバックグラウンドで構築（サイズ制限なし）
            # 構築中はフッタープログレスバーで進捗を表示する
            self._start_fts_build(tab_data)

        except Exception as e:
            self.handle_loading_error(f"表示処理中にエラーが発生しました: {str(e)}")

    def _start_fts_build(self, tab_data):
        """FTS5インデックスをバックグラウンド構築開始。フッターで進捗を表示する。"""
        self.fts_thread = Fts5BuildThread(tab_data.db_path)
        self.fts_thread.progress.connect(
            lambda pct, td=tab_data: self._on_fts_progress(pct, td)
        )
        self.fts_thread.finished.connect(
            lambda success, td=tab_data: self._on_fts_built(td, success)
        )
        # フッターバーを「検索インデックス構築中」モードで表示
        self._footer_progress_bar.setStyleSheet("")
        self._footer_progress_bar.setValue(0)
        self._footer_progress_bar.show()
        self._footer_progress_label.setText(_("検索インデックス構築中: 0%"))
        self._footer_progress_label.show()
        self.fts_thread.start()
        logger.info("FTS5構築開始: %s", tab_data.db_path)

    def _on_fts_progress(self, pct: int, tab_data):
        """FTS5構築進捗をフッターに反映する。"""
        if not self._footer_progress_bar.isVisible():
            return
        self._footer_progress_bar.setValue(pct)
        self._footer_progress_label.setText(_("検索インデックス構築中: {pct}%").format(pct=pct))

    def _on_fts_built(self, tab_data, success: bool):
        """FTS5構築完了時のコールバック"""
        self.fts_thread = None
        if success:
            tab_data.fts_enabled = True
            # 完了状態（緑）を3秒間表示してから非表示
            self._footer_progress_bar.setValue(100)
            self._footer_progress_bar.setStyleSheet(
                "QProgressBar {"
                "  border: 1px solid #388E3C;"
                "  border-radius: 3px;"
                "  background: #E8F5E9;"
                "}"
                "QProgressBar::chunk {"
                "  background-color: #43A047;"
                "  border-radius: 2px;"
                "}"
            )
            self._footer_progress_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
            self._footer_progress_label.setText(_("検索インデックス構築完了 ✓"))
            self._footer_progress_bar.setVisible(True)
            self._footer_progress_label.setVisible(True)
            QTimer.singleShot(3000, self._hide_footer_progress)
            self.statusBar().showMessage(_("高速検索インデックスの準備が完了しました"), 5000)
            logger.info("FTS5構築完了: %s", tab_data.db_path)
        else:
            self._hide_footer_progress()
            self.statusBar().showMessage(_("検索インデックスの構築をスキップしました（SQLite LIKE検索を使用）"), 5000)

    def _hide_footer_progress(self):
        """フッタープログレスバーを非表示にしてスタイルをリセットする。
        FTS5構築スレッドが動いている間は隠さない（フッター更新バグ防止）。"""
        if self.fts_thread and self.fts_thread.isRunning():
            return
        self._footer_progress_bar.setStyleSheet("")
        self._footer_progress_label.setStyleSheet("")
        self._footer_progress_bar.setVisible(False)
        self._footer_progress_label.setVisible(False)

    def handle_loading_error(self, error_message):
        """読み込みエラー処理"""
        if self._loading_refresh_timer:
            self._loading_refresh_timer.stop()
            self._loading_refresh_timer = None

        self._hide_footer_progress()

        # プログレスダイアログを閉じる
        if self.progress_dialog:
            try:
                self.progress_dialog.canceled.disconnect(self.cancel_loading)
            except TypeError:
                pass
            self.progress_dialog.close()
            self.progress_dialog = None

        # 読み込み状態をリセット
        self.is_loading = False
        self.set_ui_enabled(True)

        # スレッドをクリア
        self.csv_thread = None

        # エラーメッセージ表示
        QMessageBox.critical(self, _("読み込みエラー"), error_message)

    def cancel_loading(self):
        """読み込みキャンセル処理"""
        if self._loading_refresh_timer:
            self._loading_refresh_timer.stop()
            self._loading_refresh_timer = None

        if self.csv_thread and self.csv_thread.isRunning():
            self.csv_thread.terminate()
            self.csv_thread.wait()
            # Windows ではスレッド終了直後も sqlite3 ファイルロックが残る場合があるため
            # 少し待ってからファイル削除を試みる
            time.sleep(0.3)

        # partial_ready で追加済みのタブを削除
        if self._pending_tab_data and self._pending_tab_data in self.tabs_data:
            idx = self.tabs_data.index(self._pending_tab_data)
            td = self._pending_tab_data
            if td.db and td.db.isOpen():
                td.db.close()
            QSqlDatabase.removeDatabase(td.connection_name)
            if td.db_path:
                _remove_db_files(td.db_path)
            _session_dbs.discard(td.db_path)
            self.tab_widget.removeTab(idx)
            self.tabs_data.pop(idx)
            if not self.tabs_data:
                self.stack_layout.setCurrentIndex(0)

        self._pending_tab_data = None
        self.is_loading = False
        self.set_ui_enabled(True)
        self.csv_thread = None
        self._hide_footer_progress()

        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

    def close_tab(self, index):
        """タブを閉じる処理"""
        if self.is_loading:
            return

        if 0 <= index < len(self.tabs_data):
            tab_data = self.tabs_data[index]

            # ① このタブのDBに対してFTS5スレッドが動いていればキャンセルする
            #
            #    terminate() は Python の finally ブロックをスキップするため、
            #    sqlite3 接続が閉じられず Windows でファイルロックが残る。
            #    そのため terminate() は使わず、cancel フラグを立てて自然終了を待つ。
            #
            #    ROWID ベースの FTS5 挿入（O(log n)）により各チャンクは数十ms で完了し、
            #    通常は wait(5000) 以内に graceful に終了する。
            #    万一 5 秒を超えた場合は orphan スレッドとして管理し、
            #    finished シグナルで非同期にファイル削除する。
            if self.fts_thread and self.fts_thread.isRunning() \
                    and getattr(self.fts_thread, 'db_path', None) == tab_data.db_path:
                self.fts_thread.cancel()
                self.fts_thread.wait(5000)
                if self.fts_thread.isRunning():
                    # まだ動いている場合：orphan スレッドとして非同期削除に切り替える
                    _orphan_path = tab_data.db_path
                    _orphan_thread = self.fts_thread
                    try:
                        _orphan_thread.finished.disconnect()
                    except TypeError:
                        pass
                    def _orphan_cleanup(_p=_orphan_path, _t=_orphan_thread):
                        _remove_db_files(_p)
                        _session_dbs.discard(_p)
                        if _t in self._orphan_fts_threads:
                            self._orphan_fts_threads.remove(_t)
                    _orphan_thread.finished.connect(_orphan_cleanup)
                    self._orphan_fts_threads.append(_orphan_thread)
                    self.fts_thread = None
                    self._hide_footer_progress()
                    # ファイル削除は _orphan_cleanup に委ねるためここでは削除しない
                    # 以降の Qt 側クリーンアップ（②〜⑥）は続行する
                    tab_data.db_path = None  # ⑦ での削除をスキップさせる
                else:
                    self.fts_thread = None
                self._hide_footer_progress()

            # ② ビューからモデルを切り離す（ビューがモデル参照を保持しないように）
            if tab_data.view:
                tab_data.view.setModel(None)

            # ③ undo_stack 内の全モデルを解放
            #    clear() で内部 QSqlQuery を先に解放してから deleteLater() する。
            #    clear() を省くと QSqlTableModel が内部カーソルを保持したまま
            #    removeDatabase() に達し "still in use" 警告が出る。
            if hasattr(tab_data, 'undo_stack'):
                while tab_data.undo_stack:
                    m = tab_data.undo_stack.pop()
                    if m is not None:
                        m.clear()
                        m.deleteLater()

            # ④ 現在のモデルを解放（同上）
            if tab_data.model is not None:
                tab_data.model.clear()
                tab_data.model.deleteLater()
                tab_data.model = None

            # ⑤ deleteLater をここで実行させ、Qt側のDB参照を消す
            QApplication.processEvents()

            # ⑥ DB接続を閉じて登録解除（②〜⑤後なら "still in use" 警告が出ない）
            if tab_data.db and tab_data.db.isOpen():
                tab_data.db.close()
            QApplication.processEvents()  # close後もう一度フラッシュ
            if tab_data.connection_name:
                QSqlDatabase.removeDatabase(tab_data.connection_name)

            # ⑦ 一時ファイル削除（WAL関連ファイルを含む・リトライ付き）
            if tab_data.db_path:
                for suffix in ("", "-wal", "-shm"):
                    _p = tab_data.db_path + suffix
                    if not os.path.exists(_p):
                        continue
                    for _attempt in range(3):
                        try:
                            os.remove(_p)
                            if not suffix:
                                logger.debug("remove temporary datatable => %s", _p)
                            break
                        except OSError as e:
                            if _attempt < 2:
                                QApplication.processEvents()
                            else:
                                logger.warning("一時ファイル削除失敗: %s", e)
            _session_dbs.discard(tab_data.db_path)

            # タブとデータを削除
            self.tab_widget.removeTab(index)
            self.tabs_data.pop(index)

            # タブがなくなったら初期画面に戻す
            if len(self.tabs_data) == 0:
                self.stack_layout.setCurrentIndex(0)

            self.update_info_display()
            self.update_menu_state()

    def apply_user_settings(self):
        """ユーザー設定適用"""
        if self.is_loading:
            return
            
        font_size = self.settings.get("font_size", 12)
        text_color = self.settings.get("text_color", "#000000")
        bg_color = self.settings.get("background_color", "#FFFFFF")
        grid_color = self.settings.get("gridline_color", "#CCCCCC")

        style = f"""
            QTableView {{
                font-size: {font_size}px;
                color: {text_color};
                background-color: {bg_color};
                gridline-color: {grid_color};
            }}
        """
        
        row_limit = self.settings.get("display_row_limit", 1000)

        # 全てのタブのビューにスタイルを適用
        for tab_data in self.tabs_data:
            if tab_data.view:
                tab_data.view.setStyleSheet(style)

                # ハイライトデリゲートの設定も更新
                if tab_data.highlight_delegate:
                    tab_data.highlight_delegate.update_from_config(self.settings)

                # 全件表示モデルに対して表示行数上限を再適用
                if isinstance(tab_data.model, QSqlTableModel):
                    while tab_data.model.rowCount() < row_limit and tab_data.model.canFetchMore():
                        tab_data.model.fetchMore()

    def push_current_view_to_stack(self):
        """現在の表示内容をスタックに保存"""
        if self.is_loading:
            return
            
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            return

        if isinstance(tab_data.model, QSqlQueryModel):
            sql = tab_data.model.query().executedQuery()
            if sql:
                tab_data.view_stack.append(sql)
        elif isinstance(tab_data.model, QSqlTableModel):
            tab_data.view_stack.append("__FULL__")

    def open_search_dialog(self):
        if self.is_loading and self._pending_tab_data is None:
            return
        if not self._warn_if_converting():
            return
            
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            return  # メッセージは表示せず、単純にリターン
        
        dialog = SearchDialog(self)
        dialog.set_search_text(tab_data.last_search_keyword)
        if dialog.exec():
            keyword = dialog.get_search_text()
            tab_data.last_search_keyword = keyword
            self.execute_fts_search(keyword, tab_data)

    def execute_fts_search(self, keyword, tab_data):
        """検索を実行する。優先順位: FTS5 → SQLite LIKE"""
        if (self.is_loading and self._pending_tab_data is None) or not keyword.strip() or not (tab_data.db and tab_data.db.isOpen()):
            return

        if tab_data.fts_enabled:
            self._search_fts5(keyword, tab_data)
        else:
            self.statusBar().showMessage(_("SQLite LIKEで検索中（大容量ファイルは時間がかかります）..."), 0)
            QApplication.processEvents()
            self._search_like(keyword, tab_data)

    def _search_fts5(self, keyword: str, tab_data):
        """FTS5による高速全文検索。
        FTS5テーブルは別スレッドの sqlite3 接続で作成されるため、
        QSqlDatabase の WAL スナップショットから見えないことがある。
        そのため FTS5 クエリは raw sqlite3 で実行し rowid リストを取得してから
        Qt モデルへ渡す。
        """
        fts_phrase = '"' + keyword.replace('"', '""') + '"'

        try:
            with _sqlite3.connect(tab_data.db_path, timeout=5.0) as _conn:
                rows = _conn.execute(
                    "SELECT rowid FROM csv_data_fts WHERE csv_data_fts MATCH ?",
                    (fts_phrase,),
                ).fetchall()
                actual_count = len(rows)
        except Exception as e:
            logger.warning("FTS5検索エラー（SQLite LIKEにフォールバック）: %s", e)
            tab_data.fts_enabled = False
            self._search_like(keyword, tab_data)
            return

        if not rows:
            QMessageBox.information(self, _("検索結果"), f'"{keyword}" に一致する行は見つかりませんでした。')
            self.statusBar().showMessage(_("検索完了: 0件"), 5000)
            return

        # Undo用に現在の状態を保存
        if tab_data.model:
            tab_data.undo_stack.append(tab_data.model)

        # rowid は整数確定だが型を明示的に検証してインジェクションを防ぐ
        rowid_list = ",".join(str(int(r[0])) for r in rows)
        sql = f"SELECT * FROM csv_data WHERE rowid IN ({rowid_list})"

        model = QSqlQueryModel(self)
        model.setQuery(sql, tab_data.db)
        if model.lastError().isValid():
            QMessageBox.critical(self, _("検索エラー"), model.lastError().text())
            return

        tab_data.view.setModel(model)
        tab_data.model = model
        tab_data.set_search_state(_('全文検索 "{keyword}"').format(keyword=keyword), actual_count)
        self._set_search_highlight(tab_data, keyword)
        self.update_query_label()
        self.statusBar().showMessage(_("検索完了: {count:,} 件").format(count=actual_count), 5000)

    def _search_like(self, keyword: str, tab_data):
        """SQLite LIKE による全列フルスキャン検索（フォールバック）"""
        try:
            # 列数は undo_stack に入れる前に取得する
            col_count = tab_data.model.columnCount() if tab_data.model else 0
            if tab_data.model:
                tab_data.undo_stack.append(tab_data.model)
            if col_count == 0:
                return
            kw = keyword.replace("'", "''")
            conditions = " OR ".join(
                f'"{tab_data.model.headerData(i, Qt.Orientation.Horizontal).replace(chr(34), chr(34)*2)}" LIKE \'%{kw}%\''
                for i in range(col_count)
            )
            sql = f"SELECT * FROM csv_data WHERE {conditions}"
            count_sql = f"SELECT COUNT(*) FROM csv_data WHERE {conditions}"

            count_query = QSqlQuery(tab_data.db)
            actual_count = 0
            if count_query.exec(count_sql) and count_query.next():
                actual_count = count_query.value(0)

            model = QSqlQueryModel(self)
            model.setQuery(sql, tab_data.db)
            if model.lastError().isValid():
                QMessageBox.critical(self, _("検索エラー"), model.lastError().text())
                return

            tab_data.view.setModel(model)
            tab_data.model = model
            tab_data.set_search_state(_('LIKE検索 "{keyword}"').format(keyword=keyword), actual_count)
            self._set_search_highlight(tab_data, keyword)
            self.update_query_label()
            self.statusBar().showMessage(_("検索完了: {count:,} 件").format(count=actual_count), 5000)

        except Exception as e:
            logger.warning("LIKE検索エラー: %s", e)
            QMessageBox.critical(self, _("検索エラー"), str(e))

    def open_filter_dialog(self):
        if self.is_loading and self._pending_tab_data is None:
            return
        if not self._warn_if_converting():
            return
            
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            return  # メッセージは表示せず、単純にリターン

        
        self._clear_search_highlight(tab_data)
        columns = [tab_data.model.headerData(i, Qt.Orientation.Horizontal) for i in range(tab_data.model.columnCount())]
        dialog = FilterDialog(self, columns)
        if dialog.exec():
            groups = dialog.get_condition_groups()
            group_clauses = []
            for group in groups:
                logic = group["logic"]
                clauses = []
                for col, op, val in group["conditions"]:
                    safe_val = val.replace("'", "''")  # SQLite シングルクォートエスケープ
                    esc_col = col.replace('"', '""')
                    val_str = f"'%{safe_val}%'" if op == "LIKE" else f"'{safe_val}'"
                    clauses.append(f'"{esc_col}" {op} {val_str}')
                group_clause = f" {logic} ".join(clauses)
                group_clauses.append(f"({group_clause})")

            where_clause = group_clauses[0]
            for i in range(1, len(group_clauses)):
                logic = groups[i].get("before_logic", "AND")
                where_clause = f"({where_clause}) {logic} {group_clauses[i]}"

            # まず件数を取得
            count_sql = f"SELECT COUNT(*) FROM csv_data WHERE {where_clause}"
            try:
                count_query = QSqlQuery(tab_data.db)
                actual_count = 0
                if count_query.exec(count_sql) and count_query.next():
                    actual_count = count_query.value(0)
            except Exception as e:
                logger.warning("Count query error: %s", e)
                actual_count = 0

            model = QSqlQueryModel(self)
            model.setQuery(f"SELECT * FROM csv_data WHERE {where_clause}", tab_data.db)
            if model.lastError().isValid():
                QMessageBox.critical(self, _("抽出エラー"), model.lastError().text())
                return
            
            tab_data.view.setModel(model)
            tab_data.model = model
            tab_data.set_search_state(_("条件抽出"), actual_count)
            self.update_query_label()

    def _restore_from_undo_stack(self, tab_data) -> bool:
        """undo_stackから一段戻す。戻した場合True、スタックが空の場合Falseを返す"""
        if not tab_data.undo_stack:
            return False

        if tab_data.highlight_delegate:
            tab_data.highlight_delegate.clear_highlights()
            tab_data.highlight_delegate.clear_search_keyword()
            tab_data.view.viewport().update()

        old_model = tab_data.model
        prev_model = tab_data.undo_stack.pop()
        tab_data.view.setModel(prev_model)
        tab_data.model = prev_model
        # 同一オブジェクトかどうかの identity 比較（意図的）:
        # pop した prev_model を setModel 直後に deleteLater すると view が壊れるため
        # 「差し替え前モデル ≠ 復元モデル」の場合にのみ削除する
        if old_model is not None and old_model is not prev_model:
            old_model.deleteLater()
        if not isinstance(prev_model, QSqlTableModel):
            tab_data.set_search_state(_("前の状態に戻りました"), None)
        else:
            tab_data.clear_search_state(_("前の状態に戻りました"))

        # 編集状態をリセット
        tab_data.edited_cells.clear()
        if tab_data.highlight_delegate:
            tab_data.highlight_delegate.clear_edited_cells()
        # QSqlTableModel に戻った場合は編集トリガーを再有効化
        if tab_data.view:
            if isinstance(prev_model, QSqlTableModel):
                tab_data.view.setEditTriggers(
                    QAbstractItemView.EditTrigger.DoubleClicked
                    | QAbstractItemView.EditTrigger.EditKeyPressed
                )
            else:
                tab_data.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.update_query_label()
        return True

    # ------------------------------------------------------------------
    # セル編集追跡・上書き保存
    # ------------------------------------------------------------------

    def _connect_model_signals(self, model: QSqlTableModel, tab_data) -> None:
        """モデルのシグナルを接続する（modelReset でハイライトをクリア）。"""
        model.modelReset.connect(
            lambda td=tab_data: self._on_model_reset(td)
        )

    def _connect_delegate_signals(self, tab_data) -> None:
        """デリゲートの cell_committed シグナルを接続して正確なセル追跡を行う。"""
        if tab_data.highlight_delegate:
            tab_data.highlight_delegate.cell_committed.connect(
                lambda row, col, td=tab_data: self._on_cell_committed(row, col, td)
            )

    def _on_cell_committed(self, row: int, col: int, tab_data) -> None:
        """ユーザーがセルを確定したとき、そのセルだけを編集済みとしてマークする。"""
        tab_data.edited_cells.add((row, col))
        if tab_data.highlight_delegate:
            tab_data.highlight_delegate.add_edited_cell(row, col)
            if tab_data.view:
                tab_data.view.viewport().update()
        self.update_menu_state()

    def _on_model_reset(self, tab_data) -> None:
        """モデルリセット時に編集済みセルをクリアする。"""
        tab_data.edited_cells.clear()
        if tab_data.highlight_delegate:
            tab_data.highlight_delegate.clear_edited_cells()
            if tab_data.view:
                tab_data.view.viewport().update()

    def overwrite_csv(self) -> None:
        """現在のDBデータを元のCSVファイルに上書き保存する（Ctrl+S）。"""
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            return
        if not isinstance(tab_data.model, QSqlTableModel):
            return

        if not tab_data.csv_path:
            QMessageBox.warning(self, _("上書き保存"),
                _("元のCSVファイルのパスが不明です。「名前を付けて保存」をお使いください。"))
            return
        if not os.path.exists(tab_data.csv_path):
            QMessageBox.warning(self, _("上書き保存"),
                _("元のCSVファイルが見つかりません:\n{path}\n「名前を付けて保存」をお使いください。").format(
                    path=tab_data.csv_path))
            return

        result = QMessageBox.question(
            self, _("上書き保存"),
            _("以下のファイルに上書きしますか？\n\n{path}").format(path=tab_data.csv_path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        model = tab_data.model
        while model.canFetchMore():
            model.fetchMore()

        total_cols = model.columnCount()
        total_rows = model.rowCount()
        headers = [model.headerData(i, Qt.Orientation.Horizontal) for i in range(total_cols)]
        encoding = tab_data.csv_encoding or "utf-8-sig"

        is_utf16 = encoding.lower().startswith("utf-16")
        open_kwargs: dict = {"encoding": encoding}
        if not is_utf16:
            open_kwargs["newline"] = ""

        try:
            with open(tab_data.csv_path, "w", **open_kwargs) as f:
                writer = _csv_module.writer(f)
                writer.writerow(headers)
                for row in range(total_rows):
                    row_data = [
                        model.data(model.index(row, col)) or ""
                        for col in range(total_cols)
                    ]
                    writer.writerow(row_data)

            tab_data.edited_cells.clear()
            if tab_data.highlight_delegate:
                tab_data.highlight_delegate.clear_edited_cells()
                tab_data.view.viewport().update()

            self.statusBar().showMessage(
                _("上書き保存しました: {path}").format(path=tab_data.csv_path), 5000
            )
        except Exception as e:
            QMessageBox.critical(self, _("エラー"),
                _("上書き保存に失敗しました:\n{error}").format(error=str(e)))

    # ------------------------------------------------------------------
    # 選択範囲のコピー
    # ------------------------------------------------------------------

    def copy_selection(self) -> None:
        """選択セル範囲をタブ区切りテキストとしてクリップボードにコピーする。"""
        # テキスト入力ウィジェットにフォーカスがある場合は標準の Ctrl+C に任せる
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            focused.copy()
            return
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model or not tab_data.view:
            return
        selection = tab_data.view.selectionModel().selectedIndexes()
        if not selection:
            return
        rows = sorted(set(idx.row() for idx in selection))
        cols = sorted(set(idx.column() for idx in selection))
        cell_map = {(idx.row(), idx.column()): str(idx.data() or "") for idx in selection}
        lines = ["\t".join(cell_map.get((r, c), "") for c in cols) for r in rows]
        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage(
            _("{rows} 行 × {cols} 列をコピーしました").format(rows=len(rows), cols=len(cols)), 3000
        )

    # ------------------------------------------------------------------
    # 検索ハイライトヘルパー
    # ------------------------------------------------------------------

    def _set_search_highlight(self, tab_data, keyword: str) -> None:
        """検索後にキーワードハイライトをデリゲートに設定する。"""
        self.setup_highlight_delegate(tab_data)
        tab_data.highlight_delegate.set_search_keyword(keyword)
        tab_data.view.viewport().update()

    def _clear_search_highlight(self, tab_data) -> None:
        """検索ハイライトをクリアする。"""
        if tab_data and tab_data.highlight_delegate:
            tab_data.highlight_delegate.clear_search_keyword()
            if tab_data.view:
                tab_data.view.viewport().update()

    # ------------------------------------------------------------------
    # タブ並び替え・名前変更
    # ------------------------------------------------------------------

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        """ドラッグによるタブ移動に合わせて tabs_data を同期する。"""
        self.tabs_data.insert(to_idx, self.tabs_data.pop(from_idx))

    def _on_tab_double_clicked(self, index: int) -> None:
        """タブをダブルクリックして名前を変更する。"""
        if index < 0 or index >= len(self.tabs_data):
            return
        current_name = self.tab_widget.tabText(index)
        new_name, ok = QInputDialog.getText(
            self, _("タブ名を変更"), _("新しいタブ名を入力してください:"), text=current_name
        )
        if ok and new_name.strip():
            self.tab_widget.setTabText(index, new_name.strip())
            self.tabs_data[index].user_renamed_tab = True

    # ------------------------------------------------------------------
    # 最近使ったファイル
    # ------------------------------------------------------------------

    def _add_to_recent_files(self, path: str) -> None:
        """最近使ったファイルリストの先頭に追加して設定を保存する。"""
        recent = self.settings.get("recent_files", [])
        recent = [p for p in recent if p != path]
        recent.insert(0, path)
        self.settings["recent_files"] = recent[:10]
        save_config(self.settings)
        self._rebuild_recent_files_menu()

    def _rebuild_recent_files_menu(self) -> None:
        """最近使ったファイルサブメニューを再構築する。"""
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        recent = self.settings.get("recent_files", [])
        if not recent:
            no_item = QAction(_("（履歴なし）"), self)
            no_item.setEnabled(False)
            self.recent_menu.addAction(no_item)
            return
        for path in recent:
            name = os.path.basename(path)
            action = QAction(name, self)
            action.setToolTip(path)
            action.triggered.connect(
                lambda checked, p=path: (
                    self.load_csv_file(p) if os.path.exists(p)
                    else self._recent_file_not_found(p)
                )
            )
            self.recent_menu.addAction(action)
        self.recent_menu.addSeparator()
        clear_action = QAction(_("履歴をクリア"), self)
        clear_action.triggered.connect(self._clear_recent_files)
        self.recent_menu.addAction(clear_action)

    def _recent_file_not_found(self, path: str) -> None:
        ans = QMessageBox.question(
            self,
            _("ファイルが見つかりません"),
            f"ファイルが見つかりません:\n{path}\n\n履歴から削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.settings["recent_files"] = [
                p for p in self.settings.get("recent_files", []) if p != path
            ]
            save_config(self.settings)
            self._rebuild_recent_files_menu()

    def _clear_recent_files(self) -> None:
        self.settings["recent_files"] = []
        save_config(self.settings)
        self._rebuild_recent_files_menu()

    # ------------------------------------------------------------------

    def undo_last_action(self):
        """最後のアクションを元に戻す（Ctrl+Z対応）"""
        if self.is_loading and self._pending_tab_data is None:
            return

        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.db or not tab_data.db.isOpen():
            return

        if self._restore_from_undo_stack(tab_data):
            self.statusBar().showMessage(_("操作を元に戻しました"), 3000)
            return

        # 元に戻す履歴がない場合は全件表示に戻す
        self.reset_to_full_view()

    def reset_to_full_view(self):
        """全件表示に戻す"""
        if self.is_loading and self._pending_tab_data is None:
            return

        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.db or not tab_data.db.isOpen():
            return

        if self._restore_from_undo_stack(tab_data):
            return

        # 新しい標準のQSqlTableModelを作成
        model = QSqlTableModel(self, tab_data.db)
        model.setTable("csv_data")
        model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
        model.select()
        self._connect_model_signals(model, tab_data)

        tab_data.view.setSortingEnabled(True)
        tab_data.view.setModel(model)
        tab_data.model = model
        tab_data.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self._clear_search_highlight(tab_data)
        tab_data.clear_search_state()
        self.update_query_label()

        # 完了メッセージ（total_csv_rowsで正確な行数を表示）
        self.statusBar().showMessage(
            _("全件表示に戻しました ({rows:,} 行)").format(rows=tab_data.total_csv_rows),
            3000
        )

    def open_replace_dialog(self):
        if self.is_loading and self._pending_tab_data is None:
            return
        if not self._warn_if_converting():
            return
            
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            return  # メッセージは表示せず、単純にリターン

        
        dialog = ReplaceDialog(self)
        dialog.set_search_text(tab_data.last_search_keyword)
        
        if dialog.exec():
            search_text = dialog.get_search_text()
            replace_text = dialog.get_replace_text()
            case_sensitive = dialog.is_case_sensitive()
            whole_word = dialog.is_whole_word()
            result_type = dialog.get_result_type()
            
            tab_data.last_search_keyword = search_text
            
            if result_type == 'preview':
                self.preview_replace(search_text, replace_text, case_sensitive, whole_word, tab_data)
            elif result_type == 'replace_all':
                self.execute_replace(search_text, replace_text, case_sensitive, whole_word, tab_data)

    def preview_replace(self, search_text, replace_text, case_sensitive, whole_word, tab_data):
        """置換のプレビューを表示"""
        if self.is_loading or not search_text.strip() or not (tab_data.db and tab_data.db.isOpen()):
            return
        
        # まず検索を実行して該当件数を確認
        count = self.get_replace_count(search_text, case_sensitive, whole_word, tab_data)
        
        if count == 0:
            QMessageBox.information(self, _("置換プレビュー"), _("置換対象が見つかりませんでした。"))
            return

        # プレビューメッセージを表示
        msg = QMessageBox(self)
        msg.setWindowTitle(_("置換プレビュー"))
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(_("「{search}」を「{replace}」に置換します。").format(search=search_text, replace=replace_text))
        msg.setInformativeText(_("対象件数: {count:,} 件\n\n置換を実行しますか？").format(count=count))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.execute_replace(search_text, replace_text, case_sensitive, whole_word, tab_data)

    def get_replace_count(self, search_text, case_sensitive, whole_word, tab_data):
        """最適化された置換対象件数取得"""
        try:
            # より効率的なSQL構築
            escaped_search = search_text.replace("'", "''")
            
            if case_sensitive:
                if whole_word:
                    # 完全一致での検索
                    like_pattern = f"= '{escaped_search}'"
                else:
                    # 部分一致での検索
                    like_pattern = f"LIKE '%{escaped_search}%'"
            else:
                if whole_word:
                    # 大文字小文字無視の完全一致
                    like_pattern = f"= '{escaped_search}' COLLATE NOCASE"
                else:
                    # 大文字小文字無視の部分一致
                    like_pattern = f"LIKE '%{escaped_search}%' COLLATE NOCASE"

            # UNION ALLを使って一度のクエリで全列を検索
            column_count = tab_data.model.columnCount()
            union_queries = []
            
            for i in range(column_count):
                column_name = tab_data.model.headerData(i, Qt.Orientation.Horizontal)
                esc_col = column_name.replace('"', '""')
                union_queries.append(f'SELECT rowid FROM csv_data WHERE "{esc_col}" {like_pattern}')
            
            # 重複を排除して件数を取得
            count_sql = f"SELECT COUNT(DISTINCT rowid) FROM ({' UNION ALL '.join(union_queries)})"
            
            query = QSqlQuery(tab_data.db)
            if query.exec(count_sql) and query.next():
                return query.value(0)
            return 0
        except Exception as e:
            logger.warning("Count query error: %s", e)
            return 0

    def execute_replace(self, search_text, replace_text, case_sensitive, whole_word, tab_data):
        """最適化された置換実行"""
        if self.is_loading or not search_text.strip() or not (tab_data.db and tab_data.db.isOpen()):
            return

        try:
            # Undo用に現在の状態を保存
            if tab_data.model:
                tab_data.undo_stack.append(tab_data.model)

            # 置換処理開始
            start_time = time.time()
            self.statusBar().showMessage(_("置換処理中..."))
            
            # ハイライトデリゲートを設定
            self.setup_highlight_delegate(tab_data)
            
            # 置換されたセルの位置を記録
            replaced_cells = []
            total_replaced = 0
            replace_error: str | None = None

            query = QSqlQuery(tab_data.db)

            # トランザクション開始（高速化）
            tab_data.db.transaction()

            column_count = tab_data.model.columnCount()

            for i in range(column_count):
                column_name = tab_data.model.headerData(i, Qt.Orientation.Horizontal)
                esc_col = column_name.replace('"', '""')

                if case_sensitive:
                    if whole_word:
                        # 完全一致: SELECT → UPDATE（パラメータバインド）
                        query.prepare(f'SELECT rowid FROM csv_data WHERE "{esc_col}" = ?')
                        query.addBindValue(search_text)
                        if query.exec():
                            while query.next():
                                replaced_cells.append((query.value(0), i))

                        query.prepare(f'UPDATE csv_data SET "{esc_col}" = ? WHERE "{esc_col}" = ?')
                        query.addBindValue(replace_text)
                        query.addBindValue(search_text)
                        if not query.exec():
                            raise RuntimeError(f"列 '{column_name}' の更新に失敗: {query.lastError().text()}")
                        total_replaced += query.numRowsAffected()
                    else:
                        # 部分置換
                        like_pattern = f'%{search_text}%'
                        query.prepare(f'SELECT rowid FROM csv_data WHERE "{esc_col}" LIKE ?')
                        query.addBindValue(like_pattern)
                        if query.exec():
                            while query.next():
                                replaced_cells.append((query.value(0), i))

                        query.prepare(f'UPDATE csv_data SET "{esc_col}" = REPLACE("{esc_col}", ?, ?) WHERE "{esc_col}" LIKE ?')
                        query.addBindValue(search_text)
                        query.addBindValue(replace_text)
                        query.addBindValue(like_pattern)
                        if not query.exec():
                            raise RuntimeError(f"列 '{column_name}' の更新に失敗: {query.lastError().text()}")
                        total_replaced += query.numRowsAffected()
                else:
                    if whole_word:
                        # 大文字小文字無視の完全一致
                        query.prepare(f'SELECT rowid FROM csv_data WHERE "{esc_col}" = ? COLLATE NOCASE')
                        query.addBindValue(search_text)
                        if query.exec():
                            while query.next():
                                replaced_cells.append((query.value(0), i))

                        query.prepare(f'UPDATE csv_data SET "{esc_col}" = ? WHERE "{esc_col}" = ? COLLATE NOCASE')
                        query.addBindValue(replace_text)
                        query.addBindValue(search_text)
                        if not query.exec():
                            raise RuntimeError(f"列 '{column_name}' の更新に失敗: {query.lastError().text()}")
                        total_replaced += query.numRowsAffected()
                    else:
                        # 大文字小文字無視の部分置換（REPLACEは大文字小文字を区別するため、個別処理）
                        like_pattern = f'%{search_text}%'
                        query.prepare(f'SELECT rowid, "{esc_col}" FROM csv_data WHERE "{esc_col}" LIKE ? COLLATE NOCASE')
                        query.addBindValue(like_pattern)

                        # まず対象行を取得
                        if query.exec():
                            rows_to_update = []
                            while query.next():
                                rowid = query.value(0)
                                _raw = query.value(1)
                                current_value = str(_raw) if _raw is not None else ""
                                # 大文字小文字を無視して置換
                                new_value = re.sub(re.escape(search_text), replace_text, current_value, flags=re.IGNORECASE)
                                if new_value != current_value:
                                    rows_to_update.append((rowid, new_value))
                                    replaced_cells.append((rowid, i))

                            # バッチ更新（パラメータバインド）
                            for rowid, new_value in rows_to_update:
                                query.prepare(f'UPDATE csv_data SET "{esc_col}" = ? WHERE rowid = ?')
                                query.addBindValue(new_value)
                                query.addBindValue(rowid)
                                if not query.exec():
                                    raise RuntimeError(f"列 '{column_name}' の行更新に失敗: {query.lastError().text()}")
                                total_replaced += 1
                        continue

            # トランザクションコミット
            tab_data.db.commit()
            
            # 処理時間計算
            elapsed_time = time.time() - start_time
            
            # 現在のソート状態を保存（置換後に同じソートを再適用してハイライト位置ずれを防ぐ）
            sort_section = tab_data.view.horizontalHeader().sortIndicatorSection() if tab_data.view else -1
            sort_order = tab_data.view.horizontalHeader().sortIndicatorOrder() if tab_data.view else Qt.SortOrder.AscendingOrder

            # 置換後のデータを表示
            model = QSqlTableModel(self, tab_data.db)
            model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
            model.setTable("csv_data")
            model.select()

            # ソートを新モデルに事前適用（ハイライト位置の計算をソート後の行順序に合わせる）
            if sort_section >= 0:
                model.setSort(sort_section, sort_order)
                model.select()

            # シグナル接続はすべての select() 完了後に行う（途中の modelReset で edited_cells が消えないよう）
            self._connect_model_signals(model, tab_data)

            # rowid → モデル行番号のマッピングを構築（現在のソート順を反映）
            rowid_map_query = QSqlQuery(tab_data.db)
            if sort_section >= 0 and model.columnCount() > sort_section:
                sort_col_name = model.headerData(sort_section, Qt.Orientation.Horizontal)
                esc_sort = sort_col_name.replace('"', '""')
                order_str = "ASC" if sort_order == Qt.SortOrder.AscendingOrder else "DESC"
                rowid_map_query.exec(f'SELECT rowid FROM csv_data ORDER BY "{esc_sort}" {order_str}')
            else:
                rowid_map_query.exec("SELECT rowid FROM csv_data")
            rowid_to_model_row: dict[int, int] = {}
            mr = 0
            while rowid_map_query.next():
                rowid_to_model_row[rowid_map_query.value(0)] = mr
                mr += 1
            replaced_cells = [(rowid_to_model_row[rid], col) for rid, col in replaced_cells if rid in rowid_to_model_row]

            tab_data.view.setSortingEnabled(False)
            tab_data.view.setModel(model)
            tab_data.model = model
            # ソートインジケーターを復元（setSortingEnabled(True) 時に同じソートが再適用されるよう）
            if sort_section >= 0:
                tab_data.view.horizontalHeader().setSortIndicator(sort_section, sort_order)
            tab_data.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

            # ハイライト設定
            tab_data.highlight_delegate.set_highlighted_cells(replaced_cells)
            
            # ソート有効化とビュー更新
            QTimer.singleShot(100, lambda: self._finalize_replace_view(tab_data, search_text, replace_text, total_replaced, elapsed_time))

        except Exception as e:
            # トランザクションロールバック
            if tab_data.db and tab_data.db.isOpen():
                tab_data.db.rollback()
            error_msg = f"置換処理中にエラーが発生しました: {str(e)}"
            logger.error("置換処理エラー: %s", error_msg)
            QMessageBox.critical(self, _("置換エラー"), error_msg)
            self.statusBar().showMessage(_("置換処理中..."), 5000)

    def _finalize_replace_view(self, tab_data, search_text, replace_text, total_replaced, elapsed_time):
        """置換後のビューを最終化（設定対応版）"""
        tab_data.view.setSortingEnabled(True)
        tab_data.view.viewport().update()  # ハイライト表示を更新（凍結ビュー含む）
        
        tab_data.clear_search_state(_('置換完了: "{search}" → "{replace}" ({count:,}箇所)').format(search=search_text, replace=replace_text, count=total_replaced))
        self.update_query_label()

        # 完了メッセージ
        self.statusBar().showMessage(
            _("置換完了: {count:,} 箇所を置換しました (所要時間: {elapsed:.2f}秒)").format(
                count=total_replaced, elapsed=elapsed_time
            ),
            5000
        )

        QMessageBox.information(self, _("置換完了"),
                            _("{replaced:,} 箇所を置換しました。\n所要時間: {elapsed:.2f}秒").format(
                                replaced=total_replaced, elapsed=elapsed_time))

    def _clear_highlights(self, tab_data):
        """ハイライトをクリア（設定対応版）"""
        if tab_data.highlight_delegate:
            tab_data.highlight_delegate.clear_highlights()
            tab_data.view.viewport().update()
    
    def setup_highlight_delegate(self, tab_data):
        """ハイライトデリゲートを設定（設定対応版）"""
        if not tab_data.highlight_delegate:
            #  設定を読み込んでデリゲートを作成
            tab_data.highlight_delegate = HighlightDelegate(config=self.settings)
            tab_data.view.setItemDelegate(tab_data.highlight_delegate)
        else:
            # 既存のデリゲートの設定を更新
            tab_data.highlight_delegate.update_from_config(self.settings)

    def _copy_to_clipboard(self, text):
        """テキストをクリップボードにコピー"""
        try:
            from PyQt6.QtGui import QGuiApplication
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            self.statusBar().showMessage(_("クリップボードにコピーしました"), 3000)
        except Exception as e:
            QMessageBox.warning(self, _("コピーエラー"), f"クリップボードへのコピーに失敗しました:\n{str(e)}")

    def save_current_view_triggered(self):
        if self.is_loading and self._pending_tab_data is None:
            return
        if not self._warn_if_converting():
            return
            
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            return  # メッセージは表示せず、単純にリターン
        save_current_view(self, tab_data.model)

    def split_current_view_triggered(self):
        if self.is_loading and self._pending_tab_data is None:
            return
        if not self._warn_if_converting_strong():
            return
            
        tab_data = self.get_current_tab_data()
        if not tab_data or not tab_data.model:
            return  # メッセージは表示せず、単純にリターン
        split_current_view(self, tab_data.model, tab_data.csv_path)


    def load_database_directly(self, db_path, virtual_csv_name):
        """データベースファイルを直接開く（ZIP結合結果用）"""
        if self.is_loading:
            return

        try:
            # データベースファイルの妥当性チェック
            if not os.path.exists(db_path):
                QMessageBox.critical(self, _("エラー"), f"データベースファイルが見つかりません: {db_path}")
                return

            # 読み込み開始
            self.is_loading = True
            self.set_ui_enabled(False)
            
            # TabDataを作成
            connection_name = f"conn_{int(time.time()*1000)}"
            tab_data = TabData(virtual_csv_name, db_path, connection_name)
            
            # データベースのサイズ情報を取得
            file_size_gb = os.path.getsize(db_path) / (1024**3)
            tab_data.csv_encoding = _("UTF-8 (データベース)")
            tab_data.start_time = time.time()

            # プログレスダイアログ
            self.progress_dialog = QProgressDialog(_("データベース読み込み中..."), None, 0, 100, self)
            self.progress_dialog.setWindowTitle(_("データベース読み込み"))
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setAutoClose(False)
            self.progress_dialog.setAutoReset(False)
            self.progress_dialog.show()
            self.progress_dialog.raise_()
            self.progress_dialog.activateWindow()
            QApplication.processEvents()

            # データベース接続・モデル生成（メインスレッドで実行）
            tab_data.db = QSqlDatabase.addDatabase("QSQLITE", tab_data.connection_name)
            tab_data.db.setDatabaseName(tab_data.db_path)
            if not tab_data.db.open():
                QSqlDatabase.removeDatabase(tab_data.connection_name)
                self.handle_loading_error("データベース接続に失敗しました")
                return

            tab_data.model = QSqlTableModel(None, tab_data.db)
            tab_data.model.setTable("csv_data")
            tab_data.model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
            if not tab_data.model.select():
                tab_data.db.close()
                QSqlDatabase.removeDatabase(tab_data.connection_name)
                self.handle_loading_error("データの読み込みに失敗しました")
                return

            self._connect_model_signals(tab_data.model, tab_data)
            tab_data.load_elapsed_time = time.time() - tab_data.start_time
            self.complete_database_loading(tab_data)

        except Exception as e:
            error_msg = f"データベース読み込み準備中にエラーが発生しました:\n{str(e)}"
            logger.error("load_database_directly error: %s", error_msg)
            QMessageBox.critical(self, _("エラー"), error_msg)
            
            # エラー時の状態リセット
            self.is_loading = False
            self.set_ui_enabled(True)

    def complete_database_loading(self, tab_data):
        """データベース読み込み完了処理"""
        try:
            tab_data.view = QTableView()
            tab_data.view.setModel(tab_data.model)
            tab_data.view.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed
            )

            # ヘッダーの設定
            header = tab_data.view.horizontalHeader()
            header.setDefaultSectionSize(150)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            tab_data.view.setSortingEnabled(True)
            self.setup_highlight_delegate(tab_data)
            self._connect_delegate_signals(tab_data)

            # タブに追加（ZIP結合であることを示す）
            zip_base_name = os.path.splitext(os.path.basename(tab_data.csv_path))[0]
            tab_name = f"📦 {zip_base_name}"  # アイコンで区別
            self.tab_widget.addTab(tab_data.view, tab_name)
            self.tabs_data.append(tab_data)

            # 初回タブの場合は表示を切り替え
            if len(self.tabs_data) == 1:
                self.stack_layout.setCurrentIndex(1)
            # 新しく追加されたタブへ自動切り替え
            self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)

            # プログレスダイアログを閉じる
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None

            # 読み込み完了
            self.is_loading = False
            self.set_ui_enabled(True)

            # 設定適用と情報表示更新
            self.apply_user_settings()
            
            # 特別な情報表示（ZIP結合データベース用）
            self.update_database_info_display(tab_data)
            
            # メニュー状態を更新
            self.update_menu_state()
            
            # 読み込み完了メッセージ
            row_count = tab_data.model.rowCount()
            self.statusBar().showMessage(
                _("ZIP結合データベース読み込み完了: {name} ({rows:,} 行)").format(
                    name=tab_name, rows=row_count
                ),
                5000
            )
        except Exception as e:
            self.handle_loading_error(f"データベース表示処理中にエラーが発生しました: {str(e)}")

    def update_database_info_display(self, tab_data):
        """データベース用の情報表示更新"""
        try:
            # ファイル情報を更新
            self.info_fields[_("ファイル名")].setText(f"{tab_data.csv_path}{_(' (ZIP結合)')}")

            # データベースファイルサイズ
            file_size_gb = os.path.getsize(tab_data.db_path) / (1024**3)
            self.info_fields[_("容量")].setText(f"{file_size_gb:.2f} GB")

            self.info_fields[_("エンコーディング")].setText(_("UTF-8 (データベース)"))

            # 行数取得 - SQLで正確な件数を取得
            if tab_data.db and tab_data.db.isOpen():
                q = QSqlQuery(tab_data.db)
                if q.exec("SELECT COUNT(*) FROM csv_data") and q.next():
                    row_count = q.value(0)
                    self.info_fields[_("全体行数")].setText(f"{row_count:,}")
                    tab_data.total_csv_rows = row_count

            # 読み込み時間
            tab_data.load_elapsed_time = time.time() - tab_data.start_time
            self.info_fields[_("読み込み時間")].setText(_("{sec:.2f} 秒").format(sec=tab_data.load_elapsed_time))

            # 現在の条件表示を更新
            tab_data.clear_search_state()
            self.update_query_label()

        except Exception as e:
            logger.warning("データベース情報表示更新エラー: %s", e)
            # エラー時は基本情報のみ設定
            self.info_fields[_("ファイル名")].setText(_("ZIP結合データベース"))
            self.info_fields[_("容量")].setText(_("計算中..."))
            self.info_fields[_("エンコーディング")].setText("UTF-8")
            self.info_fields[_("全体行数")].setText(_("計算中..."))
            self.info_fields[_("読み込み時間")].setText(_("計算中..."))

    def merge_zip_csv_triggered(self):
        merge_zip_csv_to_database(parent=self)

    def show_settings_dialog(self):
        """設定ダイアログ表示（リロード対応版）"""
        if self.is_loading:
            return

        dlg = SettingsDialog(self)
        if dlg.exec():
            self.settings = load_config()
            self.apply_user_settings()
            self._rebuild_shortcuts()
            self.statusBar().showMessage(_("設定を適用しました"), 3000)
            if dlg._restart_requested:
                self._restart_app()

    def _restart_app(self):
        """アプリを再起動する。"""
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        QApplication.instance().quit()

    def closeEvent(self, event):
        # インデックス構築中に閉じようとした場合は警告を表示する
        fts_building = (
            hasattr(self, 'fts_thread') and self.fts_thread and self.fts_thread.isRunning()
        ) or any(t.isRunning() for t in getattr(self, '_orphan_fts_threads', []))

        if fts_building:
            result = QMessageBox.warning(
                self,
                _("検索インデックス構築中"),
                _("現在、検索インデックスをバックグラウンドで構築しています。\n\n"
                  "このまま閉じると構築が中断され、\n"
                  "一時ファイルがシステムに残る場合があります。\n\n"
                  "閉じますか？"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            # ユーザーが「閉じる」を選択した場合: スレッドをキャンセルして続行
            if self.fts_thread and self.fts_thread.isRunning():
                self.fts_thread.cancel()
                self.fts_thread = None
            for t in list(getattr(self, '_orphan_fts_threads', [])):
                if t.isRunning():
                    t.cancel()

        # 読み込み中の場合はキャンセル（csv_thread を terminate & wait）
        if self.is_loading:
            self.cancel_loading()

        # 全てのタブを閉じる（常にインデックス0を削除してずれを防ぐ）
        for _i in range(len(self.tabs_data)):
            self.close_tab(0)

        super().closeEvent(event)
    
    def show_update_notice_if_needed(self):
        pass