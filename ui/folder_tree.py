from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTreeView, QLabel, QFileSystemModel, QMenu, QAction
from PyQt5.QtCore import Qt, QDir, pyqtSignal, QPoint
from pathlib import Path
import subprocess
import sys

class FolderTree(QWidget):
    file_selected = pyqtSignal(str)      # full path to selected image file
    folder_selected = pyqtSignal(str)    # full path to selected folder

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel("📂 Folder Browser")
        layout.addWidget(self.label)

        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.model.setNameFilters(['*.png', '*.jpg', '*.jpeg', '*.webp', '*.bmp', '*.gif'])
        self.model.setNameFilterDisables(False)
        self.tree.setModel(self.model)

        self._hide_columns()

        # `currentChanged` fires on mouse click AND keyboard arrow keys.
        # We now use it for BOTH files and folders.
        self._suppress_current_changed = False
        self.tree.selectionModel().currentChanged.connect(self._on_current_changed)
        self.tree.doubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self.tree)

        root_path = str(Path.home())
        root_index = self.model.setRootPath(root_path)
        self.tree.setRootIndex(root_index)

    def _hide_columns(self):
        for col in range(1, self.model.columnCount()):
            self.tree.hideColumn(col)

    def set_root_path(self, path):
        if path and Path(path).exists():
            root_index = self.model.setRootPath(str(path))
            self.tree.setRootIndex(root_index)
            self._hide_columns()

    def _on_current_changed(self, current, previous):
        """Fires on click AND keyboard up/down navigation — loads the image file."""
        if self._suppress_current_changed or not current.isValid():
            return
        path = self.model.filePath(current)
        p = Path(path)
        if p.is_file():
            self.file_selected.emit(path)
        # Folders are loaded on double-click only, so single-click allows expand/collapse

    def select_path(self, path):
        """Programmatically highlight/scroll to a path without re-emitting signals."""
        if not path:
            return
        index = self.model.index(str(path))
        if not index.isValid():
            return
        self._suppress_current_changed = True
        self.tree.setCurrentIndex(index)
        self._suppress_current_changed = False
        self.tree.scrollTo(index)

    def _on_double_clicked(self, index):
        # Double‑click on a folder expands/collapses it AND loads it in the filmstrip
        file_path = self.model.filePath(index)
        if Path(file_path).is_dir():
            self.folder_selected.emit(file_path)

    def _show_context_menu(self, point: QPoint):
        index = self.tree.indexAt(point)
        if not index.isValid():
            return
        path = self.model.filePath(index)
        menu = QMenu()
        if Path(path).is_dir():
            open_action = QAction("📂 Open in Filmstrip", self)
            open_action.triggered.connect(lambda: self.folder_selected.emit(path))
            menu.addAction(open_action)
            refresh_action = QAction("🔄 Refresh", self)
            refresh_action.triggered.connect(lambda: self._refresh_folder(path))
            menu.addAction(refresh_action)
        else:
            reveal_action = QAction("📁 Reveal in Explorer", self)
            reveal_action.triggered.connect(lambda: self._reveal_file(path))
            menu.addAction(reveal_action)
        menu.exec_(self.tree.mapToGlobal(point))

    def _refresh_folder(self, path):
        # Rescan without rerooting the tree
        current_root_index = self.tree.rootIndex()
        self.model.setRootPath(path)          # forces a re‑read of `path`
        self.tree.setRootIndex(current_root_index)  # restore the root
        self._hide_columns()

    def _reveal_file(self, path):
        native_path = str(Path(path))
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', f'/select,{native_path}'])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', '-R', native_path])
        else:
            subprocess.Popen(['xdg-open', str(Path(native_path).parent)])