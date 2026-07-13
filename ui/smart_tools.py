# ui/smart_tools.py
"""
Smart Tools – Smart Collections & Advanced Bulk Operations.
"""

import json
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QProgressBar, QGroupBox, QFormLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QThreadPool, QRunnable, QObject
from pathlib import Path

from core.smart_collection import SmartCollection, CollectionManager, Condition
from core.advanced_bulk import AdvancedBulkOperations
from ui.windows_theme import dark_question, dark_information, dark_warning, dark_critical

logger = logging.getLogger(__name__)


# --- Smart Collections Worker ---
class CollectionApplyWorkerSignals(QObject):
    finished = pyqtSignal(list)  # list of matching paths
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)

class CollectionApplyWorker(QRunnable):
    def __init__(self, image_paths, collection):
        super().__init__()
        self.image_paths = image_paths
        self.collection = collection
        self.signals = CollectionApplyWorkerSignals()

    def run(self):
        try:
            matching = []
            total = len(self.image_paths)
            for i, path in enumerate(self.image_paths):
                metadata = self._get_metadata(path)
                if self.collection.matches(metadata):
                    matching.append(path)
                self.signals.progress.emit(i+1, total)
            self.signals.finished.emit(matching)
        except Exception as e:
            self.signals.error.emit(str(e))

    def _get_metadata(self, path):
        metadata = {
            'tags': [],
            'width': 0,
            'height': 0,
            'file_type': path.suffix.lower(),
            'file_date': path.stat().st_mtime,
        }
        txt_path = path.with_suffix(".txt")
        if txt_path.exists():
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        metadata['tags'] = [t.strip() for t in content.split(',') if t.strip()]
            except Exception as e:
                logger.debug(f"Failed to read tags from {txt_path}: {e}")
        try:
            from PIL import Image
            with Image.open(path) as img:
                metadata['width'] = img.width
                metadata['height'] = img.height
        except Exception as e:
            logger.debug(f"Failed to read image dimensions for {path}: {e}")
        return metadata

# --- Advanced Bulk Worker ---
class BulkWorkerSignals(QObject):
    finished = pyqtSignal(dict)  # stats
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)
    preview = pyqtSignal(list)  # list of (path, before, after)

class BulkWorker(QRunnable):
    def __init__(self, image_paths, operation, params):
        super().__init__()
        self.image_paths = image_paths
        self.operation = operation
        self.params = params
        self.signals = BulkWorkerSignals()
        self._changes = []  # (img_path, txt_path, new_tags_str)

    def run(self):
        """Compute all tag changes and emit preview. Does NOT write files."""
        try:
            modified_count = 0
            preview_items = []
            total = len(self.image_paths)
            for i, img_path in enumerate(self.image_paths):
                txt_path = img_path.with_suffix(".txt")
                if not txt_path.exists():
                    self.signals.progress.emit(i+1, total)
                    continue
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        tags = [t.strip() for t in content.split(',') if t.strip()] if content else []
                except Exception as e:
                    logger.debug(f"Failed to read tags from {txt_path}: {e}")
                    tags = []
                original = tags.copy()
                # Apply operation
                if self.operation == "Add Tag":
                    tags = AdvancedBulkOperations.apply_add_tag(tags, self.params['tag'])
                elif self.operation == "Remove Tag":
                    tags = AdvancedBulkOperations.apply_remove_tag(tags, self.params['tag'])
                elif self.operation == "Replace Tag":
                    tags = AdvancedBulkOperations.apply_replace_tag(tags, self.params['old_tag'], self.params['new_tag'])
                elif self.operation == "Regex Find/Replace":
                    tags = AdvancedBulkOperations.apply_regex_find_replace(tags, self.params['find'], self.params['replace'])
                elif self.operation == "Merge Tags":
                    tags = AdvancedBulkOperations.apply_merge_tags(tags, self.params['merge_map'])
                elif self.operation == "Split Tags":
                    tags = AdvancedBulkOperations.apply_split_tags(tags, self.params['delimiter'])
                elif self.operation == "Prefix":
                    tags = AdvancedBulkOperations.apply_prefix(tags, self.params['prefix'])
                elif self.operation == "Suffix":
                    tags = AdvancedBulkOperations.apply_suffix(tags, self.params['suffix'])
                elif self.operation == "Rename Tags":
                    tags = AdvancedBulkOperations.apply_rename_tags(tags, self.params['rename_map'])
                elif self.operation == "Remove by Pattern":
                    tags = AdvancedBulkOperations.apply_remove_by_pattern(tags, self.params['pattern'])
                elif self.operation == "Sort Tags":
                    tags = AdvancedBulkOperations.apply_sort_tags(tags, self.params.get('sort_type', 'alphabetical'))
                elif self.operation == "Normalize":
                    tags = AdvancedBulkOperations.apply_normalize(tags)
                if tags != original:
                    modified_count += 1
                    new_tags_str = ", ".join(tags)
                    self._changes.append((img_path, txt_path, new_tags_str))
                    if len(preview_items) < 10:
                        preview_items.append((str(img_path), ", ".join(original), new_tags_str))
                self.signals.progress.emit(i+1, total)
            self.signals.preview.emit(preview_items)
            self.signals.finished.emit({'modified_count': modified_count, 'total': total})
        except Exception as e:
            self.signals.error.emit(str(e))

    def apply(self):
        """Write all previously computed changes to disk."""
        written = 0
        for img_path, txt_path, new_tags_str in self._changes:
            try:
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(new_tags_str)
                written += 1
            except Exception as e:
                logger.warning(f"Failed to write tags to {txt_path}: {e}")
        return written


class SmartTools(QWidget):
    filter_applied = pyqtSignal(object)  # None or list of paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.threadpool = QThreadPool()
        self.collection_manager = CollectionManager(Path(__file__).parent.parent / "smart_collections.json")
        self.current_collection = None
        self.filtered_paths = None
        self._pending_worker = None
        self.setup_ui()
        self.refresh_collections_list()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._create_collections_tab(), "📂 Smart Collections")
        tabs.addTab(self._create_bulk_tab(), "🔧 Bulk Operations")
        layout.addWidget(tabs)

    def _create_collections_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        splitter = QSplitter(Qt.Horizontal)

        # Left: collections list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Collections"))
        self.collections_list = QListWidget()
        self.collections_list.itemClicked.connect(self._on_collection_selected)
        left_layout.addWidget(self.collections_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ New")
        add_btn.clicked.connect(self._new_collection)
        btn_row.addWidget(add_btn)
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(self._delete_collection)
        btn_row.addWidget(delete_btn)
        apply_btn = QPushButton("📂 Apply to Filmstrip")
        apply_btn.clicked.connect(self._apply_collection)
        btn_row.addWidget(apply_btn)
        clear_btn = QPushButton("📂 Show All")
        clear_btn.clicked.connect(self._clear_collection)
        btn_row.addWidget(clear_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_widget)

        # Right: editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.editor_group = QGroupBox("Collection Editor")
        form = QFormLayout(self.editor_group)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Collection name")
        form.addRow("Name:", self.name_edit)

        # Conditions list
        form.addRow(QLabel("Conditions:"))
        self.conditions_widget = QWidget()
        cond_layout = QVBoxLayout(self.conditions_widget)
        self.condition_items = []  # list of (type_combo, operator_combo, value_edit)
        self.add_condition_btn = QPushButton("➕ Add Condition")
        self.add_condition_btn.clicked.connect(self._add_condition_row)
        cond_layout.addWidget(self.add_condition_btn)
        form.addRow(self.conditions_widget)

        # Logic: AND/OR
        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["AND", "OR"])
        form.addRow("Logic:", self.logic_combo)

        self.save_collection_btn = QPushButton("💾 Save Collection")
        self.save_collection_btn.clicked.connect(self._save_collection)
        form.addRow(self.save_collection_btn)

        right_layout.addWidget(self.editor_group)
        splitter.addWidget(right_widget)

        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

        return widget

    def _create_bulk_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Operation selection
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Operation:"))
        self.op_combo = QComboBox()
        self.op_combo.addItems([
            "Add Tag", "Remove Tag", "Replace Tag",
            "Regex Find/Replace", "Merge Tags", "Split Tags",
            "Prefix", "Suffix", "Rename Tags", "Remove by Pattern",
            "Sort Tags", "Normalize"
        ])
        self.op_combo.currentIndexChanged.connect(self._on_op_changed)
        op_row.addWidget(self.op_combo)
        op_row.addStretch()
        layout.addLayout(op_row)

        # Parameters area
        self.params_widget = QWidget()
        self.params_layout = QFormLayout(self.params_widget)
        layout.addWidget(self.params_widget)

        # Preview table
        layout.addWidget(QLabel("Preview (first 10 affected):"))
        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setHorizontalHeaderLabels(["File", "Before", "After"])
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.preview_table)

        # Progress and run
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_row.addWidget(self.progress_bar)

        self.run_btn = QPushButton("▶️ Preview")
        self.run_btn.clicked.connect(self._run_bulk)
        progress_row.addWidget(self.run_btn)

        self.apply_btn = QPushButton("💾 Apply Changes")
        self.apply_btn.clicked.connect(self._apply_bulk)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setVisible(False)
        progress_row.addWidget(self.apply_btn)

        layout.addLayout(progress_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Initialize params for default operation
        self._on_op_changed(0)
        return widget

    # --- Smart Collections methods ---
    def _on_collection_selected(self, item):
        name = item.text()
        collection = self.collection_manager.get(name)
        if not collection:
            return
        self.current_collection = collection
        self.name_edit.setText(collection.name)
        self._clear_conditions()
        for cond in collection.conditions:
            self._add_condition_row()
            row = self.condition_items[-1]
            row['type'].setCurrentText(cond.type)
            row['operator'].setCurrentText(cond.operator)
            row['value'].setText(str(cond.value))
        self.logic_combo.setCurrentText(collection.logic)

    def _new_collection(self):
        self.name_edit.clear()
        self._clear_conditions()
        self.logic_combo.setCurrentIndex(0)
        self.current_collection = None

    def _delete_collection(self):
        item = self.collections_list.currentItem()
        if not item:
            return
        name = item.text()
        if dark_question(self, "Delete", f"Delete collection '{name}'?") == QMessageBox.Yes:
            self.collection_manager.delete(name)
            self.refresh_collections_list()
            self._new_collection()

    def _clear_conditions(self):
        for row in self.condition_items:
            for w in row.values():
                w.deleteLater()
        self.condition_items.clear()

    def _add_condition_row(self):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        type_combo = QComboBox()
        type_combo.addItems([
            "tag_contains", "tag_not_contains", "tag_count",
            "width", "height", "file_type", "file_date",
            "tag_has_any", "tag_has_all"
        ])
        operator_combo = QComboBox()
        operator_combo.addItems(["==", "!=", ">=", "<=", ">", "<", "contains", "not_contains", "in"])
        value_edit = QLineEdit()
        value_edit.setPlaceholderText("Value")
        remove_btn = QPushButton("✖")
        remove_btn.setFixedSize(20, 20)
        remove_btn.clicked.connect(lambda: self._remove_condition(row_widget))
        row_layout.addWidget(type_combo)
        row_layout.addWidget(operator_combo)
        row_layout.addWidget(value_edit, 1)
        row_layout.addWidget(remove_btn)

        self.conditions_widget.layout().insertWidget(self.conditions_widget.layout().count()-1, row_widget)
        self.condition_items.append({
            'widget': row_widget,
            'type': type_combo,
            'operator': operator_combo,
            'value': value_edit
        })

    def _remove_condition(self, widget):
        widget.deleteLater()
        self.condition_items = [item for item in self.condition_items if item['widget'] != widget]

    def _save_collection(self):
        name = self.name_edit.text().strip()
        if not name:
            dark_warning(self, "Error", "Name is required.")
            return
        conditions = []
        for row in self.condition_items:
            ctype = row['type'].currentText()
            cop = row['operator'].currentText()
            val = row['value'].text().strip()
            if not val:
                dark_warning(self, "Error", "All condition values must be filled.")
                return
            if ctype in ["tag_count", "width", "height"]:
                try:
                    val = int(val)
                except ValueError:
                    dark_warning(self, "Error", f"{ctype} requires a number.")
                    return
            conditions.append({"type": ctype, "value": val, "operator": cop})
        logic = self.logic_combo.currentText()
        collection = SmartCollection(name, conditions, logic)
        self.collection_manager.add(collection)
        self.refresh_collections_list()
        dark_information(self, "Saved", f"Collection '{name}' saved.")

    def refresh_collections_list(self):
        self.collections_list.clear()
        for c in self.collection_manager.collections:
            self.collections_list.addItem(c.name)

    def _apply_collection(self):
        item = self.collections_list.currentItem()
        if not item:
            dark_warning(self, "Error", "No collection selected.")
            return
        name = item.text()
        collection = self.collection_manager.get(name)
        if not collection:
            return
        if not self.image_paths:
            dark_warning(self, "Error", "No images loaded.")
            return
        self.status_label.setText("Applying collection...")
        worker = CollectionApplyWorker(self.image_paths, collection)
        worker.signals.finished.connect(self._on_collection_applied)
        worker.signals.error.connect(lambda e: self.status_label.setText(f"Error: {e}"))
        self.threadpool.start(worker)

    def _on_collection_applied(self, matching_paths):
        self.filtered_paths = matching_paths
        self.status_label.setText(f"Collection applied: {len(matching_paths)} images")
        self.filter_applied.emit(matching_paths)  # emit to main window

    def _clear_collection(self):
        self.filtered_paths = None
        self.filter_applied.emit(None)  # signal to reset to all

    # --- Bulk Operations methods ---
    def _on_op_changed(self, index):
        for i in reversed(range(self.params_layout.count())):
            widget = self.params_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        op = self.op_combo.currentText()
        if op == "Add Tag":
            self._add_param("Tag:", "tag")
        elif op == "Remove Tag":
            self._add_param("Tag:", "tag")
        elif op == "Replace Tag":
            self._add_param("Old Tag:", "old_tag")
            self._add_param("New Tag:", "new_tag")
        elif op == "Regex Find/Replace":
            self._add_param("Find Pattern:", "find")
            self._add_param("Replace With:", "replace")
        elif op == "Merge Tags":
            self._add_param("Merge Map (JSON dict):", "merge_map", "e.g. {'old1':'new1', 'old2':'new2'}")
        elif op == "Split Tags":
            self._add_param("Delimiter:", "delimiter")
        elif op == "Prefix":
            self._add_param("Prefix:", "prefix")
        elif op == "Suffix":
            self._add_param("Suffix:", "suffix")
        elif op == "Rename Tags":
            self._add_param("Rename Map (JSON dict):", "rename_map", "e.g. {'old1':'new1'}")
        elif op == "Remove by Pattern":
            self._add_param("Pattern (regex):", "pattern")
        elif op == "Sort Tags":
            self._add_param("Sort Type:", "sort_type", combobox=["alphabetical", "reverse", "by_length"])
        elif op == "Normalize":
            pass

    def _add_param(self, label, key, placeholder="", combobox=None):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        label_widget = QLabel(label)
        row_layout.addWidget(label_widget)
        if combobox:
            widget = QComboBox()
            widget.addItems(combobox)
            row_layout.addWidget(widget)
        else:
            widget = QLineEdit()
            widget.setPlaceholderText(placeholder)
            row_layout.addWidget(widget)
        row_layout.addStretch()
        self.params_layout.addRow(row)
        setattr(self, f"_param_{key}", widget)

    def _get_param_value(self, key):
        widget = getattr(self, f"_param_{key}", None)
        if widget is None:
            return None
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return widget.text().strip()

    def _run_bulk(self):
        if not self.image_paths:
            dark_warning(self, "Error", "No images loaded.")
            return
        op = self.op_combo.currentText()
        params = {}
        try:
            if op == "Add Tag":
                tag = self._get_param_value('tag')
                if not tag:
                    raise ValueError("Tag required.")
                params['tag'] = tag
            elif op == "Remove Tag":
                tag = self._get_param_value('tag')
                if not tag:
                    raise ValueError("Tag required.")
                params['tag'] = tag
            elif op == "Replace Tag":
                old = self._get_param_value('old_tag')
                new = self._get_param_value('new_tag')
                if not old:
                    raise ValueError("Old tag required.")
                params['old_tag'] = old
                params['new_tag'] = new
            elif op == "Regex Find/Replace":
                find = self._get_param_value('find')
                replace = self._get_param_value('replace')
                if not find:
                    raise ValueError("Find pattern required.")
                params['find'] = find
                params['replace'] = replace
            elif op == "Merge Tags":
                merge_map_str = self._get_param_value('merge_map')
                try:
                    merge_map = json.loads(merge_map_str)
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON for merge map.")
                params['merge_map'] = merge_map
            elif op == "Split Tags":
                delim = self._get_param_value('delimiter')
                if not delim:
                    raise ValueError("Delimiter required.")
                params['delimiter'] = delim
            elif op == "Prefix":
                prefix = self._get_param_value('prefix')
                params['prefix'] = prefix
            elif op == "Suffix":
                suffix = self._get_param_value('suffix')
                params['suffix'] = suffix
            elif op == "Rename Tags":
                rename_map_str = self._get_param_value('rename_map')
                try:
                    rename_map = json.loads(rename_map_str)
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON for rename map.")
                params['rename_map'] = rename_map
            elif op == "Remove by Pattern":
                pattern = self._get_param_value('pattern')
                if not pattern:
                    raise ValueError("Pattern required.")
                params['pattern'] = pattern
            elif op == "Sort Tags":
                sort_type = self._get_param_value('sort_type')
                params['sort_type'] = sort_type
            elif op == "Normalize":
                pass
        except Exception as e:
            dark_warning(self, "Error", str(e))
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(False)
        self.apply_btn.setVisible(False)
        self.apply_btn.setEnabled(False)
        self.status_label.setText("Previewing...")

        self._pending_worker = BulkWorker(self.image_paths, op, params)
        worker = self._pending_worker
        worker.signals.progress.connect(self._on_bulk_progress)
        worker.signals.preview.connect(self._on_bulk_preview)
        worker.signals.finished.connect(self._on_bulk_finished)
        worker.signals.error.connect(self._on_bulk_error)
        self.threadpool.start(worker)

    def _on_bulk_progress(self, current, total):
        self.progress_bar.setValue(int(current / total * 100))

    def _on_bulk_preview(self, preview_items):
        self.preview_table.setRowCount(0)
        for row, (f, before, after) in enumerate(preview_items):
            self.preview_table.insertRow(row)
            self.preview_table.setItem(row, 0, QTableWidgetItem(Path(f).name))
            self.preview_table.setItem(row, 1, QTableWidgetItem(before))
            self.preview_table.setItem(row, 2, QTableWidgetItem(after))

    def _on_bulk_finished(self, stats):
        self.progress_bar.setVisible(False)
        self.run_btn.setEnabled(True)
        if stats['modified_count'] > 0:
            self.apply_btn.setVisible(True)
            self.apply_btn.setEnabled(True)
            self.status_label.setText(f"Preview done. {stats['modified_count']} files would be modified. Click 'Apply Changes' to commit.")
        else:
            self.status_label.setText("No files would be modified.")

    def _on_bulk_error(self, error):
        self.progress_bar.setVisible(False)
        self.run_btn.setEnabled(True)
        self.apply_btn.setVisible(False)
        self.apply_btn.setEnabled(False)
        self._pending_worker = None
        self.status_label.setText(f"Error: {error}")
        dark_critical(self, "Error", error)

    def _apply_bulk(self):
        if not self._pending_worker:
            return
        reply = dark_question(self, "Confirm", "Apply all pending changes? This cannot be undone easily.", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        written = self._pending_worker.apply()
        self._pending_worker = None
        self.apply_btn.setVisible(False)
        self.apply_btn.setEnabled(False)
        self.status_label.setText(f"Applied: {written} files modified.")
        dark_information(self, "Complete", f"Applied changes to {written} files.")

    # --- External API ---
    def set_image_paths(self, paths):
        self.image_paths = paths
        self.filtered_paths = None
        self._pending_worker = None
        self.apply_btn.setVisible(False)
        self.apply_btn.setEnabled(False)
        self.status_label.setText("Ready")
        self.preview_table.setRowCount(0)
        self.progress_bar.setVisible(False)
        self.run_btn.setEnabled(True)