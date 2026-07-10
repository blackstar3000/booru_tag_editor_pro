# ui/dataset_audit.py
"""
Dataset Audit – scans the current folder and generates a report on dataset health.
"""

import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QTextEdit, QProgressBar,
    QMessageBox, QTabWidget, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool
from pathlib import Path
from collections import Counter
from PIL import Image
import json

logger = logging.getLogger(__name__)

class AuditWorkerSignals(QObject):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)

class AuditWorker(QRunnable):
    def __init__(self, image_paths, tag_library=None):
        super().__init__()
        self.image_paths = image_paths
        self.tag_library = tag_library or set()
        self.signals = AuditWorkerSignals()

    def run(self):
        try:
            report = self.generate_report()
            self.signals.finished.emit(report)
        except Exception as e:
            self.signals.error.emit(str(e))

    def generate_report(self):
        total = len(self.image_paths)
        missing_txt = []
        orphan_txt = []
        unknown_tags = set()
        tag_counts = []
        resolutions = Counter()
        file_types = Counter()
        broken_images = []
        tag_counter = Counter()

        # Collect all .txt files in the folder (assuming all in same dir)
        folder = self.image_paths[0].parent if self.image_paths else None
        all_txt = set()
        if folder:
            all_txt = {f for f in folder.glob("*.txt")}

        # Process each image
        for i, img_path in enumerate(self.image_paths):
            txt_path = img_path.with_suffix(".txt")
            if not txt_path.exists():
                missing_txt.append(str(img_path))
            elif txt_path in all_txt:
                all_txt.remove(txt_path)

            # File type
            file_types[img_path.suffix.lower()] += 1

            # Resolution
            try:
                with Image.open(img_path) as img:
                    resolutions[f"{img.width}x{img.height}"] += 1
            except:
                broken_images.append(str(img_path))

            # Tags
            if txt_path.exists():
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            tags = [t.strip() for t in content.split(',') if t.strip()]
                            tag_counts.append(len(tags))
                            tag_counter.update(tags)
                except:
                    pass

            # Progress
            self.signals.progress.emit(i + 1, total)

        # Orphan .txt files
        for txt in all_txt:
            # Check if there's an image with same stem
            img_candidates = list(txt.parent.glob(txt.stem + ".*"))
            if not any(ext in ['.png','.jpg','.jpeg','.webp','.bmp','.gif'] for ext in (p.suffix for p in img_candidates)):
                orphan_txt.append(str(txt))

        # Unknown tags: not in local library
        if self.tag_library:
            known_tags = set(self.tag_library)
            unknown_tags = {tag for tag in tag_counter if tag not in known_tags}

        # Compute stats
        avg_tags = sum(tag_counts) / len(tag_counts) if tag_counts else 0
        min_tags = min(tag_counts) if tag_counts else 0
        max_tags = max(tag_counts) if tag_counts else 0

        report = {
            'total_images': total,
            'missing_txt': missing_txt,
            'orphan_txt': orphan_txt,
            'unknown_tags': sorted(unknown_tags),
            'tag_counts': tag_counts,
            'min_tags': min_tags,
            'max_tags': max_tags,
            'avg_tags': avg_tags,
            'resolutions': dict(resolutions.most_common()),
            'file_types': dict(file_types.most_common()),
            'broken_images': broken_images,
            'tag_frequency': dict(tag_counter.most_common(20)),  # top 20
        }
        return report


class DatasetAudit(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.tag_library = []
        self.threadpool = QThreadPool()
        self.report = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top controls
        ctrl_layout = QHBoxLayout()
        self.scan_btn = QPushButton("🔍 Run Audit")
        self.scan_btn.clicked.connect(self.run_audit)
        ctrl_layout.addWidget(self.scan_btn)

        self.export_btn = QPushButton("💾 Export Report")
        self.export_btn.clicked.connect(self.export_report)
        self.export_btn.setEnabled(False)
        ctrl_layout.addWidget(self.export_btn)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Tabs for report sections
        self.report_tabs = QTabWidget()
        layout.addWidget(self.report_tabs)

        # Summary tab
        self.summary_widget = QTextEdit()
        self.summary_widget.setReadOnly(True)
        self.report_tabs.addTab(self.summary_widget, "📊 Summary")

        # Missing .txt
        self.missing_txt_widget = QTextEdit()
        self.missing_txt_widget.setReadOnly(True)
        self.report_tabs.addTab(self.missing_txt_widget, "❌ Missing .txt")

        # Orphan .txt
        self.orphan_txt_widget = QTextEdit()
        self.orphan_txt_widget.setReadOnly(True)
        self.report_tabs.addTab(self.orphan_txt_widget, "📄 Orphan .txt")

        # Unknown tags
        self.unknown_tags_widget = QTextEdit()
        self.unknown_tags_widget.setReadOnly(True)
        self.report_tabs.addTab(self.unknown_tags_widget, "❓ Unknown Tags")

        # Broken images
        self.broken_images_widget = QTextEdit()
        self.broken_images_widget.setReadOnly(True)
        self.report_tabs.addTab(self.broken_images_widget, "💔 Broken Images")

        # Resolutions
        self.resolutions_widget = QTextEdit()
        self.resolutions_widget.setReadOnly(True)
        self.report_tabs.addTab(self.resolutions_widget, "📐 Resolutions")

        # Tag frequency
        self.tag_freq_widget = QTextEdit()
        self.tag_freq_widget.setReadOnly(True)
        self.report_tabs.addTab(self.tag_freq_widget, "🏷️ Top Tags")

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def set_image_paths(self, paths):
        self.image_paths = paths
        self.clear_report()

    def set_tag_library(self, tags):
        self.tag_library = tags

    def clear_report(self):
        self.report = None
        for widget in [self.summary_widget, self.missing_txt_widget,
                       self.orphan_txt_widget, self.unknown_tags_widget,
                       self.broken_images_widget, self.resolutions_widget,
                       self.tag_freq_widget]:
            widget.clear()
        self.export_btn.setEnabled(False)
        self.status_label.setText("")

    def run_audit(self):
        if not self.image_paths:
            QMessageBox.information(self, "No Images", "Load a folder first.")
            return
        self.clear_report()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.scan_btn.setEnabled(False)
        self.status_label.setText("Scanning...")

        # Load tag library from danbooru cache? We'll use an empty set for now.
        # In the future, we could load from DanbooruClient or a local dictionary.
        tag_lib = set(self.tag_library) if self.tag_library else set()

        worker = AuditWorker(self.image_paths, tag_lib)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.error.connect(self._on_error)
        self.threadpool.start(worker)

    def _on_progress(self, current, total):
        self.progress_bar.setValue(int(current / total * 100))

    def _on_finished(self, report):
        self.report = report
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # Populate tabs
        # Summary
        summary_text = f"""Dataset Audit Report
========================

Total Images: {report['total_images']}

Missing .txt files: {len(report['missing_txt'])}
Orphan .txt files: {len(report['orphan_txt'])}
Broken Images: {len(report['broken_images'])}
Unknown Tags: {len(report['unknown_tags'])}

Tag Statistics:
  Min: {report['min_tags']}
  Max: {report['max_tags']}
  Avg: {report['avg_tags']:.2f}

File Types:
{json.dumps(report['file_types'], indent=2)}

Resolutions:
{json.dumps(report['resolutions'], indent=2)}
"""
        self.summary_widget.setText(summary_text)

        # Missing .txt
        self.missing_txt_widget.setText("\n".join(report['missing_txt']) or "None found.")

        # Orphan .txt
        self.orphan_txt_widget.setText("\n".join(report['orphan_txt']) or "None found.")

        # Unknown tags
        self.unknown_tags_widget.setText("\n".join(report['unknown_tags']) or "None found.")

        # Broken images
        self.broken_images_widget.setText("\n".join(report['broken_images']) or "None found.")

        # Resolutions
        res_lines = [f"{res}: {count}" for res, count in report['resolutions'].items()]
        self.resolutions_widget.setText("\n".join(res_lines) or "No resolution data.")

        # Tag frequency
        freq_lines = [f"{tag}: {count}" for tag, count in report['tag_frequency'].items()]
        self.tag_freq_widget.setText("\n".join(freq_lines) or "No tags found.")

        self.status_label.setText(f"Audit complete. {len(report['missing_txt'])} missing .txt, {len(report['unknown_tags'])} unknown tags.")

    def _on_error(self, error):
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error}")

    def export_report(self):
        if not self.report:
            return
        import json
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Report", "audit_report.json", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.report, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Export", f"Report saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save: {e}")