"""
i18n.py — 日英切り替えユーティリティ

Usage:
    from viewer.utils.i18n import _
    label = _("ファイル")  # lang=en → "File"

言語はアプリ起動時に set_lang() で設定する。
変更には再起動が必要。
"""

_LANG: str = "ja"

# 英語翻訳辞書（キー = 日本語文字列）
_EN: dict[str, str] = {
    # ---- メニュー ----
    "ファイル": "File",
    "開く": "Open",
    "最近使ったファイル": "Recent Files",
    "（履歴なし）": "(No History)",
    "履歴をクリア": "Clear History",
    "名前を付けて保存": "Save As",
    "名前を付けて分割して保存": "Split & Save As",
    "csvを結合して開く": "Merge & Open CSV",
    "設定": "Settings",
    "ツール": "Tools",
    "検索": "Search",
    "置換": "Replace",
    "条件抽出": "Filter",
    "元に戻す（全件表示）": "Undo (Show All)",
    "編集モード (Ctrl+E)": "Edit Mode (Ctrl+E)",
    "SQLクエリ実行": "Run SQL Query",

    # ---- 情報バー ----
    "ファイル情報": "File Info",
    "ファイル名": "File Name",
    "容量": "Size",
    "エンコーディング": "Encoding",
    "全体行数": "Total Rows",
    "読み込み時間": "Load Time",
    "現在の条件: なし": "Current Filter: None",
    "なし": "None",
    "ここに CSV / TSV ファイルをドラッグ＆ドロップしてください": "Drop CSV / TSV files here",

    # ---- 編集ツールバー ----
    "編集モード中 — 変更はまだ保存されていません": "Edit Mode — Changes not yet saved",
    "確定 (Ctrl+S)": "Commit (Ctrl+S)",
    "破棄": "Discard",

    # ---- 進捗・ステータス（静的部分） ----
    "処理中...": "Processing...",
    "キャンセル": "Cancel",
    "変換中: 0%": "Converting: 0%",
    "検索インデックス構築中: 0%": "Building search index: 0%",
    "検索インデックス構築完了 ✓": "Search index ready ✓",
    "データベース読み込み中...": "Loading database...",
    "CSVファイル読み込み": "Loading CSV",
    "データベース読み込み": "Loading Database",
    "残り時間計算中...": "Estimating time...",
    "高速検索インデックスの準備が完了しました": "Full-text search index is ready",
    "検索インデックスの構築をスキップしました（SQLite LIKE検索を使用）": "Search index skipped (using SQLite LIKE search)",
    "SQLite LIKEで検索中（大容量ファイルは時間がかかります）...": "Searching with LIKE (may be slow for large files)...",
    "操作を元に戻しました": "Action undone",
    "置換処理中...": "Replacing...",
    "設定を適用しました": "Settings applied",
    "編集モード: セルをダブルクリックまたはキー入力で編集できます": "Edit Mode: double-click or type to edit a cell",
    "変更を保存しました": "Changes saved",
    "変更を破棄しました": "Changes discarded",
    "クリップボードにコピーしました": "Copied to clipboard",

    # ---- 進捗・ステータス（フォーマット付き） ----
    "変換中: {pct}%  {count}行  {eta}": "Converting: {pct}%  {count} rows  {eta}",
    "残り約{sec:.0f}秒": "~{sec:.0f}s left",
    "残り約{min:.0f}分": "~{min:.0f}min left",
    "変換中: {pct}%": "Converting: {pct}%",
    "検索インデックス構築中: {pct}%": "Building search index: {pct}%",
    "読み込み完了: {filename} ({rows:,} 行)": "Loaded: {filename} ({rows:,} rows)",
    "{filename} を変換中... (スクロール可)": "Converting {filename}... (scrollable)",
    "{filename} を変換中... ({count:,} 行 読み込み済み)": "Converting {filename}... ({count:,} rows loaded)",
    "全件表示に戻しました ({rows:,} 行)": "Showing all rows ({rows:,} rows)",
    "検索完了: 0件": "Search complete: 0 results",
    "検索完了: {count:,} 件": "Search complete: {count:,} results",
    "置換完了: {count:,} 箇所を置換しました (所要時間: {elapsed:.2f}秒)": "Replaced {count:,} occurrences ({elapsed:.2f}s)",
    "{rows} 行 × {cols} 列をコピーしました": "Copied {rows} rows × {cols} columns",
    "ZIP結合データベース読み込み完了: {name} ({rows:,} 行)": "ZIP merged DB loaded: {name} ({rows:,} rows)",

    # ---- QMessageBox タイトル ----
    "変換処理が継続中です": "Conversion in Progress",
    "⚠ 警告: データが不完全な状態です": "⚠ Warning: Incomplete Data",
    "検索結果": "Search Results",
    "検索エラー": "Search Error",
    "抽出エラー": "Filter Error",
    "置換プレビュー": "Replace Preview",
    "置換エラー": "Replace Error",
    "置換完了": "Replace Complete",
    "読み込みエラー": "Load Error",
    "ファイルエラー": "File Error",
    "エラー": "Error",
    "警告": "Warning",
    "コピーエラー": "Copy Error",
    "保存エラー": "Save Error",
    "タブ名を変更": "Rename Tab",
    "ファイルが見つかりません": "File Not Found",
    "検索インデックス構築中": "Building Search Index",
    "アップデート完了": "Update Complete",
    "入力エラー": "Input Error",
    "削除不可": "Cannot Delete",

    # ---- QMessageBox 本文 ----
    "続行しますか？": "Continue?",
    "本当に続行しますか？": "Are you sure you want to continue?",
    "現在CSVの変換処理が継続中のため、表示されているデータは全件ではありません。\nこの状態で操作を実行すると、不完全なデータが対象となり結果が不正確になる可能性があります。\n\n変換が完了してから実行することを推奨します。\n\n続行しますか？":
        "CSV conversion is still in progress. The data shown may be incomplete.\n"
        "Running this operation now may produce inaccurate results.\n\n"
        "It is recommended to wait until conversion finishes.\n\nContinue anyway?",
    "【重要】現在CSVの変換処理が継続中のため、データは不完全な状態です。\n\nこの状態で分割保存を実行すると:\n  • 変換済みの行のみが保存されます\n  • 全データを含まない不完全なファイルが生成されます\n  • 後からデータを追加する手段はありません\n\n変換が完了するまで待ってから実行することを強く推奨します。\n\n本当に続行しますか？":
        "[IMPORTANT] CSV conversion is still in progress. The data is incomplete.\n\n"
        "Performing a split save now will:\n"
        "  • Save only the rows converted so far\n"
        "  • Produce an incomplete file missing some data\n"
        "  • Leave no way to add the remaining data later\n\n"
        "It is strongly recommended to wait until conversion finishes.\n\nAre you sure you want to continue?",
    "現在、検索インデックスをバックグラウンドで構築しています。\n\nこのまま閉じると構築が中断され、\n一時ファイルがシステムに残る場合があります。\n\n閉じますか？":
        "The search index is being built in the background.\n\n"
        "Closing now will interrupt the build and\ntemporary files may remain on your system.\n\nClose anyway?",
    "「{search}」を「{replace}」に置換します。": 'Replace "{search}" with "{replace}".',
    "対象件数: {count:,} 件\n\n置換を実行しますか？": "Matches: {count:,}\n\nProceed with replacement?",
    "{name} をバージョン {version} に更新しました！": "Updated {name} to version {version}!",
    "新機能が追加されました。": "New features have been added.",
    '全文検索 "{keyword}"': 'Full-text search: "{keyword}"',
    'LIKE検索 "{keyword}"': 'LIKE search: "{keyword}"',
    '置換完了: "{search}" → "{replace}" ({count:,}箇所)': 'Replaced: "{search}" → "{replace}" ({count:,} cells)',
    "置換対象が見つかりませんでした。": "No matches found.",
    "新しいタブ名を入力してください:": "Enter new tab name:",
    "閉じますか？": "Close anyway?",
    "検索文字列を入力してください。": "Please enter a search term.",
    "少なくとも1つのグループは必要です。": "At least one group is required.",
    "空の値があります。すべての条件を入力してください。": "Some values are empty. Please fill in all conditions.",
    "表示中のデータがありません。": "No data to display.",
    "出力する列が選択されていません。": "No columns selected for output.",
    "ファイル名を指定してください。": "Please specify a file name.",
    "暗号化する場合はパスワードを入力してください。": "Please enter a password for encryption.",
    "有効なZIPファイルを選択してください。": "Please select a valid ZIP file.",
    "出力データベース名を入力してください。": "Please enter an output database name.",

    # ---- ファイルダイアログ ----
    "CSVファイルを選択": "Select CSV File",
    "CSV Files (*.csv *.tsv);;All Files (*.*)": "CSV Files (*.csv *.tsv);;All Files (*.*)",
    "保存先を指定": "Save As",
    "CSV ファイル (*.csv)": "CSV Files (*.csv)",
    "TSV ファイル (*.tsv)": "TSV Files (*.tsv)",
    "保存先ZIPを指定": "Save ZIP As",
    "Zip files (*.zip)": "ZIP Files (*.zip)",
    "分割CSVのZIPファイルを選択": "Select ZIP of Split CSVs",
    "ZIP files (*.zip);;All files (*.*)": "ZIP files (*.zip);;All files (*.*)",

    # ---- 情報値 ----
    "計算不可": "N/A",
    "不明": "Unknown",
    "計算中...": "Calculating...",
    "ZIP結合データベース": "ZIP Merged DB",
    "UTF-8 (データベース)": "UTF-8 (Database)",
    " (ZIP結合)": " (ZIP merged)",
    "前の状態に戻りました": "Reverted to previous state",
    "全文検索": "Full-text search",
    "LIKE検索": "LIKE search",

    # ---- 保存系進捗 ----
    "ファイル保存": "Saving File",
    "保存処理を開始しています...": "Starting save...",
    "保存完了": "Save Complete",
    "分割保存": "Split Save",
    "分割保存を開始しています...": "Starting split save...",
    "ZIPファイル作成中...": "Creating ZIP...",
    "分割保存完了": "Split Save Complete",

    # ---- ZIP結合 ----
    "ZIP分割CSV結合・DB化": "Merge Split CSV (ZIP) to DB",
    "ZIPファイル:": "ZIP File:",
    "出力DB名:": "Output DB Name:",
    "ZIPファイル内容プレビュー:": "ZIP Contents Preview:",
    "参照...": "Browse...",
    "パスワード付きZIP": "Password-protected ZIP",
    "ZIPファイルのパスワードを入力": "Enter ZIP password",
    "一時ディレクトリを作成中...": "Creating temporary directory...",
    "ZIPファイルを展開中...": "Extracting ZIP...",
    "CSVファイルを結合中...": "Merging CSV files...",
    "処理を準備中...": "Preparing...",
    "ZIP結合・DB化": "Merge ZIP to DB",
    "結合・DB化完了": "Merge & Convert Complete",
    "情報": "Info",

    # ---- 検索ダイアログ ----
    "検索ワード:": "Search term:",

    # ---- 置換ダイアログ ----
    "検索文字列:": "Search:",
    "置換文字列:": "Replace with:",
    "大文字・小文字を区別する": "Case sensitive",
    "単語単位で検索": "Whole word",
    "すべて置換": "Replace All",
    "プレビュー": "Preview",

    # ---- 条件抽出ダイアログ ----
    "複数条件の抽出": "Multi-condition Filter",
    "=（一致）": "= (equals)",
    "!＝（不一致）": "≠ (not equals)",
    ">（より大きい）": "> (greater than)",
    ">=（以上）": ">= (at least)",
    "<（より小さい）": "< (less than)",
    "<=（以下）": "<= (at most)",
    "LIKE（含む）": "LIKE (contains)",
    "列:": "Column:",
    "条件:": "Operator:",
    "値:": "Value:",
    "条件グループ": "Condition Group",
    "前グループとの結合:": "Join with previous group:",
    "このグループ内の条件を:": "Combine conditions with:",
    "＋ 条件追加": "+ Add Condition",
    "－ 条件削除": "– Remove Condition",
    "＋ グループ追加": "+ Add Group",
    "抽出実行": "Apply Filter",

    # ---- 分割保存ダイアログ ----
    "分割保存オプション": "Split Save Options",
    "分割設定": "Split Settings",
    "ファイル形式": "File Format",
    "文字コード（エンコーディング）": "Encoding",
    "ZIP暗号化": "ZIP Encryption",
    "分割数:": "Split count:",
    "ファイル名（拡張子不要）:": "File name (no extension):",
    "パスワード:": "Password:",
    "※ Excel で開く場合は「UTF-8 BOM付き」または「Shift-JIS」を推奨": "※ For Excel, 'UTF-8 with BOM' or 'Shift-JIS' is recommended",
    "パスワード付きで暗号化（AES-256）": "Encrypt with password (AES-256)",
    "分割エラー": "Split Error",
    "分割中にエラーが発生しました": "An error occurred while splitting",

    # ---- 設定ダイアログ ----
    "表示設定": "Display",
    "ハイライト設定": "Highlight",
    "操作": "Shortcuts",
    "ソフト情報": "About",
    "使い方": "Help",
    "フォント設定": "Font",
    "フォントサイズ:": "Font size:",
    "パフォーマンス設定": "Performance",
    "一度に表示する行数:": "Rows displayed at once:",
    "※ 大きな値にすると表示が重くなる場合があります": "※ Large values may slow down display",
    "テーブル色設定": "Table Colors",
    "背景色:": "Background:",
    "文字色:": "Text color:",
    "罫線色:": "Grid color:",
    "ハイライト色設定": "Highlight Color",
    "ハイライト色:": "Highlight color:",
    "透明度:": "Opacity:",
    "(10=透明 ～ 255=不透明)": "(10=transparent – 255=opaque)",
    "表示時間設定": "Display Duration",
    "ハイライト表示時間:": "Highlight duration:",
    "(置換後、自動的にハイライトが消えるまでの時間)": "(time until highlight fades after replace)",
    "プレビュー表示": "Preview",
    "置換処理時のセルハイライト表示に関する設定です。": "Settings for cell highlight display after replace.",
    "キーを変更するには入力欄をクリックして新しいキーを押してください。\n変更は「OK」で保存後、次の操作から有効になります。": "Click an input field and press a new key to change it.\nChanges take effect after clicking OK.",
    "ショートカットキー設定": "Shortcut Keys",
    "キー設定": "Key",
    "クリア": "Clear",
    "デフォルトに戻す": "Reset to Defaults",
    "製作者:": "Created by:",
    "言語 / Language:": "Language / 言語:",
    "言語変更後はアプリを再起動してください": "Please restart the app to apply language changes",

    # ---- ショートカット名 ----
    "元に戻す / 全件表示に戻す": "Undo / Show All",
    "置換ダイアログを開く": "Open Replace Dialog",
    "選択範囲をコピー": "Copy Selection",
    "SQLクエリ実行ダイアログを開く": "Open SQL Query Dialog",
    "編集モードの切替": "Toggle Edit Mode",
    "編集内容を確定して保存": "Commit & Save Edits",

    # ---- 読み込み時間 ----
    "{sec:.2f} 秒": "{sec:.2f} sec",

    # ---- 条件ラベル ----
    "現在の条件: {condition}　｜　該当件数: {count:,} 件": "Current filter: {condition}  |  Rows: {count:,}",

    # ---- 置換完了ダイアログ ----
    "{replaced:,} 箇所を置換しました。\n所要時間: {elapsed:.2f}秒\n置換されたセルが{sec}秒間ハイライトされます。":
        "Replaced {replaced:,} occurrences.\nTime: {elapsed:.2f}s\nCells highlighted for {sec}s.",

    # ---- SQLクエリダイアログ ----
    "ダブルクリックで挿入": "Double-click to insert",
    "テーブル名": "Table name",
    "── 列 ──": "── Columns ──",
    "▶ 実行 (F5)": "▶ Run (F5)",
    "0 行": "0 rows",
    "{n} 行": "{n} rows",
    "結果をCSVで保存": "Export to CSV",
    "データベース接続が開いていません。": "Database connection is not open.",
    "エラー: {msg}": "Error: {msg}",
    "CSVファイルを保存": "Save CSV File",
    "CSV ファイル (*.csv);;すべてのファイル (*)": "CSV Files (*.csv);;All Files (*)",
    "CSVファイルを保存しました:\n{path}": "CSV saved to:\n{path}",
    "保存するデータがありません。先にSQLを実行してください。": "No data to save. Please run a SQL query first.",
    # ---- 保存オプションダイアログ ----
    "保存オプション": "Save Options",
    "※ 通常は「UTF-8 BOM付き」を推奨": "※ UTF-8 with BOM is recommended for most cases",
    "列の詳細設定（任意）": "Column Settings (optional)",
    "未設定（全列・元の列名・テキスト型で出力）": "Default (all columns, original names, text type)",
    "設定する...": "Configure...",
    "{included}/{total} 列を出力": "{included}/{total} columns included",
    "{count} 列を列名変更": "{count} column(s) renamed",
    "{count} 列に型指定": "{count} column(s) typed",
    "、": ", ",

    # ---- エンコーディング・フォーマット選択肢 ----
    "UTF-8 (BOMなし)": "UTF-8 (no BOM)",
    "UTF-8 BOM付き": "UTF-8 with BOM",
    "UTF-16 (BOM付き)": "UTF-16 (with BOM)",
    "GBK（中国語簡体字）": "GBK (Simplified Chinese)",
    "Big5（中国語繁体字）": "Big5 (Traditional Chinese)",
    "CP949（韓国語）": "CP949 (Korean)",
    "CSV (.csv)  カンマ区切り": "CSV (.csv)  Comma-separated",
    "TSV (.tsv)  タブ区切り": "TSV (.tsv)  Tab-separated",

    # ---- 上書き保存 ----
    "上書き保存 (Ctrl+S)": "Overwrite Save (Ctrl+S)",
    "上書き保存": "Overwrite Save",
    "以下のファイルに上書きしますか？\n\n{path}": "Overwrite the following file?\n\n{path}",
    "元のCSVファイルのパスが不明です。「名前を付けて保存」をお使いください。": "Original CSV path is unknown. Please use Save As.",
    "元のCSVファイルが見つかりません:\n{path}\n「名前を付けて保存」をお使いください。": "Original CSV file not found:\n{path}\nPlease use Save As.",
    "上書き保存しました: {path}": "Saved: {path}",
    "上書き保存に失敗しました:\n{error}": "Failed to overwrite:\n{error}",
    # ---- 編集済みセル設定 ----
    "編集済みセルの色設定": "Edited Cell Color",
    "編集済みセル色:": "Edited cell color:",
    "上書き保存": "Overwrite Save",
}


def set_lang(lang: str) -> None:
    """アプリ起動時に呼び出して言語を設定する。"""
    global _LANG
    if lang in ("ja", "en"):
        _LANG = lang


def get_lang() -> str:
    return _LANG


def _(text: str) -> str:
    """現在の言語に対応した文字列を返す。未登録はそのまま返す。"""
    if _LANG == "ja":
        return text
    return _EN.get(text, text)
