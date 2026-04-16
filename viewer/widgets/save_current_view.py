import os
import csv
import time
from PyQt6.QtWidgets import (
    QFileDialog, QMessageBox, QProgressDialog, QApplication, QDialog
)
from PyQt6.QtCore import Qt
from .save_options_dialog import SaveOptionsDialog, get_encoding_display
from ..utils.i18n import _


def _convert_value(value, dtype: str):
    """dtype に従って value を変換する。変換できない場合は元の値を返す。"""
    if value is None:
        return ""
    if dtype == "int":
        try:
            return str(int(float(str(value))))
        except (ValueError, TypeError):
            return value
    if dtype == "float":
        try:
            f = float(str(value))
            # 整数値なら小数点以下を落とさず float 表現を保持
            return str(f)
        except (ValueError, TypeError):
            return value
    return value  # text: そのまま


def save_current_view(parent, model):
    if model is None or model.rowCount() == 0:
        QMessageBox.warning(parent, _("保存エラー"), _("表示中のデータがありません。"))
        return

    while model.canFetchMore():
        model.fetchMore()

    total_cols = model.columnCount()
    total_rows = model.rowCount()
    headers = [model.headerData(i, Qt.Orientation.Horizontal) for i in range(total_cols)]

    # 保存オプション（文字コード・フォーマット・列詳細設定）を選択
    opts_dlg = SaveOptionsDialog(parent, default_encoding="utf-8-sig", headers=headers)
    if opts_dlg.exec() != QDialog.DialogCode.Accepted:
        return

    encoding  = opts_dlg.encoding()
    extension = opts_dlg.extension()
    delimiter = opts_dlg.delimiter()
    col_settings = opts_dlg.column_settings()  # None or list[dict]

    # 列設定が有効な場合、出力対象列を絞り込む
    if col_settings:
        active = [(i, s) for i, s in enumerate(col_settings) if s["include"]]
        if not active:
            QMessageBox.warning(parent, _("保存エラー"), _("出力する列が選択されていません。"))
            return
        out_headers = [s["output_name"] for _, s in active]
    else:
        active = [(i, {"output_name": h, "dtype": "text"}) for i, h in enumerate(headers)]
        out_headers = headers

    enc_label   = get_encoding_display(encoding)
    file_filter = _("CSV ファイル (*.csv)") if extension == ".csv" else _("TSV ファイル (*.tsv)")
    default_name = os.path.join(os.path.expanduser("~"), f"exported{extension}")

    save_path, _flt = QFileDialog.getSaveFileName(
        parent,
        _("保存先を指定"),
        default_name,
        file_filter,
    )
    if not save_path:
        return
    if not save_path.endswith(extension):
        save_path += extension

    progress = None
    try:
        progress = QProgressDialog(parent)
        progress.setWindowTitle(_("ファイル保存"))
        progress.setLabelText(_("保存処理を開始しています..."))
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.resize(420, 110)
        if parent:
            pg = parent.geometry()
            progress.move(pg.x() + (pg.width() - 420) // 2,
                          pg.y() + (pg.height() - 110) // 2)
        progress.show()
        progress.raise_()
        progress.activateWindow()
        QApplication.processEvents()

        progress.setValue(10)
        progress.setLabelText(f"ヘッダー情報を取得中... ({len(out_headers)} 列)")
        QApplication.processEvents()

        progress.setValue(20)
        progress.setLabelText(
            f"ファイルに書き出し中... ({total_rows:,} 行) [{enc_label}]"
        )
        QApplication.processEvents()

        batch_size = max(1000, total_rows // 50)

        # UTF-16 系は csv モジュールが改行変換を自前で行うため newline="" を渡さない
        is_utf16 = encoding.lower().startswith("utf-16")
        open_kwargs: dict = {"encoding": encoding}
        if not is_utf16:
            open_kwargs["newline"] = ""

        with open(save_path, "w", **open_kwargs) as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(out_headers)

            for start_row in range(0, total_rows, batch_size):
                end_row = min(start_row + batch_size, total_rows)
                for row in range(start_row, end_row):
                    row_data = [
                        _convert_value(model.data(model.index(row, col_idx)), s["dtype"])
                        for col_idx, s in active
                    ]
                    writer.writerow(row_data)

                pct = 20 + int((end_row / total_rows) * 70)
                progress.setValue(pct)
                progress.setLabelText(
                    f"書き出し中... {end_row:,}/{total_rows:,} 行 ({pct}%)"
                )
                QApplication.processEvents()

        progress.setValue(100)
        progress.setLabelText(_("保存完了"))
        QApplication.processEvents()
        time.sleep(0.2)
        progress.close()

        file_size_mb = os.path.getsize(save_path) / (1024 * 1024)
        QMessageBox.information(
            parent,
            _("保存完了"),
            f"{save_path} に保存しました。\n"
            f"行数: {total_rows:,}\n"
            f"列数: {len(out_headers)}\n"
            f"文字コード: {enc_label}\n"
            f"ファイルサイズ: {file_size_mb:.2f} MB",
        )

    except Exception as e:
        if progress:
            progress.close()
        QMessageBox.critical(parent, _("エラー"), f"保存中にエラーが発生しました:\n{str(e)}")
