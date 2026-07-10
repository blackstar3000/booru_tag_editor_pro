# ui/duplicate_finder.py
"""
Duplicate Finder – displays groups of duplicate images.
"""

import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QProgressBar,
    QGridLayout, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool
from PyQt5.QtGui import QPixmap, QIcon
from pathlib import Path
from core.duplicate_detector import DuplicateDetector

logger = logging.getLogger(__name__)

class DuplicateWorkerSignals(QObject):
    finished = pyqtSignal(dict)  # groups
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)

class DuplicateWorker(QRunnable):
    def __init__(self, paths, detector):
        super().__init__()
        self.paths = paths
        self.detector = detector
        self.signals = DuplicateWorkerSignals()

    def run(self):
        try:
            total = len(self.paths)
            for i, path in enumerate(self.paths):
                self.detector.compute_hash(path)  # compute and cache
                self.signals.progress.emit(i + 1, total)
            groups = self.detector.find_duplicates(self.paths)
            self.signals.finished.emit(groups)
        except Exception as e:
            self.signals.error.emit(str(e))


class DuplicateGroupWidget(QWidget):
    """A widget that displays a group of duplicate images with thumbnails."""
    deleted = pyqtSignal(Path)  # when a file is deleted

    def __init__(self, group_hash, paths, parent=None):
        super().__init__(parent)
        self.group_hash = group_hash
        self.paths = paths
        self.setup_ui()
        self.thumbnails = []

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.group_label = QLabel(f"Group (Hash: {str(self.group_hash)[:8]}...) - {len(self.paths)} images")
        self.group_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.group_label)

        # Scrollable thumbnail row
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(4)

        for i, path in enumerate(self.paths):
            # Load thumbnail
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                pixmap = QPixmap(80, 80)
                pixmap.fill(Qt.darkGray)
            scaled = pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon = QIcon(scaled)
            item_widget = QWidget()
            item_layout = QVBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel()
            label.setPixmap(scaled)
            label.setToolTip(str(path))
            item_layout.addWidget(label)
            # File name
            name_label = QLabel(path.name[:12] + "...")
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet("font-size: 8px; color: #aaa;")
            item_layout.addWidget(name_label)
            # Delete button
            del_btn = QPushButton("X")
            del_btn.setFixedSize(20, 20)
            del_btn.clicked.connect(lambda checked, p=path: self._delete_file(p))
            item_layout.addWidget(del_btn)

            grid.addWidget(item_widget, 0, i)

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _delete_file(self, path):
        reply = QMessageBox.question(
            self, "Delete File",
            f"Delete {path.name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                path.unlink()
                self.deleted.emit(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete: {e}")


class DuplicateFinder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.threadpool = QThreadPool()
        self.detector = DuplicateDetector()
        self.groups = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top buttons
        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton("🔍 Scan for Duplicates")
        self.scan_btn.clicked.connect(self.scan)
        btn_layout.addWidget(self.scan_btn)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.scan)  # same as scan
        self.refresh_btn.setEnabled(False)
        btn_layout.addWidget(self.refresh_btn)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.delete_selected_btn = QPushButton("🗑️ Delete Selected")
        self.delete_selected_btn.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.delete_selected_btn)

        self.clean_btn = QPushButton("🧹 Keep Best in Each Group")
        self.clean_btn.clicked.connect(self.keep_best)
        btn_layout.addWidget(self.clean_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Scroll area for groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.groups_container = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_container)
        scroll.setWidget(self.groups_container)
        layout.addWidget(scroll)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def set_image_paths(self, paths):
        self.image_paths = paths.copy()
        self.clear_results()

    def clear_results(self):
        for i in reversed(range(self.groups_layout.count())):
            widget = self.groups_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.groups = {}

    def scan(self):
        if not self.image_paths:
            self.status_label.setText("No images loaded.")
            return
        self.clear_results()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Scanning...")
        self.scan_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)

        worker = DuplicateWorker(self.image_paths, self.detector)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_scan_finished)
        worker.signals.error.connect(self._on_error)
        self.threadpool.start(worker)

    def _on_progress(self, current, total):
        self.progress_bar.setValue(int(current / total * 100))

    def _on_scan_finished(self, groups):
        self.groups = groups
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)

        if not groups:
            self.status_label.setText("No duplicate groups found.")
            return

        # Display groups
        for h, paths in groups.items():
            widget = DuplicateGroupWidget(h, paths)
            widget.deleted.connect(self._on_file_deleted)
            self.groups_layout.addWidget(widget)

        self.status_label.setText(f"Found {len(groups)} duplicate groups ({sum(len(v) for v in groups.values())} duplicate images).")

    def _on_error(self, error):
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error}")

    def _on_file_deleted(self, path):
        # Remove the file from the internal list
        if path in self.image_paths:
            self.image_paths.remove(path)
        # Re-scan to update groups
        self.scan()

    def select_all(self):
        # Not implemented: placeholder
        QMessageBox.information(self, "Select All", "Select all duplicates (feature coming soon)")

    def delete_selected(self):
        QMessageBox.information(self, "Delete Selected", "Delete selected (feature coming soon)")

    def keep_best(self):
        if not self.groups:
            return
        reply = QMessageBox.question(
            self, "Keep Best",
            "Keep one image per group (the one with largest resolution) and delete the rest?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        deleted_count = 0
        for h, paths in self.groups.items():
            if len(paths) <= 1:
                continue
            # Find the largest resolution
            best_path = None
            best_area = 0
            for p in paths:
                try:
                    from PIL import Image
                    with Image.open(p) as img:
                        area = img.width * img.height
                        if area > best_area:
                            best_area = area
                            best_path = p
                except:
                    pass
            if best_path:
                to_delete = [p for p in paths if p != best_path]
                for p in to_delete:
                    try:
                        p.unlink()
                        deleted_count += 1
                        if p in self.image_paths:
                            self.image_paths.remove(p)
                    except:
                        pass
        QMessageBox.information(self, "Cleanup Complete", f"Deleted {deleted_count} duplicate files.")
        self.scan()  # Re-scan to update view