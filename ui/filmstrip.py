# ui/filmstrip.py
"""
Filmstrip – horizontal thumbnail strip for rapid image navigation.
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QScrollArea, QListWidget, QListWidgetItem,
    QListView, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon
from pathlib import Path
import logging

from core.image_loader import ImageLoader

logger = logging.getLogger(__name__)

class Filmstrip(QWidget):
    image_selected = pyqtSignal(str)  # emits full path to selected image

    def __init__(self, image_loader: ImageLoader, parent=None):
        super().__init__(parent)
        self.image_loader = image_loader
        self.current_index = -1
        self._suppress_row_signal = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.list_widget = QListWidget()
        self.list_widget.setFlow(QListView.LeftToRight)
        self.list_widget.setWrapping(False)
        self.list_widget.setResizeMode(QListView.Adjust)
        self.list_widget.setIconSize(QSize(100, 100))
        self.list_widget.setGridSize(QSize(110, 110))
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setMinimumHeight(120)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: rgba(0,0,0,0.2);
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: rgba(255,255,255,0.02);
                border-radius: 4px;
                padding: 2px;
            }
            QListWidget::item:selected {
                background: rgba(139,92,246,0.25);
                border: 2px solid #8B5CF6;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background: rgba(255,255,255,0.05);
            }
        """)

        self.list_widget.setFocusPolicy(Qt.StrongFocus)
        self.list_widget.currentRowChanged.connect(self._on_current_row_changed)

        self.scroll_area.setWidget(self.list_widget)
        layout.addWidget(self.scroll_area)

    def set_images(self, paths: list):
        """Populate the filmstrip with thumbnails."""
        self.list_widget.clear()
        self.current_index = -1
        if not paths:
            return
        for path in paths:
            pixmap = self.image_loader.get_pixmap(path)
            if pixmap is None:
                pixmap = QPixmap(100, 100)
                pixmap.fill(Qt.darkGray)
            scaled = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon = QIcon(scaled)
            item = QListWidgetItem(icon, "")
            item.setToolTip(path.name)
            item.setData(Qt.UserRole, str(path))
            self.list_widget.addItem(item)
        # Select the first item if available
        if self.list_widget.count() > 0:
            self.set_current_index(0)

    def set_current_index(self, index: int):
        """Highlight the thumbnail at the given index (programmatic)."""
        if index < 0 or index >= self.list_widget.count():
            return
        self.current_index = index
        self._suppress_row_signal = True
        self.list_widget.setCurrentRow(index)
        self._suppress_row_signal = False
        self.list_widget.scrollToItem(self.list_widget.item(index), QListView.PositionAtCenter)

    def set_current_image(self, path: str):
        """Highlight the thumbnail matching the given path."""
        if not path:
            return
        for i in range(self.list_widget.count()):
            item_path = self.list_widget.item(i).data(Qt.UserRole)
            if item_path == path:
                self.set_current_index(i)
                return

    def navigate(self, delta: int):
        """Move selection by delta and emit the new image."""
        if self.list_widget.count() == 0:
            return
        new_index = self.current_index + delta
        if 0 <= new_index < self.list_widget.count():
            self.list_widget.setCurrentRow(new_index)  # triggers _on_current_row_changed

    def _on_current_row_changed(self, row):
        if self._suppress_row_signal or row < 0:
            return
        self.current_index = row
        self.list_widget.scrollToItem(self.list_widget.item(row), QListView.PositionAtCenter)
        item = self.list_widget.item(row)
        if item:
            path = item.data(Qt.UserRole)
            if path:
                self.image_selected.emit(path)