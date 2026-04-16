"""
benchmark.py - CSView パフォーマンスベンチマーク

使い方:
    python benchmark.py

計測内容:
    1. 各サイズの CSV 生成（初回のみ）
    2. CSV → SQLite 変換時間（初回表示 / フル変換）
    3. ピークメモリ使用量
    4. FTS5 全文検索速度
    5. LIKE 検索速度（FTS5 との比較）

出力:
    コンソールに結果表示 + benchmark_results.md に保存
"""

import csv
import os
import random
import sqlite3
import string
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from converter.convert_csv import convert_csv_to_sqlite, build_fts5_index

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────
BENCH_DIR = Path(__file__).parent / "benchmark_data"
BENCH_DIR.mkdir(exist_ok=True)

SCENARIOS = [
    {"label": "小規模 (1万行 / 10列)",   "rows": 10_000,    "cols": 10},
    {"label": "中規模 (10万行 / 10列)",  "rows": 100_000,   "cols": 10},
    {"label": "大規模 (100万行 / 10列)", "rows": 1_000_000, "cols": 10},
    {"label": "広幅   (10万行 / 50列)",  "rows": 100_000,   "cols": 50},
]

SEARCH_KEYWORD = "TARGET_KEYWORD"  # 検索キーワード（CSVに埋め込む）


# ─────────────────────────────────────────────
# CSV 生成
# ─────────────────────────────────────────────
def generate_csv(path: Path, num_rows: int, num_cols: int) -> None:
    """テスト用 CSV を生成する。既存ファイルはスキップ。"""
    if path.exists():
        print(f"  [skip] {path.name} は既存")
        return

    print(f"  生成中: {path.name} ({num_rows:,} 行 / {num_cols} 列)...")
    t0 = time.perf_counter()

    headers = [f"col_{i:02d}" for i in range(num_cols)]
    # 1% の確率で検索キーワードを埋め込む
    target_row = num_rows // 2

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in range(num_rows):
            if r == target_row:
                row = [SEARCH_KEYWORD] + [
                    "".join(random.choices(string.ascii_letters + string.digits, k=8))
                    for _ in range(num_cols - 1)
                ]
            else:
                row = [
                    "".join(random.choices(string.ascii_letters + string.digits, k=8))
                    for _ in range(num_cols)
                ]
            writer.writerow(row)

    elapsed = time.perf_counter() - t0
    size_mb = path.stat().st_size / 1024 / 1024
    print(f"  完了: {size_mb:.1f} MB ({elapsed:.1f}s)")


# ─────────────────────────────────────────────
# 変換ベンチマーク
# ─────────────────────────────────────────────
def bench_convert(csv_path: Path) -> dict:
    """CSV → SQLite 変換を計測する。"""
    db_path = str(csv_path.with_suffix(".db"))

    partial_time = None  # 初回表示可能になるまでの時間

    def on_partial():
        nonlocal partial_time
        partial_time = time.perf_counter() - t0

    tracemalloc.start()
    t0 = time.perf_counter()

    convert_csv_to_sqlite(
        str(csv_path),
        db_path,
        progress_callback=None,
        partial_ready_callback=on_partial,
    )

    full_time = time.perf_counter() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # DB ファイルサイズ
    db_size_mb = Path(db_path).stat().st_size / 1024 / 1024

    # 行数確認
    conn = sqlite3.connect(db_path)
    row_count = conn.execute("SELECT COUNT(*) FROM csv_data").fetchone()[0]
    conn.close()

    return {
        "partial_s": partial_time,
        "full_s": full_time,
        "peak_mb": peak_bytes / 1024 / 1024,
        "db_size_mb": db_size_mb,
        "row_count": row_count,
        "db_path": db_path,
    }


# ─────────────────────────────────────────────
# FTS5 / LIKE 検索ベンチマーク
# ─────────────────────────────────────────────
def bench_search(db_path: str, num_cols: int) -> dict:
    """FTS5 と LIKE 検索の速度を計測する。"""
    # FTS5 構築
    t0 = time.perf_counter()
    fts_ok = build_fts5_index(db_path)
    fts_build_s = time.perf_counter() - t0

    results = {"fts_build_s": fts_build_s, "fts_ok": fts_ok}

    conn = sqlite3.connect(db_path)

    # FTS5 検索
    if fts_ok:
        phrase = f'"{SEARCH_KEYWORD}"'
        t0 = time.perf_counter()
        rows = conn.execute(
            "SELECT COUNT(*) FROM csv_data_fts WHERE csv_data_fts MATCH ?",
            (phrase,),
        ).fetchone()[0]
        results["fts_search_ms"] = (time.perf_counter() - t0) * 1000
        results["fts_hits"] = rows

    # LIKE 検索（全列）
    cols = [
        row[1]
        for row in conn.execute("PRAGMA table_info(csv_data)").fetchall()
    ]
    like_conditions = " OR ".join(
        f'"{c}" LIKE ?' for c in cols
    )
    params = [f"%{SEARCH_KEYWORD}%"] * len(cols)
    t0 = time.perf_counter()
    like_rows = conn.execute(
        f"SELECT COUNT(*) FROM csv_data WHERE {like_conditions}", params
    ).fetchone()[0]
    results["like_search_ms"] = (time.perf_counter() - t0) * 1000
    results["like_hits"] = like_rows

    conn.close()
    return results


# ─────────────────────────────────────────────
# レポート出力
# ─────────────────────────────────────────────
def fmt(v, unit="s", precision=2):
    if v is None:
        return "N/A"
    return f"{v:.{precision}f}{unit}"


def run():
    print("=" * 60)
    print("CSView ベンチマーク")
    print("=" * 60)

    all_results = []

    for s in SCENARIOS:
        label = s["label"]
        rows = s["rows"]
        cols = s["cols"]
        csv_name = f"bench_{rows}rows_{cols}cols.csv"
        csv_path = BENCH_DIR / csv_name

        print(f"\n>>> {label}")

        # 1. CSV 生成
        generate_csv(csv_path, rows, cols)
        csv_size_mb = csv_path.stat().st_size / 1024 / 1024

        # 2. 変換ベンチ
        print(f"  変換中...")
        conv = bench_convert(csv_path)

        # 3. 検索ベンチ
        print(f"  検索中...")
        search = bench_search(conv["db_path"], cols)

        result = {
            "label": label,
            "csv_mb": csv_size_mb,
            "rows": conv["row_count"],
            "cols": cols,
            **conv,
            **search,
        }
        all_results.append(result)

        # 即時表示
        partial_str = fmt(conv["partial_s"]) if conv["partial_s"] else "N/A (50k行未満)"
        print(f"  CSV サイズ     : {csv_size_mb:.1f} MB")
        print(f"  初回表示まで   : {partial_str}")
        print(f"  フル変換時間   : {fmt(conv['full_s'])}")
        print(f"  ピークメモリ   : {fmt(conv['peak_mb'], 'MB', 1)}")
        print(f"  SQLite サイズ  : {fmt(conv['db_size_mb'], 'MB', 1)}")
        if search.get("fts_ok"):
            print(f"  FTS5 構築時間  : {fmt(search['fts_build_s'])}")
            print(f"  FTS5 検索時間  : {fmt(search.get('fts_search_ms'), 'ms', 1)}")
        print(f"  LIKE 検索時間  : {fmt(search.get('like_search_ms'), 'ms', 1)}")

    # ─────────────────────────────────
    # Markdown レポート生成
    # ─────────────────────────────────
    report_path = Path(__file__).parent / "benchmark_results.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# CSView Benchmark Results\n\n")
        f.write(f"実行日時: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 変換パフォーマンス\n\n")
        f.write("| シナリオ | CSV サイズ | 初回表示 | フル変換 | ピークメモリ | SQLite サイズ |\n")
        f.write("|---------|-----------|---------|---------|------------|-------------|\n")
        for r in all_results:
            p = fmt(r["partial_s"]) if r.get("partial_s") else "< 5s"
            f.write(
                f"| {r['label']} | {r['csv_mb']:.1f} MB"
                f" | {p} | {fmt(r['full_s'])}"
                f" | {fmt(r['peak_mb'], 'MB', 1)}"
                f" | {fmt(r['db_size_mb'], 'MB', 1)} |\n"
            )

        f.write("\n## 検索パフォーマンス\n\n")
        f.write("| シナリオ | FTS5 構築 | FTS5 検索 | LIKE 検索 | FTS5 倍率 |\n")
        f.write("|---------|---------|---------|---------|----------|\n")
        for r in all_results:
            fts_ms = r.get("fts_search_ms")
            like_ms = r.get("like_search_ms")
            ratio = f"{like_ms / fts_ms:.0f}x" if fts_ms and like_ms and fts_ms > 0 else "N/A"
            f.write(
                f"| {r['label']}"
                f" | {fmt(r.get('fts_build_s'), 's', 1)}"
                f" | {fmt(fts_ms, 'ms', 1)}"
                f" | {fmt(like_ms, 'ms', 1)}"
                f" | {ratio} |\n"
            )

    print(f"\n{'=' * 60}")
    print(f"レポート保存先: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    run()
