"""
convert_csv.py - CSV to SQLite変換エンジン

アーキテクチャ:
  Polars全読み込み + iter_rows() の代わりに Python csv モジュール（C実装）で
  ストリーミング挿入することで、メモリ使用量と変換時間を大幅に削減。

速度比較（1M行 / 10列の目安）:
  旧: Polars全読み込み(3s) + iter_rows変換(4s) + executemany(2s) ≒ 9s
  新: csvストリーミング(1.5s) + executemany(2s)                  ≒ 3.5s
"""
import csv
import sqlite3
import os
import codecs
import time as _time
from charset_normalizer import detect as charset_detect
from typing import Callable, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROGRESSIVE_ROWS = 50_000    # この行数を超えたら partial_ready_callback を呼ぶ
TYPE_SAMPLE_ROWS = 200        # 型推論に使うサンプル行数
FTS5_SIZE_THRESHOLD = 500 * 1024 * 1024  # 500MB 超はFTS5をスキップ
WAL_COMMIT_INTERVAL = 100_000  # WALモード移行後の中間COMMITの行数間隔（リーダーに進捗を見せるため）


def _infer_column_types(sample_rows: list, col_count: int) -> list:
    """
    サンプル行から各カラムの最適な型を推論する。
    空値は無視。INTEGER → REAL → TEXT の順に昇格する。
    """
    types = ["INTEGER"] * col_count
    for row in sample_rows:
        for i, val in enumerate(row[:col_count]):
            if types[i] == "TEXT" or not val:
                continue
            try:
                int(val)
            except (ValueError, TypeError):
                try:
                    float(val)
                    types[i] = "REAL"
                except (ValueError, TypeError):
                    types[i] = "TEXT"
    return types


_FTS5_CHUNK = 10_000  # FTS5 チャンク挿入行数


def build_fts5_index(
    db_path: str,
    table_name: str = "csv_data",
    progress_callback: Optional[Callable[[int], None]] = None,
    cancelled_flag: Optional[Callable[[], bool]] = None,
) -> bool:
    """
    既存のSQLiteデータベースにFTS5インデックスを構築する。
    サイズ制限なし。チャンク単位で挿入し progress_callback で進捗を通知する。
    呼び出し元スレッドでブロックするため、バックグラウンドスレッドから呼ぶこと。

    Returns:
        bool: 構築成功なら True、失敗・キャンセルなら False
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # カラム情報を取得
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        cols = cursor.fetchall()
        if not cols:
            return False

        escaped = [f'"{row[1].replace(chr(34), chr(34)*2)}"' for row in cols]
        quoted_cols = ", ".join(escaped)

        # FTS5 仮想テーブルを再作成
        cursor.executescript(f"""
            DROP TABLE IF EXISTS "{table_name}_fts";
            CREATE VIRTUAL TABLE "{table_name}_fts" USING fts5(
                {quoted_cols},
                content='{table_name}',
                content_rowid='rowid'
            );
        """)

        # 総行数を取得（進捗計算用）
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        total = cursor.fetchone()[0] or 1

        # ROWID ベースのチャンク挿入でキャンセル・進捗に対応する。
        # LIMIT/OFFSET では後半チャンクで O(n) フルスキャンが発生するため
        # WHERE rowid > last_rowid を使って O(log n) に抑える。
        inserted = 0
        last_rowid = 0
        while True:
            if cancelled_flag and cancelled_flag():
                logger.info("FTS5構築キャンセル: %s", db_path)
                return False

            cursor.execute(
                f'INSERT INTO "{table_name}_fts"(rowid, {quoted_cols})'
                f' SELECT rowid, {quoted_cols} FROM "{table_name}"'
                f' WHERE rowid > ? ORDER BY rowid LIMIT ?',
                (last_rowid, _FTS5_CHUNK),
            )
            rows_inserted = cursor.rowcount
            conn.commit()
            inserted += rows_inserted
            last_rowid += rows_inserted  # csv_data の rowid は連番なのでこれで正確

            if progress_callback:
                pct = min(99, int(inserted / total * 100))
                progress_callback(pct)

            if rows_inserted < _FTS5_CHUNK:
                break  # 全行挿入完了

        if progress_callback:
            progress_callback(100)

        logger.info("FTS5インデックス構築完了: %s (%d 行)", db_path, inserted)
        return True

    except Exception as e:
        logger.warning("FTS5構築エラー: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def estimate_row_count(file_path: str) -> int:
    """
    ファイルの先頭 64KB をサンプリングして総行数（ヘッダー除く）を推定する。
    計算は瞬時に終わるため、変換開始前の情報バー表示に使用する。
    """
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return 0
        with open(file_path, "rb") as f:
            chunk = f.read(65536)
        newlines = chunk.count(b"\n")
        if newlines <= 1:
            return 0
        avg_bytes_per_line = len(chunk) / newlines
        estimated = int(file_size / avg_bytes_per_line) - 1  # ヘッダー行を除く
        return max(0, estimated)
    except Exception:
        return 0


def detect_encoding(file_path: str) -> str:
    """ファイルのエンコーディングを検出する。BOM → chardet → フォールバックの順で試行。"""
    try:
        with open(file_path, "rb") as f:
            raw = f.read(4096)

        # BOM優先
        if raw.startswith(codecs.BOM_UTF8):
            return "utf-8-sig"
        if raw.startswith(codecs.BOM_UTF16_LE):
            return "utf-16-le"
        if raw.startswith(codecs.BOM_UTF16_BE):
            return "utf-16-be"

        # chardetで高信頼度検出
        result = charset_detect(raw)
        if result["confidence"] > 0.7:
            enc = result["encoding"].lower()
            if enc in ("shift_jis", "shift-jis", "sjis"):
                return "shift_jis"
            if enc in ("cp932", "ms932"):
                return "cp932"
            if enc in ("utf-8", "utf8"):
                return "utf-8"
            return result["encoding"]

        # CSV/TSV/Excel で使われうるエンコーディングを優先順に試行
        for enc in (
            "utf-8",
            "utf-8-sig",
            "cp932",        # Windows Shift-JIS
            "shift_jis",
            "euc_jp",
            "iso2022_jp",   # JIS
            "utf-16",
            "utf-16-le",
            "utf-16-be",
            "cp1252",       # Windows 西欧
            "latin-1",      # ISO-8859-1
            "cp1251",       # Windows キリル
            "gbk",          # 中国語簡体字
            "big5",         # 中国語繁体字
            "cp949",        # 韓国語
        ):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    for _ in range(5):
                        if not f.readline():
                            break
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue

        return "utf-8"

    except Exception as e:
        logger.warning("エンコーディング検出エラー: %s", e)
        return "utf-8"


def convert_csv_to_sqlite(
    csv_path: str,
    db_path: str,
    progress_callback: Optional[object] = None,
    partial_ready_callback: Optional[Callable[[], None]] = None,
    table_name: str = "csv_data",
    chunk_size: int = 500_000,
) -> None:
    """
    CSVをSQLiteへ変換する（プログレッシブ表示対応版）。

    PROGRESSIVE_ROWS 行挿入後に WAL モードへ切り替え、
    partial_ready_callback を呼び出す。これにより呼び出し元は
    変換完了を待たずにデータを表示できる。

    FTS5インデックスはこの関数では構築しない。
    build_fts5_index() を別スレッドで呼ぶこと。

    Args:
        csv_path: 変換元CSVファイルパス
        db_path: 出力SQLiteファイルパス
        progress_callback: 進捗通知シグナル (emit(int) を呼び出す)
        partial_ready_callback: PROGRESSIVE_ROWS 行挿入後に呼ばれるコールバック
        table_name: SQLiteテーブル名
        chunk_size: 一度にINSERTするバッチサイズ
    """
    conn = None
    try:
        if os.path.exists(db_path):
            os.remove(db_path)

        delimiter = "\t" if Path(csv_path).suffix.lower() == ".tsv" else ","
        file_size = os.path.getsize(csv_path)
        detected_encoding = detect_encoding(csv_path)
        logger.debug("エンコーディング: %s", detected_encoding)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # フェーズ1 PRAGMA: 高速インポート設定
        # journal_mode=MEMORY で最速インポートを行い、
        # PROGRESSIVE_ROWS 到達後に WAL へ切り替えて並行読み取りを許可する
        cursor.execute("PRAGMA page_size = 65536")
        cursor.execute("PRAGMA journal_mode = MEMORY")
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA temp_store = MEMORY")
        cursor.execute("PRAGMA cache_size = -131072")   # 128MB
        cursor.execute("PRAGMA mmap_size = 268435456")  # 256MB

        total_rows = 0
        partial_notified = False
        sample_rows: list = []
        _last_progress_emit = 0.0          # 進捗 emit のスロットリング用
        _PROGRESS_INTERVAL = 0.3           # 最低 0.3 秒間隔で emit
        _rows_since_commit = 0             # 中間 COMMIT カウンター

        # UTF-16 系は csv モジュールが改行変換を自前で行うため newline="" を渡さない
        _is_utf16 = detected_encoding.lower().startswith("utf-16")
        _open_kwargs: dict = {"encoding": detected_encoding, "errors": "replace"}
        if not _is_utf16:
            _open_kwargs["newline"] = ""

        with open(csv_path, "r", **_open_kwargs) as f:
            reader = csv.reader(f, delimiter=delimiter)

            columns = next(reader, None)
            if not columns:
                raise ValueError("CSVファイルにヘッダー行が見つかりません")

            col_count = len(columns)
            escaped = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in columns]

            # --- 型推論: 先頭 TYPE_SAMPLE_ROWS 行をサンプリング ---
            for row in reader:
                if len(row) < col_count:
                    row.extend([""] * (col_count - len(row)))
                sample_rows.append(row[:col_count])
                if len(sample_rows) >= TYPE_SAMPLE_ROWS:
                    break

            col_types = _infer_column_types(sample_rows, col_count)
            col_defs = ", ".join(
                f"{c} {t}" for c, t in zip(escaped, col_types)
            )
            cursor.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

            placeholders = ", ".join(["?"] * col_count)
            insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'

            conn.execute("BEGIN")

            # サンプル行を先に挿入
            if sample_rows:
                cursor.executemany(insert_sql, sample_rows)
                total_rows += len(sample_rows)

            batch: list = []

            for row in reader:
                actual_len = len(row)
                if actual_len != col_count:
                    if actual_len < col_count:
                        row.extend([""] * (col_count - actual_len))
                    else:
                        logger.debug(
                            "行 %d: 列数不一致 (期待=%d, 実際=%d)、超過分を切り捨て",
                            total_rows + 1, col_count, actual_len,
                        )
                batch.append(row[:col_count])
                total_rows += 1

                # 1万行ごとに時間チェックして進捗 emit（0.3秒スロットリング）
                if progress_callback and file_size > 0 and total_rows % 10_000 == 0:
                    _now = _time.monotonic()
                    if _now - _last_progress_emit >= _PROGRESS_INTERVAL:
                        try:
                            percent = int(f.tell() / file_size * 95)
                            progress_callback.emit(min(95, percent))
                            _last_progress_emit = _now
                        except Exception:
                            pass

                if len(batch) >= chunk_size:
                    cursor.executemany(insert_sql, batch)
                    batch.clear()

                # WAL モード移行後: WAL_COMMIT_INTERVAL 行ごとに中間 COMMIT してリーダーに進捗を公開
                # （COMMIT しないと SELECT COUNT(*) が最後のコミット時点の値しか返さないため）
                if partial_notified:
                    _rows_since_commit += 1
                    if _rows_since_commit >= WAL_COMMIT_INTERVAL:
                        conn.commit()
                        conn.execute("BEGIN")
                        _rows_since_commit = 0

                # PROGRESSIVE_ROWS 到達でWAL切替 → コールバック通知
                if not partial_notified and total_rows >= PROGRESSIVE_ROWS:
                    cursor.executemany(insert_sql, batch)
                    batch.clear()
                    conn.commit()

                    # MEMORY → WAL に切り替えて並行読み取りを許可
                    cursor.execute("PRAGMA journal_mode = WAL")
                    cursor.execute("PRAGMA wal_autocheckpoint = 0")
                    conn.execute("BEGIN")
                    partial_notified = True
                    _rows_since_commit = 0

                    if partial_ready_callback:
                        partial_ready_callback()

            if batch:
                cursor.executemany(insert_sql, batch)

        conn.commit()

        # WAL チェックポイントを実行してファイルサイズを最適化
        if partial_notified:
            cursor.execute("PRAGMA wal_autocheckpoint = 1000")
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        if progress_callback:
            progress_callback.emit(100)

        conn.close()
        conn = None
        logger.info("SQLite変換完了: %s (%d 行)", db_path, total_rows)

    except Exception as e:
        error_msg = f"CSV to SQLite変換エラー: {str(e)}"
        logger.error(error_msg)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
        except OSError:
            pass
        raise Exception(error_msg)