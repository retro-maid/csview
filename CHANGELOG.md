# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-04-27

### Fixed
- About タブ（設定 → ソフト情報）にバージョン番号・著作権表記・ライセンスリンクを追加
- インストーラーにライセンス同意画面を追加（GNU GPL v3 を表示）
- LICENSE ファイル先頭にプロジェクト固有の著作権表記を追加（`Copyright (C) 2026 Retro Maid`）

### Added
- README にダウンロード数バッジを追加（累計・最新バージョン別）

## [1.0.1] - 2026-04-01

### Added
- 大容量 CSV/TSV のプログレッシブ読み込み — 変換中からスクロール・閲覧が可能
- FTS5 による全文検索（非対応環境は SQLite LIKE にフォールバック）
- AND/OR を組み合わせた複数条件フィルターダイアログ
- 置換プレビュー確認 + 置換済みセルのハイライト表示
- 任意 SQL をテーブルに直接実行する SQL クエリ実行機能
- セルインライン編集 + 編集済みセルの色トラッキング
- 元ファイルへのワンクリック上書き保存（Ctrl+S）
- CSV/TSV エクスポート（UTF-8 / BOM付き UTF-8 / Shift-JIS / UTF-16）
- ZIP 分割保存（AES-256 暗号化オプション付き）
- 分割 ZIP から CSV を結合して一括読み込みする ZIP 結合機能
- CSV/TSV のドラッグ＆ドロップによる起動
- 最近使ったファイル履歴
- 日本語 / English の言語切り替え（設定から変更、再起動で適用）
- フォントサイズ・背景色・文字色・罫線色の外観カスタマイズ
- インストーラー版（ファイル関連付け付き）とポータブル版の 2 種類を提供
- 右クリック「プログラムから開く」での表示名を `CSView.exe` ではなく `CSView` で表示
- インストーラー起動時の再インストール / アンインストール / バージョン変更ダイアログ
- EXE への Version Resource 埋め込み（FileDescription / ProductName 等）
- CHANGELOG.md 連動の GitHub リリースノート自動生成 CI/CD パイプライン

[Unreleased]: https://github.com/Retro-Maid/CSView/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/Retro-Maid/CSView/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/Retro-Maid/CSView/releases/tag/v1.0.1
