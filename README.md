<p align="center">
  <img src="assets/long_logo.png" alt="CSView" width="640">
</p>

<h3 align="center">High-speed CSV / TSV Viewer for Windows</h3>

<p align="center">
  <a href="README.ja.md">日本語</a> | English
</p>

<p align="center">
  <a href="https://github.com/Retro-Maid/CSView/releases/latest">
    <img src="https://img.shields.io/github/v/release/Retro-Maid/CSView?style=flat-square&label=Download&color=4a90d9&logo=github&logoColor=white" alt="Download">
  </a>
  <a href="https://github.com/Retro-Maid/CSView/actions/workflows/release.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/Retro-Maid/CSView/release.yml?style=flat-square&label=CI%2FCD&logo=githubactions&logoColor=white" alt="CI">
  </a>
  <a href="https://github.com/Retro-Maid/CSView/stargazers">
    <img src="https://img.shields.io/github/stars/Retro-Maid/CSView?style=flat-square&color=f4c542&logo=github&logoColor=white" alt="Stars">
  </a>
  <img src="https://img.shields.io/github/release-date/Retro-Maid/CSView?style=flat-square&label=Released&color=2ecc71" alt="Release Date">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-10%2F11-0078D4?style=flat-square&logo=windows&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/UI-PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/DB-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Packaged%20with-PyInstaller-9b59b6?style=flat-square" alt="PyInstaller">
  <img src="https://img.shields.io/badge/Installer-Inno%20Setup%206-e67e22?style=flat-square" alt="Inno Setup">
  <img src="https://img.shields.io/badge/License-GPL%20v3-blue?style=flat-square&logo=gnu&logoColor=white" alt="License">
</p>

---

**CSView** is a fast, lightweight CSV/TSV viewer for Windows built with PyQt6 and SQLite.
It handles large files smoothly by converting them to an in-memory SQLite database on load, enabling instant search, filter, and SQL queries without loading everything into RAM.

---

## Features

| Feature | Description |
|---------|-------------|
| **Large file support** | Progressive loading — browse while the file is still being imported |
| **Full-text search** | FTS5-powered instant search, falls back to SQLite LIKE for compatibility |
| **Multi-condition filter** | Build complex AND/OR filter rules with a visual dialog |
| **Find & Replace** | Preview before applying; highlights replaced cells |
| **SQL query** | Run arbitrary SQL against the loaded table |
| **Cell editing** | Edit cells inline; edited cells are highlighted for easy tracking |
| **Overwrite save** | Save edits back to the original CSV file with a single click |
| **Export** | Save as CSV/TSV with selectable encoding (UTF-8, UTF-8 BOM, Shift-JIS, UTF-16) |
| **Split save** | Split and save as a ZIP archive, with optional AES-256 encryption |
| **ZIP merge** | Merge split CSVs from a ZIP back into a single dataset |
| **Drag & drop** | Drop a CSV/TSV file onto the window to open it |
| **Recent files** | Quick access to previously opened files |
| **Language** | Japanese / English — switchable from Settings |
| **Appearance** | Configurable font size, background, text, and grid colors |

---

## Performance

### Comparison with other tools

| | **CSView** | Modern CSV | EmEditor | CSViewer | Cassava | Excel | pandas |
|--|-----------|-----------|---------|---------|---------|-------|--------|
| **Price** | **Free / OSS** | $39–59 | Paid | Free | Free | Paid | Free |
| **Windows** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Mac / Linux** | ❌ | ✅ | ❌ | ❌ | ❌ | Partial | ✅ |
| **Row limit** | Unlimited | 2 billion | 1 trillion+ | 5 million† | Unknown | **1,048,576** | Unlimited |
| **Memory model** | Streaming + SQLite | Hybrid‡ | Streaming | Streaming | Full load (est.) | Full load | Full load |
| **First display** | **~2 s** (still loading) | After load | After load | After index | After load | After load | N/A |
| **FTS5 / instant search** | ✅ **FTS5** | ❌ Find only | ❌ Find only | ❌ | ❌ | ❌ | ❌ |
| **SQL query** | ✅ | ❌ | ❌ | ❌ | ❌ | Partial | ✅ (code) |
| **Multi-condition filter** | ✅ | ✅ | ❌ | ✅ | ❌ | Partial | ✅ (code) |
| **Cell editing + save** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ (code) |
| **Encoding auto-detect** | ✅ | Partial | ✅ | Unknown | Partial (JP) | Partial | Partial |
| **ZIP / split / merge** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

† CSViewer: simultaneous display limit. ‡ Modern CSV: streaming in read-only mode, full load in edit mode.

> Competitor data is based on official documentation and public specifications, not measured by CSView's authors.
> pandas has no built-in GUI; comparison is for programmatic CSV loading.

### Measured benchmarks

Tested on Windows 11, Intel Core i7, NVMe SSD.
CSV data: 10 columns of random 8-character ASCII strings.

#### Load time

| File | Rows | CSV size | First display | Full load | Peak memory |
|------|------|----------|--------------|-----------|-------------|
| Small  | 10,000  | 0.9 MB  | instant      | **0.45 s** | 6.1 MB  |
| Medium | 100,000 | 8.7 MB  | **2.6 s**    | 5.1 s      | 30.4 MB |
| Large  | 1,000,000 | 86.8 MB | **2.2 s**  | 51.6 s     | 302.6 MB |
| Wide (50 cols) | 100,000 | 43.0 MB | **8.0 s** | 16.1 s  | 139.6 MB |

"First display" = time until rows are visible and scrollable while the rest continues loading in the background.

#### Search speed (keyword search, 10 columns)

| Rows | FTS5 (full-text index) | LIKE (fallback) | FTS5 speedup |
|------|----------------------|-----------------|--------------|
| 10,000   | 0.8 ms  | 6.4 ms   | **8×**   |
| 100,000  | 1.8 ms  | 61.4 ms  | **34×**  |
| 1,000,000 | 1.8 ms | 602.2 ms | **334×** |

FTS5 index is built automatically in the background after loading.

> **Reproduce**: `python benchmark.py` in the project root generates these numbers on your machine.

---

## Download

Head to the [**Releases**](https://github.com/Retro-Maid/CSView/releases/latest) page and download one of the following:

| File | Description |
|------|-------------|
| `CSView_Setup_x.x.x.exe` | **Installer** (recommended) — adds file associations for `.csv` / `.tsv` |
| `CSView_portable.zip` | **Portable** — extract and run `CSView.exe` directly |

### ⚠️ Windows SmartScreen Warning

Because CSView is not code-signed with a commercial certificate, Windows SmartScreen may display
**"Windows protected your PC"** when you run the installer for the first time.

This is expected behavior for open-source software distributed without a paid certificate.
To proceed:

1. Click **"More info"** in the SmartScreen dialog
2. Click **"Run anyway"**

If you prefer to avoid this dialog entirely, use the **portable ZIP** version instead — it does not trigger SmartScreen.

### System Requirements

- Windows 10 / 11 (64-bit)
- No runtime installation required (self-contained)

---

## Usage

1. **Open a file** — drag and drop a CSV/TSV onto the window, or use **File → Open**
2. **Search** — press `Ctrl+F` or use **Tools → Search**
3. **Filter** — use **Tools → Filter** to build multi-condition rules
4. **Replace** — press `Ctrl+H` or use **Tools → Replace**
5. **SQL** — use **Tools → Run SQL Query** to query the table directly
6. **Edit** — double-click any cell to edit; edited cells are highlighted automatically
7. **Overwrite save** — click the 💾 button or press `Ctrl+S` to save back to the original file
8. **Export** — use **File → Save As** to export the current view
9. **Settings** — configure language, appearance, and shortcuts via the gear icon

---

## Building from Source

### Requirements

- Python 3.11
- Inno Setup 6 (for installer only)

### Steps

```bat
git clone https://github.com/Retro-Maid/CSView.git
cd CSView
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt

:: Run without building
python main.py

:: Build EXE
pyinstaller csv_viewer.spec --clean --noconfirm

:: Build installer (requires Inno Setup 6)
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\csv_viewer_installer.iss
```

### GitHub Release

Pushing a tag triggers the CI pipeline which builds and publishes the release automatically:

```bat
git tag v1.x.x
git push origin v1.x.x
```

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

© 2026 Retro Maid

- [X (Twitter)](https://x.com/retro_maid)
- [GitHub](https://github.com/Retro-Maid)
