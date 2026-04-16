# assets

このディレクトリにはアプリケーションのアイコンとロゴ画像が格納されています。

This directory contains the application icon and logo images.

---

## ファイル一覧 / File list

### `app_icon.ico`

アプリケーションアイコン。以下の用途で使用されます。

The application icon. Used in the following contexts:

- `CSView.exe` 本体のウィンドウアイコン / Window icon of `CSView.exe`
- タスクバー・デスクトップのショートカットアイコン / Taskbar and desktop shortcut icon
- Inno Setup インストーラーの SetupIcon / Inno Setup installer's SetupIcon
- PyInstaller ビルド時の EXE アイコン埋め込み / EXE icon embedded at PyInstaller build time

サイズ: 複数解像度（16×16 〜 256×256）を含む複合 ICO ファイル。

Size: Multi-resolution ICO file containing sizes from 16×16 to 256×256.

---

### `long_logo.png`

README に使用するワイドロゴ画像（横長バナー形式）。

Wide logo image (horizontal banner) used in the README.

- 推奨表示幅: 640px / Recommended display width: 640 px
- `README.md` および `README.ja.md` の冒頭に埋め込み済み / Embedded at the top of `README.md` and `README.ja.md`

---

## ビルドへの組み込み / Integration into the build

`csv_viewer.spec` の `datas` セクションで `app_icon.ico` が `assets/` フォルダごと PyInstaller バンドルに含まれます。

In `csv_viewer.spec`, the `datas` section bundles `app_icon.ico` into the PyInstaller output under the `assets/` folder.

```python
datas=[
    ('assets/app_icon.ico', 'assets'),
    ...
]
```

`long_logo.png` はランタイムには不要なため、バンドルには含まれません。

`long_logo.png` is not required at runtime and is therefore not included in the bundle.

---

## 注意事項 / Notes

- アイコン・ロゴの著作権は [Retro Maid](https://github.com/Retro-Maid) に帰属します。
- これらの素材を本プロジェクト以外の目的で使用・再配布することを禁じます。

- Copyright of the icons and logos belongs to [Retro Maid](https://github.com/Retro-Maid).
- Use or redistribution of these assets for purposes other than this project is prohibited.
