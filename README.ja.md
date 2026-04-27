<p align="center">
  <img src="assets/long_logo.png" alt="CSView" width="640">
</p>

<h3 align="center">Windows 向け高速 CSV / TSV ビューア</h3>

<p align="center">
  日本語 | <a href="README.md">English</a>
</p>

<p align="center">
  <a href="https://github.com/Retro-Maid/CSView/releases/latest">
    <img src="https://img.shields.io/github/v/release/Retro-Maid/CSView?style=flat-square&label=%E3%83%80%E3%82%A6%E3%83%B3%E3%83%AD%E3%83%BC%E3%83%89&color=4a90d9&logo=github&logoColor=white" alt="Download">
  </a>
  <a href="https://github.com/Retro-Maid/CSView/actions/workflows/release.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/Retro-Maid/CSView/release.yml?style=flat-square&label=CI%2FCD&logo=githubactions&logoColor=white" alt="CI">
  </a>
  <a href="https://github.com/Retro-Maid/CSView/stargazers">
    <img src="https://img.shields.io/github/stars/Retro-Maid/CSView?style=flat-square&color=f4c542&logo=github&logoColor=white" alt="Stars">
  </a>
  <img src="https://img.shields.io/github/release-date/Retro-Maid/CSView?style=flat-square&label=%E3%83%AA%E3%83%AA%E3%83%BC%E3%82%B9%E6%97%A5&color=2ecc71" alt="Release Date">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-10%2F11-0078D4?style=flat-square&logo=windows&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/UI-PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/DB-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/パッケージ-PyInstaller-9b59b6?style=flat-square" alt="PyInstaller">
  <img src="https://img.shields.io/badge/インストーラー-Inno%20Setup%206-e67e22?style=flat-square" alt="Inno Setup">
  <img src="https://img.shields.io/badge/ライセンス-GPL%20v3-blue?style=flat-square&logo=gnu&logoColor=white" alt="License">
</p>

<p align="center">
  <a href="https://github.com/Retro-Maid/CSView/releases">
    <img src="https://img.shields.io/github/downloads/Retro-Maid/CSView/total?style=flat-square&label=%E7%B4%AF%E8%A8%88DL%E6%95%B0&color=28a745&logo=github&logoColor=white" alt="累計ダウンロード数">
  </a>
  <a href="https://github.com/Retro-Maid/CSView/releases/latest">
    <img src="https://img.shields.io/github/downloads/Retro-Maid/CSView/latest/total?style=flat-square&label=%E6%9C%80%E6%96%B0%E7%89%88DL%E6%95%B0&color=28a745&logo=github&logoColor=white" alt="最新版ダウンロード数">
  </a>
</p>

---

**CSView** は PyQt6 + SQLite を使った Windows 向けの高速軽量 CSV/TSV ビューアです。
ファイルを開いた際に SQLite データベースへ変換することで、大容量ファイルでも快適に閲覧・検索・抽出・編集が行えます。

---

## 機能一覧

| 機能 | 説明 |
|------|------|
| **大容量ファイル対応** | プログレッシブ読み込み — 変換中でもスクロール可能 |
| **全文検索** | FTS5 による高速検索、非対応環境は SQLite LIKE にフォールバック |
| **複数条件フィルター** | AND/OR を組み合わせた複雑な絞り込み条件を GUI で設定 |
| **検索・置換** | 置換前にプレビュー確認、置換済みセルをハイライト表示 |
| **SQL クエリ実行** | 読み込んだテーブルに対して任意の SQL を実行 |
| **セル編集** | インライン編集、編集済みセルは色でトラッキング |
| **上書き保存** | 編集内容を元の CSV ファイルにワンクリックで書き戻し |
| **エクスポート** | CSV/TSV 形式でエンコード選択保存（UTF-8 / BOM付き / Shift-JIS / UTF-16） |
| **分割保存** | ZIP 分割保存、AES-256 暗号化対応 |
| **ZIP 結合** | 分割 ZIP から CSV を結合して一括読み込み |
| **ドラッグ＆ドロップ** | ウィンドウに CSV/TSV をドロップするだけで開ける |
| **最近使ったファイル** | 履歴から素早く再オープン |
| **言語切替** | 日本語 / English — 設定から切替可能（再起動で適用） |
| **外観設定** | フォントサイズ・背景色・文字色・罫線色をカスタマイズ |

---

## パフォーマンス

### 他ツールとの比較

| | **CSView** | Modern CSV | EmEditor | CSViewer | Cassava | Excel | pandas |
|--|-----------|-----------|---------|---------|---------|-------|--------|
| **価格** | **無料 / OSS** | $39–59 | 有料 | 無料 | 無料 | 有料 | 無料 |
| **Windows** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Mac / Linux** | ❌ | ✅ | ❌ | ❌ | ❌ | 部分 | ✅ |
| **行数上限** | 無制限 | 20億行 | 1兆行以上 | 500万行† | 不明 | **1,048,576 行** | 無制限 |
| **メモリモデル** | ストリーミング + SQLite | ハイブリッド‡ | ストリーミング | ストリーミング | 全量ロード（推定） | 全量ロード | 全量ロード |
| **初回表示** | **~2秒**（読み込み中から閲覧可） | ロード後 | ロード後 | インデックス後 | ロード後 | ロード後 | N/A |
| **FTS5 / 瞬時全文検索** | ✅ **FTS5** | ❌ 検索のみ | ❌ 検索のみ | ❌ | ❌ | ❌ | ❌ |
| **SQL クエリ** | ✅ | ❌ | ❌ | ❌ | ❌ | 部分 | ✅（コード） |
| **複数条件フィルター** | ✅ | ✅ | ❌ | ✅ | ❌ | 部分 | ✅（コード） |
| **セル編集 + 保存** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅（コード） |
| **文字コード自動判定** | ✅ | 部分 | ✅ | 不明 | 部分（日本語） | 部分 | 部分 |
| **ZIP 分割 / 結合** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

† CSViewer: 同時表示の上限。‡ Modern CSV: 閲覧モードはストリーミング、編集モードは全量ロード。

> 競合ツールのデータは各社の公式ドキュメント・仕様に基づくものであり、CSView 開発者による実測値ではありません。

### 実測ベンチマーク

Windows 11 / Intel Core i7 / NVMe SSD で計測。
テストデータ: 8文字 ASCII ランダム文字列 × 10列。

#### 読み込み速度

| ファイル | 行数 | CSV サイズ | 初回表示 | フル読み込み | ピークメモリ |
|---------|------|----------|---------|------------|------------|
| 小規模 | 1万行 | 0.9 MB | 即時 | **0.45 秒** | 6.1 MB |
| 中規模 | 10万行 | 8.7 MB | **2.6 秒** | 5.1 秒 | 30.4 MB |
| 大規模 | 100万行 | 86.8 MB | **2.2 秒** | 51.6 秒 | 302.6 MB |
| 広幅 (50列) | 10万行 | 43.0 MB | **8.0 秒** | 16.1 秒 | 139.6 MB |

「初回表示」= バックグラウンドで読み込みを続けながら、行をスクロール・閲覧できるようになるまでの時間。

#### 検索速度（キーワード検索 / 10列）

| 行数 | FTS5（全文検索インデックス） | LIKE（フォールバック） | FTS5 倍率 |
|------|--------------------------|-------------------|---------|
| 1万行 | 0.8 ms | 6.4 ms | **8倍** |
| 10万行 | 1.8 ms | 61.4 ms | **34倍** |
| 100万行 | 1.8 ms | 602.2 ms | **334倍** |

FTS5 インデックスは読み込み完了後にバックグラウンドで自動構築されます。

> **再現方法**: プロジェクトルートで `python benchmark.py` を実行すると同じ数値を確認できます。

---

## ダウンロード

[**リリースページ**](https://github.com/Retro-Maid/CSView/releases/latest) から最新版をダウンロードしてください。

| ファイル | 説明 |
|----------|------|
| `CSView_Setup_x.x.x.exe` | **インストーラー版**（推奨）— `.csv` / `.tsv` のファイル関連付けも設定 |
| `CSView_portable.zip` | **ポータブル版** — ZIP を展開して `CSView.exe` を実行するだけ |

### ⚠️ Windows の保護メッセージについて

CSView は商用のコード署名証明書を使用していないため、インストーラー（.exe）を初回実行した際に
**「Windows によって PC が保護されました」** というダイアログが表示される場合があります。

これは個人・OSS 開発者が配布する署名なしソフトウェアでは一般的な動作です。
続行するには：

1. ダイアログの **「詳細情報」** をクリック
2. **「実行」** をクリック

ダイアログを表示させたくない場合は、**ポータブル ZIP 版**を使用してください（SmartScreen は起動しません）。

### 動作要件

- Windows 10 / 11（64bit）
- 追加インストール不要（自己完結型）

---

## 使い方

1. **ファイルを開く** — ウィンドウに CSV/TSV をドロップ、または **ファイル → 開く**
2. **検索** — `Ctrl+F` または **ツール → 検索**
3. **条件抽出** — **ツール → 条件抽出** で複数条件フィルターを設定
4. **置換** — `Ctrl+H` または **ツール → 置換**
5. **SQL クエリ** — **ツール → SQL クエリ実行** でテーブルに直接クエリ
6. **編集** — セルをダブルクリックしてインライン編集、編集済みセルは自動でハイライト
7. **上書き保存** — 💾 ボタンまたは `Ctrl+S` で元ファイルに書き戻し
8. **保存** — **ファイル → 名前を付けて保存** で現在の表示を出力
9. **設定** — 歯車アイコンから言語・外観・ショートカットを設定

---

## ソースからビルド

### 必要なもの

- Python 3.11
- Inno Setup 6（インストーラーのみ）

### 手順

```bat
git clone https://github.com/Retro-Maid/CSView.git
cd CSView
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt

:: ビルドなしで実行
python main.py

:: EXE ビルド
pyinstaller csv_viewer.spec --clean --noconfirm

:: インストーラー作成（Inno Setup 6 が必要）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\csv_viewer_installer.iss
```

### GitHub リリース

タグをプッシュすると CI が自動でビルド＆リリースを作成します。

```bat
git tag v1.x.x
git push origin v1.x.x
```

---

## ライセンス

このプロジェクトは [GNU General Public License v3.0](LICENSE) のもとで公開されています。

© 2026 Retro Maid

- [X (Twitter)](https://x.com/retro_maid)
- [GitHub](https://github.com/Retro-Maid)
