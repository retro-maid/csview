import os
import csv
import time
import logging
import zipfile
import shutil
import pyzipper

logger = logging.getLogger(__name__)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QDialogButtonBox, QProgressDialog, QFileDialog,
    QMessageBox, QApplication, QTextEdit, QPushButton
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from converter.convert_csv import convert_csv_to_sqlite, detect_encoding
from ..utils.i18n import _


class ZipMergeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("ZIP分割CSV結合・DB化"))
        self.resize(600, 400)
        layout = QVBoxLayout(self)

        # ZIPファイル選択
        zip_layout = QHBoxLayout()
        zip_layout.addWidget(QLabel(_("ZIPファイル:")))
        self.zip_path_edit = QLineEdit()
        self.zip_path_edit.setReadOnly(True)
        zip_layout.addWidget(self.zip_path_edit)

        self.browse_zip_btn = QPushButton(_("参照..."))
        self.browse_zip_btn.clicked.connect(self.browse_zip_file)
        zip_layout.addWidget(self.browse_zip_btn)
        layout.addLayout(zip_layout)

        # パスワード入力
        password_layout = QHBoxLayout()
        self.password_check = QCheckBox(_("パスワード付きZIP"))
        password_layout.addWidget(self.password_check)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setEnabled(False)
        self.password_edit.setPlaceholderText(_("ZIPファイルのパスワードを入力"))
        password_layout.addWidget(self.password_edit)
        layout.addLayout(password_layout)

        self.password_check.stateChanged.connect(
            lambda state: self.password_edit.setEnabled(bool(state))
        )

        # 出力先設定
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel(_("出力DB名:")))
        self.output_name_edit = QLineEdit(f"csv_editor_merged_{int(time.time()*1000)}.db")
        output_layout.addWidget(self.output_name_edit)
        layout.addLayout(output_layout)

        # プレビュー表示
        preview_label = QLabel(_("ZIPファイル内容プレビュー:"))
        layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setReadOnly(True)
        layout.addWidget(self.preview_text)

        # ボタン
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_zip_file(self):
        """ZIPファイル選択"""
        zip_path, _flt = QFileDialog.getOpenFileName(
            self,
            _("分割CSVのZIPファイルを選択"),
            "",
            _("ZIP files (*.zip);;All files (*.*)")
        )
        if zip_path:
            self.zip_path_edit.setText(zip_path)
            self.update_preview()

    def update_preview(self):
        """ZIPファイル内容のプレビュー更新"""
        zip_path = self.zip_path_edit.text()
        if not zip_path or not os.path.exists(zip_path):
            self.preview_text.clear()
            return

        try:
            preview_text = f"ZIPファイル: {os.path.basename(zip_path)}\n"
            preview_text += f"ファイルサイズ: {os.path.getsize(zip_path) / (1024*1024):.2f} MB\n\n"

            # パスワードが設定されている場合
            password = None
            if self.password_check.isChecked() and self.password_edit.text():
                password = self.password_edit.text().encode('utf-8')

            # ZIP内容を確認
            try:
                if password:
                    with pyzipper.AESZipFile(zip_path, 'r') as zf:
                        zf.setpassword(password)
                        file_list = zf.namelist()
                else:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        file_list = zf.namelist()

                csv_files = [f for f in file_list if f.lower().endswith('.csv')]

                preview_text += f"CSVファイル数: {len(csv_files)}\n"
                preview_text += "ファイル一覧:\n"

                for i, csv_file in enumerate(sorted(csv_files)[:10]):  # 最初の10個のみ表示
                    preview_text += f"  {i+1:2d}. {csv_file}\n"

                if len(csv_files) > 10:
                    preview_text += f"  ... 他 {len(csv_files) - 10} ファイル\n"

            except Exception as e:
                preview_text += f"エラー: {str(e)}\n"
                preview_text += "パスワードが必要な場合は、パスワードを設定してください。"

            self.preview_text.setPlainText(preview_text)

        except Exception as e:
            self.preview_text.setPlainText(f"プレビューエラー: {str(e)}")

    def get_settings(self):
        """設定値を取得"""
        return {
            'zip_path': self.zip_path_edit.text(),
            'use_password': self.password_check.isChecked(),
            'password': self.password_edit.text() if self.password_check.isChecked() else None,
            'output_name': self.output_name_edit.text().strip()
        }


class ZipMergeThread(QThread):
    """ZIP結合・DB化処理用スレッド"""
    progress = pyqtSignal(int, str)  # 進捗率とメッセージ
    finished = pyqtSignal(str)  # 完了時のDBパス
    failed = pyqtSignal(str)  # エラーメッセージ

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def run(self):
        temp_dir = None
        temp_csv_path = None

        try:
            # 設定取得
            zip_path = self.settings['zip_path']
            use_password = self.settings['use_password']
            password = self.settings['password']
            output_name = self.settings['output_name']

            if not output_name.endswith('.db'):
                output_name += '.db'

            # 出力先決定（一時ディレクトリに作成）
            import tempfile
            temp_db_dir = tempfile.gettempdir()
            db_path = os.path.join(temp_db_dir, output_name)

            self.progress.emit(5, _("一時ディレクトリを作成中..."))

            # 一時ディレクトリ作成
            temp_dir = tempfile.mkdtemp(prefix="zip_merge_")

            self.progress.emit(10, _("ZIPファイルを展開中..."))

            # ZIPファイル展開
            csv_files = []
            try:
                if use_password and password:
                    password_bytes = password.encode('utf-8')
                    with pyzipper.AESZipFile(zip_path, 'r') as zf:
                        zf.setpassword(password_bytes)
                        file_list = zf.namelist()
                        csv_files = [f for f in file_list if f.lower().endswith('.csv')]

                        for csv_file in csv_files:
                            zf.extract(csv_file, temp_dir)
                else:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        file_list = zf.namelist()
                        csv_files = [f for f in file_list if f.lower().endswith('.csv')]

                        for csv_file in csv_files:
                            zf.extract(csv_file, temp_dir)

            except Exception as e:
                self.failed.emit(f"ZIP展開エラー: {str(e)}")
                return

            if not csv_files:
                self.failed.emit("ZIPファイル内にCSVファイルが見つかりません。")
                return

            self.progress.emit(20, f"{len(csv_files)} 個のCSVファイルを発見...")

            # CSVファイルをソート（ファイル名順）
            csv_files.sort()
            extracted_paths = [os.path.join(temp_dir, csv_file) for csv_file in csv_files]

            self.progress.emit(30, _("CSVファイルを結合中..."))

            # 最初のCSVでヘッダーを確認
            first_enc = detect_encoding(extracted_paths[0])
            with open(extracted_paths[0], "r", encoding=first_enc, errors="replace", newline="") as f:
                headers = next(csv.reader(f), None)

            if not headers:
                self.failed.emit("最初のCSVファイルにヘッダーが見つかりません。")
                return

            # ストリーミングマージ：一時CSVに直接書き出す（メモリ使用量を最小化）
            temp_csv_path = os.path.join(temp_dir, "merged_temp.csv")
            total_rows_written = 0

            with open(temp_csv_path, "w", encoding="utf-8", newline="") as out_f:
                writer = csv.writer(out_f)
                writer.writerow(headers)

                for i, csv_path in enumerate(extracted_paths):
                    try:
                        enc = detect_encoding(csv_path)
                        with open(csv_path, "r", encoding=enc, errors="replace", newline="") as f:
                            reader = csv.reader(f)
                            file_headers = next(reader, None)
                            if file_headers is None:
                                continue

                            if file_headers != headers:
                                self.progress.emit(
                                    30 + (i * 30 // len(extracted_paths)),
                                    f"警告: {os.path.basename(csv_path)} のヘッダーが異なります"
                                )
                                # ヘッダーが異なる場合は列を合わせる
                                col_indices = []
                                for h in headers:
                                    try:
                                        col_indices.append(file_headers.index(h))
                                    except ValueError:
                                        col_indices.append(None)
                                for row in reader:
                                    mapped = [
                                        row[idx] if idx is not None and idx < len(row) else ""
                                        for idx in col_indices
                                    ]
                                    writer.writerow(mapped)
                                    total_rows_written += 1
                            else:
                                for row in reader:
                                    writer.writerow(row)
                                    total_rows_written += 1

                        progress_val = 30 + ((i + 1) * 30 // len(extracted_paths))
                        self.progress.emit(progress_val, f"結合中... {i+1}/{len(extracted_paths)}")

                    except Exception as e:
                        self.progress.emit(
                            30 + (i * 30 // len(extracted_paths)),
                            f"エラー: {os.path.basename(csv_path)} をスキップ - {str(e)}"
                        )
                        continue

            self.progress.emit(65, f"結合完了: 総行数 {total_rows_written:,} 行")

            self.progress.emit(70, "データベース変換を開始...")

            # convert_csv_to_sqliteを呼び出し
            def db_progress_callback(percent):
                # 70% + (percent * 0.3) で70%～100%の範囲に調整
                adjusted_percent = 70 + int(percent * 0.3)
                self.progress.emit(adjusted_percent, f"データベース作成中... {percent}%")

            # プログレスコールバック用のシグナルエミッター
            class ProgressEmitter:
                def __init__(self, callback):
                    self.callback = callback
                def emit(self, value):
                    self.callback(value)

            progress_emitter = ProgressEmitter(db_progress_callback)

            convert_csv_to_sqlite(
                csv_path=temp_csv_path,
                db_path=db_path,
                progress_callback=progress_emitter
            )

            self.progress.emit(100, "完了")
            self.finished.emit(db_path)

        except Exception as e:
            self.failed.emit(f"処理中にエラーが発生しました: {str(e)}")

        finally:
            # クリーンアップ（失敗してもエラーログだけ残して続行）
            if temp_csv_path and os.path.exists(temp_csv_path):
                try:
                    os.remove(temp_csv_path)
                except Exception as e:
                    logger.debug("一時CSVファイル削除失敗: %s", e)

            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.debug("一時ディレクトリ削除失敗: %s", e)

def merge_zip_csv_to_database(parent=None):
    """ZIP分割CSV結合・DB化のメイン関数"""

    # 設定ダイアログ表示
    dialog = ZipMergeDialog(parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    settings = dialog.get_settings()

    if not settings['zip_path'] or not os.path.exists(settings['zip_path']):
        QMessageBox.warning(parent, _("入力エラー"), _("有効なZIPファイルを選択してください。"))
        return None

    if not settings['output_name']:
        QMessageBox.warning(parent, _("入力エラー"), _("出力データベース名を入力してください。"))
        return None

    # プログレスダイアログ
    progress = QProgressDialog(_("処理を準備中..."), None, 0, 100, parent)
    progress.setWindowTitle(_("ZIP結合・DB化"))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.setCancelButton(None)
    progress.show()
    progress.raise_()
    progress.activateWindow()
    QApplication.processEvents()

    # スレッドを親に保持（破棄されないように）
    if not hasattr(parent, "zip_merge_thread"):
        parent.zip_merge_thread = None
    if parent.zip_merge_thread and parent.zip_merge_thread.isRunning():
        parent.zip_merge_thread.terminate()
        parent.zip_merge_thread.wait()

    parent.zip_merge_thread = ZipMergeThread(settings)
    thread = parent.zip_merge_thread
    thread.setParent(parent)

    def update_progress(percent, message):
        if not progress.wasCanceled():
            progress.setValue(percent)
            progress.setLabelText(message)
            QApplication.processEvents()

    def on_finished(db_path):
        progress.close()

        if os.path.exists(db_path):
            file_size = os.path.getsize(db_path) / (1024 * 1024)
            QMessageBox.information(
                parent,
                _("結合・DB化完了"),
                f"ZIP分割CSVの結合・データベース化が完了しました。\n\n"
                f"一時データベース: {os.path.basename(db_path)}\n"
                f"データベースサイズ: {file_size:.2f} MB\n\n"
                f"CSVエディターで開きます。"
            )

            if hasattr(parent, 'load_database_directly'):
                zip_name = os.path.splitext(os.path.basename(settings['zip_path']))[0]
                virtual_csv_path = f"{zip_name}_merged.csv"
                parent.load_database_directly(db_path, virtual_csv_path)
            else:
                QMessageBox.information(parent, _("情報"), f"データベースが作成されました: {db_path}")
        else:
            QMessageBox.warning(parent, _("エラー"), "データベースファイルが作成されませんでした。")

    def on_failed(error_message):
        progress.close()
        QMessageBox.critical(parent, _("エラー"), error_message)

    # シグナル接続
    thread.progress.connect(update_progress)
    thread.finished.connect(on_finished)
    thread.failed.connect(on_failed)

    # スレッド開始
    thread.start()
    return thread
