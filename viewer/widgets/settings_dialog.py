from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QSpinBox, QColorDialog,
    QPushButton, QHBoxLayout, QTabWidget, QWidget, QDialogButtonBox,
    QGroupBox, QGridLayout, QKeySequenceEdit, QTextBrowser, QScrollArea,
    QComboBox, QMessageBox
)
from PyQt6.QtGui import QColor, QPixmap, QKeySequence, QDesktopServices, QImage, QPainter, QIcon
from PyQt6.QtCore import Qt, QUrl, QByteArray
from PyQt6.QtSvg import QSvgRenderer
import json
import os
from ..utils.config import load_app_info, resource_path
from ..utils.i18n import _

DEFAULT_CONFIG = {
    "font_size": 12,
    "display_row_limit": 1000,
    "background_color": "#ffffff",
    "text_color": "#000000",
    "gridline_color": "#cccccc",
    "highlight_color": "#ffff00",
    "highlight_opacity": 100,
    "highlight_duration": 5,
    "cell_edit_color": "#ffebb4",
    "cell_edit_opacity": 80,
    "shortcuts": {},
    "recent_files": [],
    "language": "ja",
}

# ショートカットキーのデフォルト値と表示名
# (config_key, 表示名, デフォルトキーシーケンス)
SHORTCUT_DEFS = [
    ("undo",          "元に戻す / 全件表示に戻す",       "Ctrl+Z"),
    ("replace",       "置換ダイアログを開く",             "Ctrl+H"),
    ("copy",          "選択範囲をコピー",                 "Ctrl+C"),
    ("sql_query",     "SQLクエリ実行ダイアログを開く",     "Ctrl+Shift+Q"),
    ("overwrite_save","上書き保存",                       "Ctrl+S"),
]

DEFAULT_SHORTCUTS = {key: default for key, _, default in SHORTCUT_DEFS}


def get_config_path():
    config_dir = os.path.join(os.path.expanduser("~"), ".csv_viewer_app")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")

def load_config():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            # shortcuts は入れ子なので不足キーを個別補完する
            for k, v in DEFAULT_SHORTCUTS.items():
                if k not in config["shortcuts"]:
                    config["shortcuts"][k] = v
            # recent_files はリストのまま保持
            if not isinstance(config.get("recent_files"), list):
                config["recent_files"] = []
            if "language" not in config:
                config["language"] = "ja"
            return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    cfg = DEFAULT_CONFIG.copy()
    cfg["shortcuts"] = DEFAULT_SHORTCUTS.copy()
    cfg["recent_files"] = []
    return cfg

def save_config(config):
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("設定"))
        self.resize(520, 480)
        self.config = load_config()
        self._original_lang = self.config.get("language", "ja")
        self._restart_requested = False

        tabs = QTabWidget(self)
        self.general_tab = QWidget()
        self.highlight_tab = QWidget()
        self.shortcuts_tab = QWidget()
        self.about_tab = QWidget()
        self.usage_tab = QWidget()

        self.init_general_tab()
        self.init_highlight_tab()
        self.init_shortcuts_tab()
        self.init_about_tab()
        self.init_usage_tab()

        tabs.addTab(self.general_tab, _("表示設定"))
        tabs.addTab(self.highlight_tab, _("ハイライト設定"))
        tabs.addTab(self.shortcuts_tab, _("操作"))
        tabs.addTab(self.about_tab, _("ソフト情報"))
        tabs.addTab(self.usage_tab, _("使い方"))

        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)

        self.reset_btn = QPushButton(_("デフォルトに戻す"))
        self.reset_btn.clicked.connect(self.reset_to_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btns)

        layout.addLayout(btn_layout)

    def init_general_tab(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)

        font_group = QGroupBox(_("フォント設定"))
        font_layout = QGridLayout()
        font_layout.addWidget(QLabel(_("フォントサイズ:")), 0, 0)
        self.font_spin = QSpinBox()
        self.font_spin.setRange(6, 48)
        self.font_spin.setSuffix(" pt")
        self.font_spin.setValue(self.config.get("font_size", 12))
        font_layout.addWidget(self.font_spin, 0, 1)
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        performance_group = QGroupBox(_("パフォーマンス設定"))
        performance_layout = QGridLayout()
        performance_layout.addWidget(QLabel(_("一度に表示する行数:")), 0, 0)
        self.row_spin = QSpinBox()
        self.row_spin.setRange(100, 100000)
        self.row_spin.setSuffix(" 行")
        self.row_spin.setValue(self.config.get("display_row_limit", 1000))
        performance_layout.addWidget(self.row_spin, 0, 1)
        help_label = QLabel(_("※ 大きな値にすると表示が重くなる場合があります"))
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        performance_layout.addWidget(help_label, 1, 0, 1, 2)
        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)

        color_group = QGroupBox(_("テーブル色設定"))
        color_layout = QGridLayout()

        color_layout.addWidget(QLabel(_("背景色:")), 0, 0)
        self.bg_button = QPushButton()
        self.bg_color = QColor(self.config.get("background_color", "#ffffff"))
        self.update_button_color(self.bg_button, self.bg_color)
        self.bg_button.clicked.connect(self.choose_bg_color)
        color_layout.addWidget(self.bg_button, 0, 1)

        color_layout.addWidget(QLabel(_("文字色:")), 1, 0)
        self.fg_button = QPushButton()
        self.fg_color = QColor(self.config.get("text_color", "#000000"))
        self.update_button_color(self.fg_button, self.fg_color)
        self.fg_button.clicked.connect(self.choose_fg_color)
        color_layout.addWidget(self.fg_button, 1, 1)

        color_layout.addWidget(QLabel(_("罫線色:")), 2, 0)
        self.grid_button = QPushButton()
        self.grid_color = QColor(self.config.get("gridline_color", "#cccccc"))
        self.update_button_color(self.grid_button, self.grid_color)
        self.grid_button.clicked.connect(self.choose_grid_color)
        color_layout.addWidget(self.grid_button, 2, 1)

        color_group.setLayout(color_layout)
        layout.addWidget(color_group)

        lang_group = QGroupBox(_("言語 / Language:"))
        lang_layout = QGridLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("日本語", "ja")
        self.lang_combo.addItem("English", "en")
        current_lang = self.config.get("language", "ja")
        self.lang_combo.setCurrentIndex(0 if current_lang == "ja" else 1)
        lang_layout.addWidget(self.lang_combo, 0, 0)
        lang_note = QLabel(_("言語変更後はアプリを再起動してください"))
        lang_note.setStyleSheet("color: #888; font-size: 11px;")
        lang_layout.addWidget(lang_note, 1, 0)
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)

        layout.addStretch()
        self.general_tab.setLayout(layout)

    def init_highlight_tab(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)

        description = QLabel(_("置換処理時のセルハイライト表示に関する設定です。"))
        description.setStyleSheet("color: #333; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(description)

        color_group = QGroupBox(_("ハイライト色設定"))
        color_layout = QGridLayout()

        color_layout.addWidget(QLabel(_("ハイライト色:")), 0, 0)
        self.highlight_button = QPushButton()
        self.highlight_color = QColor(self.config.get("highlight_color", "#ffff00"))
        self.update_button_color(self.highlight_button, self.highlight_color)
        self.highlight_button.clicked.connect(self.choose_highlight_color)
        color_layout.addWidget(self.highlight_button, 0, 1)

        color_layout.addWidget(QLabel(_("透明度:")), 1, 0)
        opacity_layout = QHBoxLayout()
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(10, 255)
        self.opacity_spin.setValue(self.config.get("highlight_opacity", 100))
        self.opacity_spin.valueChanged.connect(self.update_highlight_preview)
        opacity_layout.addWidget(self.opacity_spin)
        opacity_layout.addWidget(QLabel(_("(10=透明 ～ 255=不透明)")))
        opacity_layout.addStretch()
        color_layout.addLayout(opacity_layout, 1, 1)

        color_group.setLayout(color_layout)
        layout.addWidget(color_group)

        duration_group = QGroupBox(_("表示時間設定"))
        duration_layout = QGridLayout()
        duration_layout.addWidget(QLabel(_("ハイライト表示時間:")), 0, 0)
        time_layout = QHBoxLayout()
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 60)
        self.duration_spin.setSuffix(" 秒")
        self.duration_spin.setValue(self.config.get("highlight_duration", 5))
        time_layout.addWidget(self.duration_spin)
        time_layout.addWidget(QLabel(_("(置換後、自動的にハイライトが消えるまでの時間)")))
        time_layout.addStretch()
        duration_layout.addLayout(time_layout, 0, 1)
        duration_group.setLayout(duration_layout)
        layout.addWidget(duration_group)

        preview_group = QGroupBox(_("プレビュー"))
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel(_("プレビュー表示"))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(60)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("border: 1px solid #ccc; padding: 10px;")
        self.update_highlight_preview()
        preview_layout.addWidget(self.preview_label)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # 編集済みセル色設定
        edit_color_group = QGroupBox(_("編集済みセルの色設定"))
        edit_color_layout = QGridLayout()

        edit_color_layout.addWidget(QLabel(_("編集済みセル色:")), 0, 0)
        self.edit_color_button = QPushButton()
        self.edit_cell_color = QColor(self.config.get("cell_edit_color", "#ffebb4"))
        self.update_button_color(self.edit_color_button, self.edit_cell_color)
        self.edit_color_button.clicked.connect(self.choose_edit_cell_color)
        edit_color_layout.addWidget(self.edit_color_button, 0, 1)

        edit_color_layout.addWidget(QLabel(_("透明度:")), 1, 0)
        edit_opacity_layout = QHBoxLayout()
        self.edit_opacity_spin = QSpinBox()
        self.edit_opacity_spin.setRange(10, 255)
        self.edit_opacity_spin.setValue(self.config.get("cell_edit_opacity", 80))
        edit_opacity_layout.addWidget(self.edit_opacity_spin)
        edit_opacity_layout.addWidget(QLabel(_("(10=透明 ～ 255=不透明)")))
        edit_opacity_layout.addStretch()
        edit_color_layout.addLayout(edit_opacity_layout, 1, 1)

        edit_color_group.setLayout(edit_color_layout)
        layout.addWidget(edit_color_group)

        layout.addStretch()
        self.highlight_tab.setLayout(layout)

    def init_shortcuts_tab(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        note = QLabel(_("キーを変更するには入力欄をクリックして新しいキーを押してください。\n変更は「OK」で保存後、次の操作から有効になります。"))
        note.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(note)

        group = QGroupBox(_("ショートカットキー設定"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        # ヘッダー行
        header_action = QLabel(_("操作"))
        header_action.setStyleSheet("font-weight: bold; color: #333;")
        header_key = QLabel(_("キー設定"))
        header_key.setStyleSheet("font-weight: bold; color: #333;")
        grid.addWidget(header_action, 0, 0)
        grid.addWidget(header_key, 0, 1)
        grid.addWidget(QLabel(""), 0, 2)  # クリアボタン列

        saved_shortcuts = self.config.get("shortcuts", {})
        self._key_edits: dict[str, QKeySequenceEdit] = {}

        for row_idx, (key, label, default) in enumerate(SHORTCUT_DEFS, start=1):
            seq_str = saved_shortcuts.get(key, default)

            action_label = QLabel(_(label))
            edit = QKeySequenceEdit(QKeySequence(seq_str))
            edit.setMaximumWidth(200)

            clear_btn = QPushButton(_("クリア"))
            clear_btn.setFixedWidth(60)
            clear_btn.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            clear_btn.clicked.connect(lambda _, e=edit: e.clear())

            grid.addWidget(action_label, row_idx, 0)
            grid.addWidget(edit, row_idx, 1)
            grid.addWidget(clear_btn, row_idx, 2)

            self._key_edits[key] = edit

        grid.setColumnStretch(0, 1)
        group.setLayout(grid)
        layout.addWidget(group)
        layout.addStretch()
        self.shortcuts_tab.setLayout(layout)

    @staticmethod
    def _svg_to_icon(svg_bytes: bytes, size: int = 24) -> QIcon:
        """SVGバイト列をQIconに変換する。"""
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        if not renderer.isValid():
            return QIcon()
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter()
        if not painter.begin(image):
            return QIcon()
        renderer.render(painter)
        painter.end()
        return QIcon(QPixmap.fromImage(image))

    def init_about_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        app_info = load_app_info()

        name_label = QLabel(app_info.get("app_name", "CSView"))
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        name_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(name_label)

        author_label = QLabel(_("製作者:") + f' {app_info.get("author", "")}')
        author_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        author_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(author_label)

        # X / GitHub ボタン
        _X_SVG = (
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            b'<path fill="white" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17'
            b'l-4.714-6.231-5.401 6.231H2.738l7.73-8.835L1.254 2.25H8.08l4.713 6.231'
            b' 5.451-7.731zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
        )
        _GITHUB_SVG = (
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            b'<path fill="white" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8'
            b' 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724'
            b'-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084'
            b'-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305'
            b' 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93'
            b' 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322'
            b' 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552'
            b' 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23'
            b' 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015'
            b' 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297'
            b'c0-6.627-5.373-12-12-12"/></svg>'
        )

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        x_url = app_info.get("x_url", "")
        if x_url:
            x_btn = QPushButton("  X (旧Twitter)")
            x_btn.setIcon(self._svg_to_icon(_X_SVG, 18))
            x_btn.setFixedSize(180, 40)
            x_btn.setStyleSheet(
                "QPushButton { background:#000; color:#fff; border-radius:6px;"
                " font-size:13px; font-weight:bold; }"
                " QPushButton:hover { background:#222; }"
            )
            x_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(x_url)))
            btn_layout.addWidget(x_btn)
            btn_layout.addSpacing(12)

        github_url = app_info.get("github_url", "")
        if github_url:
            gh_btn = QPushButton("  GitHub")
            gh_btn.setIcon(self._svg_to_icon(_GITHUB_SVG, 18))
            gh_btn.setFixedSize(180, 40)
            gh_btn.setStyleSheet(
                "QPushButton { background:#24292e; color:#fff; border-radius:6px;"
                " font-size:13px; font-weight:bold; }"
                " QPushButton:hover { background:#3a3f44; }"
            )
            gh_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(github_url)))
            btn_layout.addWidget(gh_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        self.about_tab.setLayout(layout)

    def init_usage_tab(self):
        from ..utils.i18n import get_lang
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet("font-size: 13px; font-family: Meiryo, sans-serif;")
        if get_lang() == "en":
            browser.setHtml("""<style>body{margin:16px;line-height:1.7;}h3{color:#333;border-bottom:1px solid #ccc;padding-bottom:4px;margin-top:20px;}ul{margin:4px 0 4px 20px;padding:0;}li{margin:2px 0;}kbd{background:#eee;border:1px solid #bbb;border-radius:3px;padding:1px 5px;font-size:12px;font-family:monospace;}</style>
<h3>Open a File</h3><ul><li>Drag & drop CSV, TSV, or ZIP files onto the window, or use <b>File → Open</b>.</li><li>Selecting multiple files opens each in a separate tab.</li><li>Multiple CSVs inside a ZIP are merged into one tab.</li><li>Use <b>File → Recent Files</b> to quickly reopen previous files.</li></ul>
<h3>Tab Operations</h3><ul><li>Double-click a tab to rename it.</li><li>Drag & drop tabs to reorder.</li><li>Click the × button to close a tab.</li></ul>
<h3>Search <kbd>Ctrl+F</kbd></h3><ul><li>Open the search dialog from <b>Tools → Search</b>.</li><li>A full-text search index (FTS5) is built in the background after loading.</li><li>LIKE search is available before the index is ready; fast full-text search activates after.</li></ul>
<h3>Replace <kbd>Ctrl+H</kbd></h3><ul><li>Open the replace dialog from <b>Tools → Replace</b>.</li><li>You can narrow replacement to specific columns.</li><li>Replaced cells are highlighted temporarily (color and duration configurable in Highlight settings).</li></ul>
<h3>Filter</h3><ul><li>Use <b>Tools → Filter</b> to narrow rows by multiple conditions.</li><li>Press <kbd>Ctrl+Z</kbd> or use <b>Tools → Undo (Show All)</b> to clear the filter.</li></ul>
<h3>SQL Query <kbd>Ctrl+Shift+Q</kbd></h3><ul><li>Run any SQL statement from <b>Tools → Run SQL Query</b>.</li><li>Data is stored in a table named <code>csv_data</code>.</li><li>SELECT results are shown in the table view.</li></ul>
<h3>Edit Mode <kbd>Ctrl+E</kbd></h3><ul><li>Toggle edit mode from <b>Tools → Edit Mode</b>.</li><li>Press <kbd>Ctrl+S</kbd> or click <b>Commit</b> to save changes.</li><li>Click <b>Discard</b> to undo all edits.</li><li>Changes are written back to the underlying SQLite database.</li></ul>
<h3>Copy <kbd>Ctrl+C</kbd></h3><ul><li>Select cells and press <kbd>Ctrl+C</kbd> to copy.</li><li>Multi-row and multi-column selections are supported. Output is tab-separated.</li></ul>
<h3>Save</h3><ul><li>Use <b>File → Save As</b> to save the current view as CSV.</li><li>Configure delimiter, encoding, headers, and BOM at save time.</li></ul>
<h3>Split & Save (ZIP)</h3><ul><li>Use <b>File → Split & Save As</b> to split data into parts and save as a ZIP file.</li><li>You can set a password on the ZIP file.</li></ul>
<h3>Undo / Show All <kbd>Ctrl+Z</kbd></h3><ul><li>Returns to the full dataset from search, filter, or SQL query results.</li><li>Up to 20 operations are remembered; press repeatedly to step back.</li></ul>""")
        else:
            browser.setHtml("""<style>body{margin:16px;line-height:1.7;}h3{color:#333;border-bottom:1px solid #ccc;padding-bottom:4px;margin-top:20px;}ul{margin:4px 0 4px 20px;padding:0;}li{margin:2px 0;}kbd{background:#eee;border:1px solid #bbb;border-radius:3px;padding:1px 5px;font-size:12px;font-family:monospace;}</style>
<h3>ファイルを開く</h3><ul><li>CSV・TSV・ZIPファイルをドラッグ＆ドロップ、またはメニュー「ファイル → 開く」で開けます。</li><li>複数ファイルを同時に選択すると、それぞれ別タブで開きます。</li><li>ZIP内の複数CSVファイルは結合して1つのタブに表示されます。</li><li>「ファイル → 最近使ったファイル」から以前開いたファイルを素早く開けます。</li></ul>
<h3>タブ操作</h3><ul><li>タブをダブルクリックすると名前を変更できます。</li><li>タブをドラッグ＆ドロップで並び替えられます。</li><li>タブの「×」ボタンで閉じられます。</li></ul>
<h3>検索 <kbd>Ctrl+F</kbd></h3><ul><li>「ツール → 検索」で全文検索ダイアログを開きます。</li><li>ファイルを開いた後、バックグラウンドで検索インデックス（FTS5）を構築します。</li><li>インデックス構築前でもLIKE検索が使えます。完了後は高速な全文検索に切り替わります。</li></ul>
<h3>置換 <kbd>Ctrl+H</kbd></h3><ul><li>「ツール → 置換」で置換ダイアログを開きます。</li><li>列を絞り込んで置換することもできます。</li><li>置換後のセルは一定時間ハイライト表示されます（色・時間は「ハイライト設定」で変更可）。</li></ul>
<h3>フィルター</h3><ul><li>「ツール → フィルター」で複数条件による絞り込みができます。</li><li><kbd>Ctrl+Z</kbd>または「ツール → 全件表示に戻す」でフィルターを解除します。</li></ul>
<h3>SQLクエリ実行 <kbd>Ctrl+Shift+Q</kbd></h3><ul><li>「ツール → SQLクエリ実行」で任意のSQL文を実行できます。</li><li>データはテーブル名<code>csv_data</code>に格納されています。</li></ul>
<h3>編集モード <kbd>Ctrl+E</kbd></h3><ul><li>「ツール → 編集モード」でセルを直接編集できます。</li><li><kbd>Ctrl+S</kbd>または「確定」ボタンで変更を保存します。</li><li>「破棄」ボタンで変更を取り消します。</li></ul>
<h3>コピー <kbd>Ctrl+C</kbd></h3><ul><li>セルを選択して<kbd>Ctrl+C</kbd>でコピーできます。</li><li>複数行・複数列の範囲選択にも対応。コピー内容はタブ区切り形式です。</li></ul>
<h3>保存</h3><ul><li>「ファイル → 保存」で現在表示中のデータをCSVとして保存します。</li><li>保存時に区切り文字・エンコーディング・ヘッダー有無・BOM付与などを設定できます。</li></ul>
<h3>分割保存（ZIP）</h3><ul><li>「ファイル → 分割保存（ZIP）」でデータを指定行数ごとに分割してZIPファイルで保存します。</li></ul>
<h3>元に戻す / 全件表示 <kbd>Ctrl+Z</kbd></h3><ul><li>検索・フィルター・SQLクエリの結果から元の全件表示に戻します。</li><li>操作履歴を最大20件保持しており、繰り返し押すことで順番に戻せます。</li></ul>""")
        layout.addWidget(browser)
        self.usage_tab.setLayout(layout)

    def _choose_color(self, attr: str, button, title: str, post_hook=None) -> None:
        current = getattr(self, attr)
        color = QColorDialog.getColor(initial=current, parent=self, title=title)
        if color.isValid():
            setattr(self, attr, color)
            self.update_button_color(button, color)
            if post_hook:
                post_hook()

    def choose_bg_color(self):
        self._choose_color("bg_color", self.bg_button, "背景色を選択")

    def choose_fg_color(self):
        self._choose_color("fg_color", self.fg_button, "文字色を選択")

    def choose_grid_color(self):
        self._choose_color("grid_color", self.grid_button, "罫線色を選択")

    def choose_highlight_color(self):
        self._choose_color("highlight_color", self.highlight_button, "ハイライト色を選択",
                           post_hook=self.update_highlight_preview)

    def choose_edit_cell_color(self):
        self._choose_color("edit_cell_color", self.edit_color_button, "編集済みセル色を選択")

    def update_button_color(self, button, color: QColor):
        hex_code = color.name()
        brightness = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
        text_color = "#000000" if brightness > 186 else "#ffffff"
        button.setText(hex_code)
        button.setStyleSheet(f"background-color: {hex_code}; color: {text_color}; border: 1px solid #999;")

    def update_highlight_preview(self):
        if hasattr(self, 'preview_label') and hasattr(self, 'highlight_color') and hasattr(self, 'opacity_spin'):
            color = self.highlight_color
            opacity = self.opacity_spin.value()
            rgba_color = f"rgba({color.red()}, {color.green()}, {color.blue()}, {opacity/255:.2f})"
            self.preview_label.setStyleSheet(f"""
                background-color: {rgba_color};
                border: 1px solid #ccc;
                padding: 10px;
                color: #000;
            """)
            self.preview_label.setText(f"ハイライトプレビュー\n透明度: {opacity}/255")

    def reset_to_defaults(self):
        # 表示設定
        self.font_spin.setValue(DEFAULT_CONFIG["font_size"])
        self.row_spin.setValue(DEFAULT_CONFIG["display_row_limit"])
        self.bg_color = QColor(DEFAULT_CONFIG["background_color"])
        self.fg_color = QColor(DEFAULT_CONFIG["text_color"])
        self.grid_color = QColor(DEFAULT_CONFIG["gridline_color"])
        self.update_button_color(self.bg_button, self.bg_color)
        self.update_button_color(self.fg_button, self.fg_color)
        self.update_button_color(self.grid_button, self.grid_color)

        # ハイライト設定
        self.highlight_color = QColor(DEFAULT_CONFIG["highlight_color"])
        self.opacity_spin.setValue(DEFAULT_CONFIG["highlight_opacity"])
        self.duration_spin.setValue(DEFAULT_CONFIG["highlight_duration"])
        self.update_button_color(self.highlight_button, self.highlight_color)
        self.update_highlight_preview()

        # 編集済みセル色設定
        self.edit_cell_color = QColor(DEFAULT_CONFIG["cell_edit_color"])
        self.edit_opacity_spin.setValue(DEFAULT_CONFIG["cell_edit_opacity"])
        self.update_button_color(self.edit_color_button, self.edit_cell_color)

        # ショートカット設定
        for key, _, default in SHORTCUT_DEFS:
            if key in self._key_edits:
                self._key_edits[key].setKeySequence(QKeySequence(default))

        # 言語設定
        self.lang_combo.setCurrentIndex(0)

    def accept(self):
        self.config["font_size"] = self.font_spin.value()
        self.config["display_row_limit"] = self.row_spin.value()
        self.config["background_color"] = self.bg_color.name()
        self.config["text_color"] = self.fg_color.name()
        self.config["gridline_color"] = self.grid_color.name()

        self.config["highlight_color"] = self.highlight_color.name()
        self.config["highlight_opacity"] = self.opacity_spin.value()
        self.config["highlight_duration"] = self.duration_spin.value()

        self.config["cell_edit_color"] = self.edit_cell_color.name()
        self.config["cell_edit_opacity"] = self.edit_opacity_spin.value()

        # ショートカット設定を収集
        shortcuts = {}
        for key in self._key_edits:
            seq = self._key_edits[key].keySequence()
            shortcuts[key] = seq.toString() if not seq.isEmpty() else ""
        self.config["shortcuts"] = shortcuts

        new_lang = self.lang_combo.currentData()
        self.config["language"] = new_lang

        save_config(self.config)
        super().accept()

        if new_lang != self._original_lang:
            if new_lang == "en":
                title = "Restart Required"
                msg   = "Would you like to restart the application to apply the language change?"
            else:
                title = "再起動の確認"
                msg   = "言語の変更を適用するため、ソフトの再起動を行いますか？"
            result = QMessageBox.question(
                None, title, msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if result == QMessageBox.StandardButton.Yes:
                self._restart_requested = True
