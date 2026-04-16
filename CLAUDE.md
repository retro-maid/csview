# CSView — 高速CSVビューア

## プロジェクト概要

PyQt6 + SQLite ベースの Windows 向け高速CSVビューア。
CSVをSQLiteに変換してQSqlTableModelで表示することで、大容量ファイルでも高速動作する。

## 技術スタック

| 項目 | 内容 |
|------|------|
| 言語 | Python 3.11 |
| UI | PyQt6 |
| DB | SQLite (QSqlite driver / 直接 sqlite3 モジュール) |
| エンコード検出 | chardet |
| ZIP暗号化 | pyzipper |
| パッケージング | PyInstaller (single EXE) + Inno Setup (インストーラー) |
| CI/CD | GitHub Actions |

## ディレクトリ構造

```
csview/
├── main.py                     # エントリーポイント
├── csv_viewer.spec             # PyInstaller設定
├── requirements.txt            # ランタイム依存
├── requirements-dev.txt        # ビルド用依存 (-r requirements.txt + pyinstaller)
├── version.json                # バージョン情報 (app_name, version, release_date 等)
├── CHANGELOG.md                # 更新履歴 (Keep a Changelog 形式)
├── assets/
│   ├── app_icon.ico / .png     # アプリアイコン
│   └── installer.ico           # インストーラーアイコン
├── installer/
│   └── csv_viewer_installer.iss  # Inno Setup スクリプト
├── converter/
│   └── convert_csv.py          # CSV→SQLite変換エンジン (chardet + csv streaming)
├── viewer/
│   ├── app.py                  # メインウィンドウ (CsvEditor, CsvLoadThread, DatabaseLoadThread)
│   ├── widgets/
│   │   ├── csv_tab.py          # ※ スタブファイル。実装は app.py 内にある
│   │   ├── filter_dialog.py    # 複数条件フィルターダイアログ
│   │   ├── highlight_delegate.py  # 置換ハイライト描画
│   │   ├── merge_csv.py        # ZIP分割CSV結合・DB化
│   │   ├── replace_dialog.py   # 置換ダイアログ
│   │   ├── save_current_view.py   # 現在ビューをCSV保存
│   │   ├── search_dialog.py    # 全文検索ダイアログ
│   │   ├── settings_dialog.py  # 設定ダイアログ + load_config / save_config
│   │   └── split_current_view.py  # 分割保存(ZIP)ダイアログ
│   ├── calc_widgets/
│   │   ├── statistics_calculator.py  # 統計計算UI (SQLiteStatisticsCalculator)
│   │   └── statistics_engine.py      # 統計計算エンジン (SQLiteStatisticsEngine)
│   └── utils/
│       └── config.py           # PyInstaller対応リソースパス / バージョン情報 / state管理
├── .github/
│   └── workflows/
│       └── release.yml         # タグpush時に自動ビルド＆リリース
└── .claude/
    └── commands/
        ├── build.md            # /build コマンド
        └── release.md          # /release コマンド
```

## 開発環境セットアップ

```bat
cd csview
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

## ビルド方法

### EXE のみ（開発確認用）
```bat
venv\Scripts\activate
pyinstaller csv_viewer.spec --clean --noconfirm
:: 出力: dist\CSView.exe
```

### インストーラー作成（配布用）
```bat
venv\Scripts\activate
pyinstaller csv_viewer.spec --clean --noconfirm
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\csv_viewer_installer.iss
:: 出力: installer\Output\CSView_Setup_<version>.exe
```

## GitHub リリースフロー

1. `CHANGELOG.md` の `[Unreleased]` セクションを新バージョンセクションに移動する
2. `version.json` の `version` と `release_date` を更新する
3. `git commit -m "chore: release v1.x.x"` でコミット
4. `git tag v1.x.x && git push origin master --tags` でタグをプッシュ
5. GitHub Actions が自動起動し、EXE とインストーラーをビルド・リリースに添付する
   - `CHANGELOG.md` の該当バージョンセクションが Release Notes に自動反映される
   - タグと `version.json` の不一致は CI で自動検出される

`/release` コマンドで一連の手順を案内できる。

## 既知のコード上の問題（次回作業時の注意）

### バグ・潜在的問題（✅ 2026-03-25 修正済み）

1. ~~設定ディレクトリの不一致~~ — `config.py` 側のデッドな `get_config_path()`/`load_config()` を削除済み
2. ~~`split_current_view.py` finally NameError~~ — `tmp_dir = None`, `part_files = []` を try 前に移動済み
3. ~~`loaded_csv_path` 参照ミス~~ — `csv_path` パラメータを追加し、呼び出し元から `tab_data.csv_path` を渡すよう修正済み
4. ~~`undo_last_action` の `in_search_mode` 誤設定~~ — `isinstance(prev_model, QSqlTableModel)` で正しく判定するよう修正済み

### バグ・設計問題（✅ 2026-03-25 追加修正済み）

1. ~~`display_row_limit` 設定が機能していない~~ — `complete_loading` と `apply_user_settings` に `fetchMore()` ループを追加して実装済み
2. ~~FTS5全文検索のエスケープが不完全~~ — FTS5フレーズ構文 `"..."` によるラップに変更済み（`keyword.replace('"', '""')` でフレーズ内エスケープ）

### デッドコード（✅ 2026-03-25 修正済み）

- `viewer/widgets/csv_tab.py` — 削除済み
- `app.py` — `show_error()`、`QFont` import、コメントアウト行、ラッパーメソッド を削除済み
- `viewer/utils/config.py` — `get_default_save_dir()`、`get_config_path()`、`load_config()` を削除済み
- `split_current_view.py` — `import time` の二重インポートを削除済み
- `csv_viewer.spec` — `hiddenimports` の `'polars'` を削除済み

### 設計上の問題（✅ 2026-03-25 修正済み）

- ~~`resource_path()` 関数の重複~~ — `utils/config.py` に一本化、`app.py` と `settings_dialog.py` は import に統一
- ~~`QSqlQuery` ローカルインポート~~ — トップレベルに統合済み
- ~~`undo_stack` が無制限リスト~~ — `deque(maxlen=20)` に変更済み
- ~~FTS5検索エスケープ不完全~~ — フレーズ構文 `"..."` に変更済み
- ~~`undo_last_action`/`reset_to_full_view` の重複ロジック~~ — `_restore_from_undo_stack` ヘルパーに集約済み（`reset_to_full_view` の `in_search_mode = True` バグも同時に修正）

## コード規約

- **ロギング**: `logging.getLogger(__name__)` を使用、`print()` は使わない
- **パス操作**: `os.path` より `pathlib.Path` を優先
- **SQL実行**: クエリはパラメータバインドを使用、文字列フォーマットで組み立てない（現状一部未対応）
- **スレッド**: UI操作はメインスレッドで行う（`QThread.finished` シグナル経由）
- **設定読み込み**: `from .widgets.settings_dialog import load_config` を使う（`utils/config.py` 側は使わない）
- **コメント**: 日本語コメント可。絵文字コメント（🆕, ✅ 等）は整理していく方針

## 注意事項

- `csv_viewer.spec` の `hiddenimports` に `'polars'` が残っているが polars は使用していない → 削除すること
- `requirements.txt` は UTF-8 で管理する（旧ファイルは誤って UTF-16LE だった）
- インストーラービルドは Inno Setup 6 が必要（CI では choco でインストール）
- Windows 専用アプリのため、ビルドは常に `windows-latest` で行う
