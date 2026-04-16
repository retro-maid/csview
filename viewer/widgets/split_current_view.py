import os
import csv
import shutil
import zipfile
import tempfile
import pyzipper
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QLineEdit,
    QCheckBox, QDialogButtonBox, QProgressDialog, QFileDialog, QMessageBox,
    QApplication, QGroupBox, QComboBox
)
from PyQt6.QtCore import Qt
from .save_options_dialog import ENCODING_OPTIONS, FORMAT_OPTIONS, get_encoding_display
from ..utils.i18n import _


class SplitSettingsDialog(QDialog):
    def __init__(self, default_base_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("分割保存オプション"))
        layout = QVBoxLayout(self)
        self.resize(520, 280)

        # --- 分割設定 ---
        split_group = QGroupBox(_("分割設定"))
        split_layout = QVBoxLayout(split_group)

        h1 = QHBoxLayout()
        h1.addWidget(QLabel(_("分割数:")))
        self.split_spin = QSpinBox()
        self.split_spin.setRange(1, 1000)
        self.split_spin.setValue(5)
        h1.addWidget(self.split_spin)
        h1.addStretch()
        split_layout.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel(_("ファイル名（拡張子不要）:")))
        self.base_name_edit = QLineEdit(default_base_name)
        h2.addWidget(self.base_name_edit)
        split_layout.addLayout(h2)

        layout.addWidget(split_group)

        # --- ファイル形式 ---
        fmt_group = QGroupBox(_("ファイル形式"))
        fmt_layout = QHBoxLayout(fmt_group)
        self._format_combo = QComboBox()
        for label, ext, _delim in FORMAT_OPTIONS:
            self._format_combo.addItem(label, (ext, _delim))
        fmt_layout.addWidget(self._format_combo)
        layout.addWidget(fmt_group)

        # --- 文字コード ---
        enc_group = QGroupBox(_("文字コード（エンコーディング）"))
        enc_layout = QVBoxLayout(enc_group)
        enc_note = QLabel(_("※ Excel で開く場合は「UTF-8 BOM付き」または「Shift-JIS」を推奨"))
        enc_note.setStyleSheet("color: #555; font-size: 11px;")
        enc_layout.addWidget(enc_note)
        self._enc_combo = QComboBox()
        default_idx = 0
        for i, (label, enc, _bom) in enumerate(ENCODING_OPTIONS):
            self._enc_combo.addItem(label, enc)
            if enc == "utf-8-sig":
                default_idx = i
        self._enc_combo.setCurrentIndex(default_idx)
        enc_layout.addWidget(self._enc_combo)
        layout.addWidget(enc_group)

        # --- 暗号化 ---
        encrypt_group = QGroupBox(_("ZIP暗号化"))
        encrypt_layout = QVBoxLayout(encrypt_group)
        self.encrypt_check = QCheckBox(_("パスワード付きで暗号化（AES-256）"))
        encrypt_layout.addWidget(self.encrypt_check)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel(_("パスワード:")))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setEnabled(False)
        h3.addWidget(self.password_edit)
        encrypt_layout.addLayout(h3)
        layout.addWidget(encrypt_group)

        self.encrypt_check.stateChanged.connect(
            lambda state: self.password_edit.setEnabled(bool(state))
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        ext, delim = self._format_combo.currentData()
        return {
            "count": self.split_spin.value(),
            "base_name": self.base_name_edit.text().strip(),
            "encrypt": self.encrypt_check.isChecked(),
            "password": self.password_edit.text().strip(),
            "encoding": self._enc_combo.currentData(),
            "extension": ext,
            "delimiter": delim,
        }


def split_current_view(parent, model, csv_path: str = ""):
    if model is None or model.rowCount() == 0:
        QMessageBox.warning(parent, _("分割エラー"), _("表示中のデータがありません。"))
        return

    while model.canFetchMore():
        model.fetchMore()

    default_name = os.path.splitext(os.path.basename(csv_path))[0] if csv_path else ""
    dlg = SplitSettingsDialog(default_name, parent)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    settings = dlg.get_values()
    count = settings["count"]
    base_name = settings["base_name"] or default_name
    use_encryption = settings["encrypt"]
    password = settings["password"].encode("utf-8") if use_encryption and settings["password"] else None
    encoding = settings["encoding"]
    extension = settings["extension"]
    delimiter = settings["delimiter"]
    enc_label = get_encoding_display(encoding)

    if not base_name:
        QMessageBox.warning(parent, _("入力エラー"), _("ファイル名を指定してください。"))
        return
    if use_encryption and not password:
        QMessageBox.warning(parent, _("入力エラー"), _("暗号化する場合はパスワードを入力してください。"))
        return

    zip_path, _flt = QFileDialog.getSaveFileName(parent, _("保存先ZIPを指定"), "", _("Zip files (*.zip)"))
    if not zip_path:
        return
    if not zip_path.endswith(".zip"):
        zip_path += ".zip"

    tmp_dir = None
    part_files = []

    try:
        headers = [model.headerData(i, Qt.Orientation.Horizontal) for i in range(model.columnCount())]
        total_rows = model.rowCount()
        chunk_size = total_rows // count + (1 if total_rows % count > 0 else 0)

        tmp_dir = tempfile.mkdtemp()

        progress = QProgressDialog(parent)
        progress.setWindowTitle(_("分割保存"))
        progress.setLabelText(_("分割保存を開始しています..."))
        progress.setRange(0, count)
        progress.setValue(0)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.resize(400, 100)
        if parent:
            parent_geometry = parent.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - 400) // 2
            y = parent_geometry.y() + (parent_geometry.height() - 100) // 2
            progress.move(x, y)
        progress.show()
        progress.raise_()
        progress.activateWindow()
        QApplication.processEvents()

        for i in range(count):
            progress.setValue(i)
            progress.setLabelText(f"分割保存中... {i+1}/{count} ファイルを作成中")
            QApplication.processEvents()

            start = i * chunk_size
            end = min(start + chunk_size, total_rows)
            part_name = f"{i+1:02d}_{base_name}{extension}"
            part_path = os.path.join(tmp_dir, part_name)

            with open(part_path, "w", encoding=encoding, newline="") as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerow(headers)
                for row in range(start, end):
                    writer.writerow([model.data(model.index(row, col)) for col in range(model.columnCount())])

            part_files.append(part_path)
            progress.setValue(i + 1)
            progress.setLabelText(f"完了: {part_name}")
            QApplication.processEvents()

        progress.setLabelText(_("ZIPファイル作成中..."))
        progress.setValue(count)
        QApplication.processEvents()

        if use_encryption:
            with pyzipper.AESZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(password)
                for f in part_files:
                    zf.write(f, os.path.basename(f))
        else:
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for f in part_files:
                    zf.write(f, os.path.basename(f))

        progress.close()
        QMessageBox.information(
            parent,
            _("分割保存完了"),
            f"{count} ファイルに分割して保存しました。\n"
            f"保存先: {zip_path}\n"
            f"文字コード: {enc_label}",
        )

    except Exception as e:
        if 'progress' in locals():
            progress.close()
        QMessageBox.critical(parent, _("エラー"), f"分割中にエラーが発生しました:\n{str(e)}")

    finally:
        for f in part_files:
            if os.path.exists(f):
                os.remove(f)
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)  # 空でない場合も削除可能
