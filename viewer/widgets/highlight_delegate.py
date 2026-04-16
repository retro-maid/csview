from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtCore import Qt, pyqtSignal


class HighlightDelegate(QStyledItemDelegate):
    # ユーザーがセルを確定したときに (row, col) を通知するシグナル
    cell_committed = pyqtSignal(int, int)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.highlighted_cells = set()      # 置換ハイライト: (row, col) のセット
        self.highlight_color = QColor(255, 255, 0, 100)
        self.edited_cells = set()           # 編集済みセル: (row, col) のセット
        self.edit_color = QColor(255, 235, 180, 80)  # デフォルト: 薄いオレンジ
        self.search_keyword = ""            # 検索キーワードによるテキスト内ハイライト
        self.search_color = QColor(0, 110, 255, 75)   # 半透明の青
        self._apply_color_from_config(config)

    def _apply_color_from_config(self, config) -> None:
        if not config:
            return
        color = QColor(config.get("highlight_color", "#ffff00"))
        color.setAlpha(config.get("highlight_opacity", 100))
        self.highlight_color = color
        edit_color = QColor(config.get("cell_edit_color", "#ffebb4"))
        edit_color.setAlpha(config.get("cell_edit_opacity", 80))
        self.edit_color = edit_color

    # ------------------------------------------------------------------
    # 検索キーワード API
    # ------------------------------------------------------------------

    def set_search_keyword(self, keyword: str) -> None:
        self.search_keyword = keyword

    def clear_search_keyword(self) -> None:
        self.search_keyword = ""

    # ------------------------------------------------------------------
    # 描画
    # ------------------------------------------------------------------

    def paint(self, painter, option, index):
        cell_key = (index.row(), index.column())

        # 置換ハイライト（セル全体を黄色で塗る）
        if cell_key in self.highlighted_cells:
            painter.fillRect(option.rect, QBrush(self.highlight_color))
            super().paint(painter, option, index)
            return

        # 編集済みセルのハイライト（うっすら色を付けてから通常描画）
        if cell_key in self.edited_cells:
            painter.fillRect(option.rect, QBrush(self.edit_color))

        # 通常描画
        super().paint(painter, option, index)

        # 検索キーワードハイライト（テキスト内の一致部分を青でマーク）
        if not self.search_keyword:
            return
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not text:
            return
        kw_lower = self.search_keyword.lower()
        if kw_lower not in text.lower():
            return

        self._paint_keyword_highlight(painter, option, index, text, kw_lower)

    def _paint_keyword_highlight(self, painter, option, index, text, kw_lower):
        """テキスト内のキーワード一致部分に半透明の矩形を重ねる。"""
        style = QApplication.style()
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt)
        if not text_rect.isValid():
            return

        fm = painter.fontMetrics()
        text_lower = text.lower()

        painter.save()
        painter.setClipRect(text_rect)

        pos = 0
        while True:
            idx = text_lower.find(kw_lower, pos)
            if idx == -1:
                break
            before_px = fm.horizontalAdvance(text[:idx])
            kw_px = fm.horizontalAdvance(text[idx: idx + len(self.search_keyword)])
            hl_rect = text_rect.__class__(
                text_rect.left() + before_px,
                text_rect.top() + 1,
                kw_px,
                text_rect.height() - 2,
            )
            painter.fillRect(hl_rect, self.search_color)
            pos = idx + len(self.search_keyword)

        painter.restore()

    # ------------------------------------------------------------------
    # 置換ハイライト API（既存）
    # ------------------------------------------------------------------

    def set_highlighted_cells(self, cells):
        self.highlighted_cells = set(cells)

    def clear_highlights(self):
        self.highlighted_cells.clear()

    def add_highlight(self, row, column):
        self.highlighted_cells.add((row, column))

    def set_highlight_color(self, color):
        self.highlight_color = color

    # ------------------------------------------------------------------
    # 編集済みセル API
    # ------------------------------------------------------------------

    def set_edited_cells(self, cells):
        self.edited_cells = set(cells)

    def add_edited_cell(self, row, column):
        self.edited_cells.add((row, column))

    def clear_edited_cells(self):
        self.edited_cells.clear()

    def setModelData(self, editor, model, index):
        """セル編集確定時に呼ばれる。値が実際に変わった場合のみ cell_committed を通知する。"""
        old_value = index.data(Qt.ItemDataRole.EditRole)
        super().setModelData(editor, model, index)
        new_value = index.data(Qt.ItemDataRole.EditRole)
        if old_value != new_value:
            self.cell_committed.emit(index.row(), index.column())

    def update_from_config(self, config) -> None:
        self._apply_color_from_config(config)
