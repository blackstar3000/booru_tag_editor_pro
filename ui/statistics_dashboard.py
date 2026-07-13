# ui/statistics_dashboard.py
"""
Statistics Dashboard – displays dataset stats (total images, tags, top tags, resolutions, file types).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QMessageBox
)
from PyQt5.QtCore import QThreadPool, pyqtSignal, QObject, QRunnable
import logging
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

class StatsWorkerSignals(QObject):
    finished = pyqtSignal(dict)

class StatsWorker(QRunnable):
    def __init__(self, image_paths):
        super().__init__()
        self.image_paths = image_paths
        self.signals = StatsWorkerSignals()

    def run(self):
        stats = self.compute_stats()
        self.signals.finished.emit(stats)

    def compute_stats(self):
        total_images = len(self.image_paths)
        total_tags = 0
        tag_counter = Counter()
        resolution_counter = Counter()
        file_type_counter = Counter()

        for img_path in self.image_paths:
            # File type
            ext = img_path.suffix.lower()
            file_type_counter[ext] += 1

            # Resolution
            try:
                from PIL import Image
                with Image.open(img_path) as img:
                    w, h = img.size
                    resolution_counter[f"{w}x{h}"] += 1
            except Exception as e:
                logger.debug(f"Failed to read image {img_path}: {e}")

            # Tags
            txt_path = img_path.with_suffix(".txt")
            if txt_path.exists():
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            tags = [t.strip() for t in content.split(',') if t.strip()]
                            total_tags += len(tags)
                            tag_counter.update(tags)
                except Exception as e:
                    logger.debug(f"Failed to read tags from {txt_path}: {e}")

        avg_tags = total_tags / total_images if total_images > 0 else 0
        most_common = tag_counter.most_common(10)
        most_common_res = resolution_counter.most_common(10)

        stats = {
            'total_images': total_images,
            'total_tags': total_tags,
            'avg_tags': avg_tags,
            'most_common_tags': most_common,
            'resolution_counts': most_common_res,
            'file_type_counts': file_type_counter.most_common(),
        }
        return stats


class StatisticsDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.threadpool = None
        self.stats = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.title_label = QLabel("📊 Dataset Statistics")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.title_label)

        # Summary row
        summary_layout = QHBoxLayout()
        self.total_images_label = QLabel("Images: 0")
        self.total_tags_label = QLabel("Tags: 0")
        self.avg_tags_label = QLabel("Avg tags: 0.0")
        summary_layout.addWidget(self.total_images_label)
        summary_layout.addWidget(self.total_tags_label)
        summary_layout.addWidget(self.avg_tags_label)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # Tables
        tables_layout = QHBoxLayout()

        # Most common tags
        tag_widget = QWidget()
        tag_layout = QVBoxLayout(tag_widget)
        tag_layout.addWidget(QLabel("Top Tags"))
        self.tag_table = QTableWidget(0, 2)
        self.tag_table.setHorizontalHeaderLabels(["Tag", "Count"])
        self.tag_table.horizontalHeader().setStretchLastSection(True)
        tag_layout.addWidget(self.tag_table)
        tables_layout.addWidget(tag_widget)

        # Resolution counts
        res_widget = QWidget()
        res_layout = QVBoxLayout(res_widget)
        res_layout.addWidget(QLabel("Resolution Distribution"))
        self.res_table = QTableWidget(0, 2)
        self.res_table.setHorizontalHeaderLabels(["Resolution", "Count"])
        self.res_table.horizontalHeader().setStretchLastSection(True)
        res_layout.addWidget(self.res_table)
        tables_layout.addWidget(res_widget)

        # File types
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.addWidget(QLabel("File Types"))
        self.file_table = QTableWidget(0, 2)
        self.file_table.setHorizontalHeaderLabels(["Type", "Count"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        file_layout.addWidget(self.file_table)
        tables_layout.addWidget(file_widget)

        layout.addLayout(tables_layout)

        # Refresh button
        self.refresh_btn = QPushButton("🔄 Refresh Stats")
        self.refresh_btn.clicked.connect(self.request_refresh)
        layout.addWidget(self.refresh_btn)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def set_image_paths(self, paths, threadpool):
        self.image_paths = paths
        self.threadpool = threadpool
        self.request_refresh()

    def request_refresh(self):
        if not self.image_paths:
            self.status_label.setText("No images loaded.")
            return
        self.status_label.setText("Computing statistics...")
        worker = StatsWorker(self.image_paths)
        worker.signals.finished.connect(self.on_stats_ready)
        self.threadpool.start(worker)

    def on_stats_ready(self, stats):
        self.stats = stats
        self.display_stats()
        self.status_label.setText("Statistics updated.")

    def display_stats(self):
        self.total_images_label.setText(f"Images: {self.stats.get('total_images', 0)}")
        self.total_tags_label.setText(f"Tags: {self.stats.get('total_tags', 0)}")
        self.avg_tags_label.setText(f"Avg tags: {self.stats.get('avg_tags', 0):.2f}")

        # Tags table
        self.tag_table.setRowCount(0)
        for i, (tag, count) in enumerate(self.stats.get('most_common_tags', [])):
            self.tag_table.insertRow(i)
            self.tag_table.setItem(i, 0, QTableWidgetItem(tag))
            self.tag_table.setItem(i, 1, QTableWidgetItem(str(count)))

        # Res table
        self.res_table.setRowCount(0)
        for i, (res, count) in enumerate(self.stats.get('resolution_counts', [])):
            self.res_table.insertRow(i)
            self.res_table.setItem(i, 0, QTableWidgetItem(res))
            self.res_table.setItem(i, 1, QTableWidgetItem(str(count)))

        # File types
        self.file_table.setRowCount(0)
        for i, (ftype, count) in enumerate(self.stats.get('file_type_counts', [])):
            self.file_table.insertRow(i)
            self.file_table.setItem(i, 0, QTableWidgetItem(ftype))
            self.file_table.setItem(i, 1, QTableWidgetItem(str(count)))