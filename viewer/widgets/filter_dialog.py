from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QGroupBox, QScrollArea, QWidget, QMessageBox
)
from ..utils.i18n import _


class ConditionRow(QWidget):
    def __init__(self, column_names, parent=None):
        super().__init__(parent)
        self.column_box = QComboBox()
        self.column_box.addItems(column_names)

        self.operator_box = QComboBox()
        self.operator_box.addItems([
            _("=（一致）"), _("!＝（不一致）"), _(">（より大きい）"), _(">=（以上）"),
            _("<（より小さい）"), _("<=（以下）"), _("LIKE（含む）")
        ])

        self.value_input = QLineEdit()

        layout = QHBoxLayout()
        layout.addWidget(QLabel(_("列:")))
        layout.addWidget(self.column_box)
        layout.addWidget(QLabel(_("条件:")))
        layout.addWidget(self.operator_box)
        layout.addWidget(QLabel(_("値:")))
        layout.addWidget(self.value_input)
        self.setLayout(layout)

    def get_condition(self):
        op_map = {
            _("=（一致）"): "=", _("!＝（不一致）"): "!=", _(">（より大きい）"): ">", _(">=（以上）"): ">=",
            _("<（より小さい）"): "<", _("<=（以下）"): "<=", _("LIKE（含む）"): "LIKE"
        }
        return (
            self.column_box.currentText(),
            op_map[self.operator_box.currentText()],
            self.value_input.text().strip()
        )


class ConditionGroup(QGroupBox):
    def __init__(self, column_names, parent=None,
                 move_up_callback=None, move_down_callback=None, delete_callback=None):
        super().__init__(_("条件グループ"), parent)
        self.before_logic_box = QComboBox()
        self.before_logic_box.addItems(["AND", "OR"])
        self.logic_box = QComboBox()
        self.logic_box.addItems(["AND", "OR"])
        self.rows = []

        self.move_up_callback = move_up_callback
        self.move_down_callback = move_down_callback
        self.delete_callback = delete_callback

        before_logic_layout = QHBoxLayout()
        before_logic_layout.addWidget(QLabel(_("前グループとの結合:")))
        before_logic_layout.addWidget(self.before_logic_box)
        before_logic_layout.addStretch()

        logic_layout = QHBoxLayout()
        logic_layout.addWidget(QLabel(_("このグループ内の条件を:")))
        logic_layout.addWidget(self.logic_box)
        logic_layout.addStretch()

        self.row_container = QVBoxLayout()
        self.add_row(column_names)

        row_controls = QHBoxLayout()
        add_btn = QPushButton(_("＋ 条件追加"))
        remove_btn = QPushButton(_("－ 条件削除"))
        add_btn.clicked.connect(lambda: self.add_row(column_names))
        remove_btn.clicked.connect(self.remove_row)
        row_controls.addWidget(add_btn)
        row_controls.addWidget(remove_btn)
        row_controls.addStretch()

        control_row = QHBoxLayout()
        up_btn = QPushButton("↑")
        down_btn = QPushButton("↓")
        delete_btn = QPushButton("❌")
        up_btn.clicked.connect(lambda: self.move_up_callback(self))
        down_btn.clicked.connect(lambda: self.move_down_callback(self))
        delete_btn.clicked.connect(lambda: self.delete_callback(self))
        control_row.addStretch()
        control_row.addWidget(up_btn)
        control_row.addWidget(down_btn)
        control_row.addWidget(delete_btn)

        layout = QVBoxLayout()
        layout.addLayout(before_logic_layout)
        layout.addLayout(logic_layout)
        layout.addLayout(self.row_container)
        layout.addLayout(row_controls)
        layout.addLayout(control_row)
        self.setLayout(layout)

    def set_first_group(self):
        self.before_logic_box.setVisible(False)

    def add_row(self, column_names):
        row = ConditionRow(column_names)
        self.rows.append(row)
        self.row_container.addWidget(row)

    def remove_row(self):
        if len(self.rows) > 1:
            row = self.rows.pop()
            row.setParent(None)

    def get_group_logic(self):
        return self.logic_box.currentText()

    def get_before_logic(self):
        return self.before_logic_box.currentText()

    def get_conditions(self):
        return [row.get_condition() for row in self.rows]


class FilterDialog(QDialog):
    def __init__(self, parent=None, column_names=None):
        super().__init__(parent)
        self.setWindowTitle(_("複数条件の抽出"))
        self.setMinimumSize(600, 500)
        self.column_names = column_names or []

        self.group_container = QVBoxLayout()
        self.group_widgets = []

        scroll_widget = QWidget()
        scroll_widget.setLayout(self.group_container)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_widget)

        btn_add_group = QPushButton(_("＋ グループ追加"))
        btn_add_group.clicked.connect(self.add_group)

        btn_ok = QPushButton(_("抽出実行"))
        btn_cancel = QPushButton(_("キャンセル"))
        btn_ok.clicked.connect(self.check_and_accept)
        btn_cancel.clicked.connect(self.reject)

        group_control = QHBoxLayout()
        group_control.addWidget(btn_add_group)
        group_control.addStretch()

        bottom_buttons = QHBoxLayout()
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(btn_ok)
        bottom_buttons.addWidget(btn_cancel)

        layout = QVBoxLayout()
        layout.addLayout(group_control)
        layout.addWidget(scroll)
        layout.addLayout(bottom_buttons)
        self.setLayout(layout)

        self.add_group()  # 初期グループ追加

    def add_group(self):
        group = ConditionGroup(
            self.column_names,
            move_up_callback=self.move_group_up,
            move_down_callback=self.move_group_down,
            delete_callback=self.delete_group
        )
        if not self.group_widgets:
            group.set_first_group()
        self.group_widgets.append(group)
        self.group_container.addWidget(group)

    def delete_group(self, group):
        if len(self.group_widgets) == 1:
            QMessageBox.warning(self, _("削除不可"), _("少なくとも1つのグループは必要です。"))
            return
        self.group_widgets.remove(group)
        self._rebuild_group_ui()

    def move_group_up(self, group):
        index = self.group_widgets.index(group)
        if index > 0:
            self.group_widgets[index], self.group_widgets[index - 1] = (
                self.group_widgets[index - 1],
                self.group_widgets[index]
            )
            self._rebuild_group_ui()

    def move_group_down(self, group):
        index = self.group_widgets.index(group)
        if index < len(self.group_widgets) - 1:
            self.group_widgets[index], self.group_widgets[index + 1] = (
                self.group_widgets[index + 1],
                self.group_widgets[index]
            )
            self._rebuild_group_ui()

    def _rebuild_group_ui(self):
        for i in reversed(range(self.group_container.count())):
            widget = self.group_container.itemAt(i).widget()
            if widget:
                self.group_container.removeWidget(widget)
                widget.setParent(None)

        for idx, group in enumerate(self.group_widgets):
            if idx == 0:
                group.set_first_group()
            else:
                group.before_logic_box.setVisible(True)
            self.group_container.addWidget(group)

    def get_condition_groups(self):
        result = []
        for idx, group in enumerate(self.group_widgets):
            group_data = {
                "logic": group.get_group_logic(),
                "conditions": group.get_conditions()
            }
            if idx != 0:
                group_data["before_logic"] = group.get_before_logic()
            result.append(group_data)
        return result

    def check_and_accept(self):
        for group in self.group_widgets:
            for col, op, val in group.get_conditions():
                if not val:
                    QMessageBox.warning(self, _("入力エラー"), _("空の値があります。すべての条件を入力してください。"))
                    return
        self.accept()
