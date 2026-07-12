"""
Reusable autocomplete popup with Danbooru-category colors and post counts.
ComfyUI-Autocomplete-Plus style inline popup.
"""

import ctypes
import platform
from ctypes import wintypes

from PyQt5.QtWidgets import (
    QListView, QStyledItemDelegate, QStyleOptionViewItem,
    QAbstractItemView, QApplication, QStyle, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QModelIndex, QAbstractListModel, QSize, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QColor, QPainter, QFont, QPen, QBrush

import logging
logger = logging.getLogger(__name__)


def _enable_window_blur(hwnd):
    """Windows 11 Mica/Acrylic backdrop with graceful fallback."""
    if platform.system() != "Windows":
        return False

    hwnd = wintypes.HWND(hwnd)
    dwmapi = ctypes.windll.dwmapi

    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMSBT_AUTO = 0
    DWMSBT_NONE = 1
    DWMSBT_MAINWINDOW = 2
    DWMSBT_TRANSIENTWINDOW = 3
    DWMSBT_TABBEDWINDOW = 4
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20

    def _set_attr(attribute, value):
        value = ctypes.c_int(value)
        return dwmapi.DwmSetWindowAttribute(
            hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
        ) == 0

    try:
        _set_attr(DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    except Exception:
        pass

    try:
        if _set_attr(DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_MAINWINDOW):
            return True
    except Exception:
        pass

    try:
        if _set_attr(DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_TRANSIENTWINDOW):
            return True
    except Exception:
        pass

    try:
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int),
            ]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]

        accent = ACCENT_POLICY()
        accent.AccentState = 4
        accent.GradientColor = 0x99202020
        accent.AccentFlags = 2

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(accent)

        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        return True

    except Exception:
        return False

CATEGORY_COLORS = {
    0: QColor("#88CCEE"),
    1: QColor("#FFB347"),
    3: QColor("#B39DDB"),
    4: QColor("#81C784"),
    5: QColor("#FF8A65"),
}

CATEGORY_NAMES = {
    0: "General",
    1: "Artist",
    3: "Copyright",
    4: "Character",
    5: "Meta",
}


class TagEntry:
    __slots__ = ('name', 'category', 'post_count', 'source')
    def __init__(self, name: str, category: int = 0, post_count: int = 0, source: str = "api"):
        self.name = name
        self.category = category
        self.post_count = post_count
        self.source = source


class TagAutocompleteModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._entries):
            return None
        entry = self._entries[index.row()]
        if role == Qt.DisplayRole:
            return entry.name
        if role == Qt.UserRole:
            return entry.name
        if role == Qt.UserRole + 1:
            return entry.category
        if role == Qt.UserRole + 2:
            return entry.post_count
        return None

    def set_entries(self, entries):
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def entry_at(self, row):
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None


GLASS_SELECTED = QColor(139, 92, 246, 45)
GLASS_HOVER = QColor(255,255,255,18)

GLASS_TEXT = QColor(245,245,245)
GLASS_TEXT_SELECTED = QColor(255,255,255)

GLASS_COUNT = QColor(185,185,185)

class TagAutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        name = index.data(Qt.DisplayRole) or ""
        category = index.data(Qt.UserRole + 1) or 0
        post_count = index.data(Qt.UserRole + 2) or 0
        post_count_str = f"{post_count:,}" if post_count > 0 else ""

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, GLASS_SELECTED)
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, GLASS_HOVER)

        color = CATEGORY_COLORS.get(category, CATEGORY_COLORS[0])
        alpha_color = QColor(color)
        alpha_color.setAlpha(220)
        bar_rect = option.rect.adjusted(4, 5, -(option.rect.width() - 7), -5)
        painter.fillRect(bar_rect, alpha_color)

        text_rect = option.rect.adjusted(14, 0, -80, 0)
        font = option.font
        font.setPointSize(max(9, font.pointSize() - 1))
        painter.setFont(font)
        painter.setPen(GLASS_TEXT_SELECTED if option.state & QStyle.State_Selected else GLASS_TEXT)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, name)

        if post_count_str:
            count_rect = option.rect.adjusted(-80, 0, -8, 0)
            count_font = QFont(font)
            count_font.setPointSize(max(7, font.pointSize() - 2))
            painter.setFont(count_font)
            painter.setPen(GLASS_COUNT)
            painter.drawText(count_rect, Qt.AlignVCenter | Qt.AlignRight, post_count_str)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(280, 30)


def _filter_local_tags(local_tags, query):
    q = query.lower()
    return [TagEntry(t, source="local") for t in local_tags if q in t.lower()]


class TagAutocompletePopup(QListView):
    tag_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._blur_applied = False
        self._model = TagAutocompleteModel(self)
        self.setModel(self._model)
        self.setItemDelegate(TagAutocompleteDelegate(self))
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NativeWindow)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setMaximumHeight(300)
        self.setMinimumWidth(200)
        self.clicked.connect(self._on_clicked)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet("""
QListView {
    background: rgba(22,24,28,90);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 14px;
    padding: 8px;
    outline: none;
}

QListView::item {
    background: transparent;
    padding: 6px 12px;
    border-radius: 8px;
}

QListView::item:selected {
    background: rgba(139,92,246,0.18);
    color: white;
}

QListView::item:hover {
    background: rgba(255,255,255,0.06);
}

QScrollBar:vertical {
    background: rgba(255,255,255,0.04);
    width: 10px;
    margin: 6px 2px 6px 0;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.22);
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,0.32);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: transparent;
    height: 0px;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
        """)
        self._input_widget = None
        QApplication.instance().installEventFilter(self)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._blur_applied:
            self._blur_applied = True
            hwnd = int(self.winId())
            _enable_window_blur(hwnd)

    def install_on(self, input_widget):
        self._input_widget = input_widget
        input_widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if self.isVisible():
            if event.type() == QEvent.MouseButtonPress:
                popup_rect = self.geometry()
                click_pos = event.globalPos() if hasattr(event, 'globalPos') else event.screenPos().toPoint()
                if not popup_rect.contains(click_pos):
                    if self._input_widget:
                        input_global = self._input_widget.mapToGlobal(self._input_widget.rect().topLeft())
                        input_rect = self._input_widget.rect().translated(input_global)
                        if not input_rect.contains(click_pos):
                            self.hide()
                            return False
                    else:
                        self.hide()
                        return False
            elif event.type() == QEvent.KeyPress and obj == self._input_widget:
                if self._handle_key(event):
                    return True
        return super().eventFilter(obj, event)

    def _on_clicked(self, index):
        entry = self._model.entry_at(index.row())
        if entry:
            self.tag_selected.emit(entry.name)
            self.hide()

    def show_suggestions(self, entries, anchor_rect):
        if not entries:
            self.hide()
            return
        self._model.set_entries(entries)
        row_height = 26
        h = min(300, len(entries) * row_height + 6)
        w = anchor_rect.width()
        self.setFixedWidth(w)
        self.setFixedHeight(h)
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            # Position directly below the input, left-aligned
            global_pos = anchor_rect.bottomLeft()
            # Clamp horizontally
            if global_pos.x() + w > available.right():
                global_pos.setX(available.right() - w)
            if global_pos.x() < available.left():
                global_pos.setX(available.left())
            # If doesn't fit below, show above
            bottom = global_pos.y() + h
            if bottom > available.bottom():
                global_pos.setY(anchor_rect.top() - h)
            self.move(global_pos)
        else:
            self.move(anchor_rect.bottomLeft())
        self.setCurrentIndex(self._model.index(0, 0))
        self.show()

    def _handle_key(self, event):
        key = event.key()
        if key == Qt.Key_Down:
            self._select_next()
            return True
        if key == Qt.Key_Up:
            self._select_prev()
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            idx = self.currentIndex()
            if idx.isValid():
                self._on_clicked(idx)
            return True
        if key == Qt.Key_Escape:
            self.hide()
            return True
        return False

    def _select_next(self):
        row = self.currentIndex().row()
        if row < self._model.rowCount() - 1:
            self.setCurrentIndex(self._model.index(row + 1, 0))

    def _select_prev(self):
        row = self.currentIndex().row()
        if row > 0:
            self.setCurrentIndex(self._model.index(row - 1, 0))
