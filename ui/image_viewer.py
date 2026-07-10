from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu, QAction
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QResizeEvent
import logging

logger = logging.getLogger(__name__)

class ImageViewer(QWidget):
    context_menu_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 10px;")
        self.label.setMinimumHeight(400)
        self.label.setText("No image loaded")
        self.label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.label.customContextMenuRequested.connect(lambda pt: self.context_menu_requested.emit(pt))
        self.layout.addWidget(self.label)

    def set_pixmap(self, pixmap: QPixmap):
        self._original_pixmap = pixmap
        self._update_display()

    def _update_display(self):
        if self._original_pixmap is None or self._original_pixmap.isNull():
            self.label.setText("No image loaded")
            return
        size = self.label.size()
        if size.width() > 10 and size.height() > 10:
            scaled = self._original_pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            scaled = self._original_pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(scaled)

    def resizeEvent(self, event):
        self._update_display()
        super().resizeEvent(event)

    def clear(self):
        self._original_pixmap = None
        self.label.clear()
        self.label.setText("No image loaded")
