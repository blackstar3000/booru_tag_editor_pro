# ui/dialogs/tag_validator_dialog.py
"""
Tag Validator Dialog – validate, fix, and explore booru tags against
the real Danbooru vocabulary (~140k tags).
"""

import ctypes
import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QCheckBox, QComboBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QWidget, QSpinBox,
    QDoubleSpinBox, QLineEdit, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from core.tag_validator import get_validator, CATEGORY_NAMES, TEMPLATE_PRESETS, apply_template

logger = logging.getLogger(__name__)

GLASS_BG = "background: rgba(16, 18, 26, 0.75); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px;"
GLASS_BG2 = "background: rgba(24, 26, 36, 0.85); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px;"

CATEGORY_COLORS = {
    0: "#ccc",
    1: "#f87171",
    3: "#a78bfa",
    4: "#34d399",
    5: "#fbbf24",
}


class TagValidatorDialog(QDialog):
    tags_validated = pyqtSignal(str, list, list)  # output, kept, dropped

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✅ Tag Validator")
        self.setMinimumSize(750, 620)
        self.resize(850, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._validator = get_validator()
        self._setup_ui()
        self.setStyleSheet(self._glass_stylesheet())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QLabel("Tag Validator")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #e2e8f0; border: none;")
        layout.addWidget(header)

        tag_count = self._validator.total_tags if self._validator and self._validator.is_loaded else 0
        info = QLabel(f"Validates against {tag_count:,} real Danbooru tags "
                      "with alias remapping, morphological fixes, and sub-phrase extraction.")
        info.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Input area
        input_label = QLabel("Paste tags (comma-separated):")
        input_label.setStyleSheet("color: #cbd5e1; font-size: 12px; border: none;")
        layout.addWidget(input_label)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(
            "e.g. 1girl, blonde hair, smirking, jean shorts, black crop top, masterpiece, best quality"
        )
        self.input_edit.setMaximumHeight(80)
        self.input_edit.setFont(QFont("Consolas", 11))
        layout.addWidget(self.input_edit)

        # Options row
        opts_layout = QHBoxLayout()

        self.strict_check = QCheckBox("Strict mode")
        self.strict_check.setChecked(True)
        self.strict_check.setToolTip("Drop tags that match no real Danbooru tag")
        opts_layout.addWidget(self.strict_check)

        self.sort_check = QCheckBox("Sort tags")
        self.sort_check.setChecked(True)
        self.sort_check.setToolTip("Reorder tags Danbooru-style: people counts, character, copyright, artist, general, meta")
        opts_layout.addWidget(self.sort_check)

        fuzzy_label = QLabel("Fuzzy cutoff:")
        fuzzy_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        opts_layout.addWidget(fuzzy_label)

        self.fuzzy_spin = QDoubleSpinBox()
        self.fuzzy_spin.setRange(0.0, 1.0)
        self.fuzzy_spin.setSingleStep(0.05)
        self.fuzzy_spin.setValue(0.0)
        self.fuzzy_spin.setDecimals(2)
        self.fuzzy_spin.setFixedWidth(70)
        self.fuzzy_spin.setToolTip("0 = disabled. 0.85+ remaps near-miss typos to real tags.")
        opts_layout.addWidget(self.fuzzy_spin)

        min_count_label = QLabel("Min posts:")
        min_count_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        opts_layout.addWidget(min_count_label)

        self.min_count_spin = QSpinBox()
        self.min_count_spin.setRange(0, 1000000)
        self.min_count_spin.setValue(0)
        self.min_count_spin.setFixedWidth(90)
        self.min_count_spin.setSuffix("  (0=all)")
        opts_layout.addWidget(self.min_count_spin)

        template_label = QLabel("Template:")
        template_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        opts_layout.addWidget(template_label)

        self.template_combo = QComboBox()
        self.template_combo.addItems(list(TEMPLATE_PRESETS.keys()))
        self.template_combo.setCurrentText("tags_only")
        self.template_combo.setFixedWidth(140)
        self.template_combo.setToolTip("Quality-tag wrapper for different model families")
        opts_layout.addWidget(self.template_combo)

        opts_layout.addStretch()

        # Validate button
        self.validate_btn = QPushButton("⚡ Validate")
        self.validate_btn.setStyleSheet(
            "QPushButton { padding: 6px 18px; font-size: 12px; font-weight: bold; "
            "background: rgba(139, 92, 246, 0.3); border: 1px solid rgba(139, 92, 246, 0.5); "
            "border-radius: 8px; color: #e2e8f0; }"
            "QPushButton:hover { background: rgba(139, 92, 246, 0.5); }"
        )
        self.validate_btn.clicked.connect(self._on_validate)
        opts_layout.addWidget(self.validate_btn)

        layout.addLayout(opts_layout)

        # Results splitter: output + details
        splitter = QSplitter(Qt.Vertical)

        # Output area
        out_container = QWidget()
        out_container.setStyleSheet(f"#outContainer {{ {GLASS_BG} }}")
        out_container.setObjectName("outContainer")
        out_layout = QVBoxLayout(out_container)
        out_layout.setContentsMargins(8, 8, 8, 8)

        out_header = QHBoxLayout()
        out_label = QLabel("Validated output:")
        out_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: bold; border: none;")
        out_header.addWidget(out_label)

        self.output_count_label = QLabel("0 tags")
        self.output_count_label.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
        out_header.addWidget(self.output_count_label)
        out_header.addStretch()

        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.setStyleSheet(
            "QPushButton { padding: 3px 10px; font-size: 10px; border-radius: 6px; "
            "background: rgba(59,130,246,0.2); border: 1px solid rgba(59,130,246,0.3); color: #93c5fd; }"
            "QPushButton:hover { background: rgba(59,130,246,0.4); }"
        )
        self.copy_btn.clicked.connect(self._on_copy)
        out_header.addWidget(self.copy_btn)

        out_layout.addLayout(out_header)

        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setFont(QFont("Consolas", 11))
        self.output_edit.setStyleSheet("border: none; background: transparent; color: #a5f3fc;")
        out_layout.addWidget(self.output_edit)

        splitter.addWidget(out_container)

        # Details area: dropped + tag info
        details_container = QWidget()
        details_container.setStyleSheet(f"#detailsContainer {{ {GLASS_BG} }}")
        details_container.setObjectName("detailsContainer")
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(8, 8, 8, 8)

        details_splitter = QSplitter(Qt.Horizontal)

        # Dropped tags
        drop_group = QWidget()
        drop_layout = QVBoxLayout(drop_group)
        drop_layout.setContentsMargins(0, 0, 0, 0)
        drop_label = QLabel("Dropped tags:")
        drop_label.setStyleSheet("color: #f87171; font-size: 12px; font-weight: bold;")
        drop_layout.addWidget(drop_label)

        self.dropped_table = QTableWidget()
        self.dropped_table.setColumnCount(2)
        self.dropped_table.setHorizontalHeaderLabels(["Tag", "Reason"])
        self.dropped_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.dropped_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.dropped_table.verticalHeader().setVisible(False)
        self.dropped_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.dropped_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.dropped_table.setStyleSheet(
            "QTableWidget { background: transparent; border: none; color: #fca5a5; }"
            "QHeaderView::section { background: rgba(255,255,255,0.05); color: #94a3b8; "
            "border: none; padding: 4px; font-size: 11px; }"
        )
        drop_layout.addWidget(self.dropped_table)

        details_splitter.addWidget(drop_group)

        # Tag info table
        info_group = QWidget()
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_label = QLabel("Tag details:")
        info_label.setStyleSheet("color: #a78bfa; font-size: 12px; font-weight: bold;")
        info_layout.addWidget(info_label)

        self.info_table = QTableWidget()
        self.info_table.setColumnCount(4)
        self.info_table.setHorizontalHeaderLabels(["Tag", "Category", "Posts", "Aliases"])
        self.info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.info_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.info_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.info_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.info_table.setStyleSheet(
            "QTableWidget { background: transparent; border: none; color: #e2e8f0; }"
            "QHeaderView::section { background: rgba(255,255,255,0.05); color: #94a3b8; "
            "border: none; padding: 4px; font-size: 11px; }"
        )
        info_layout.addWidget(self.info_table)

        details_splitter.addWidget(info_group)
        details_splitter.setSizes([300, 400])

        details_layout.addWidget(details_splitter)
        splitter.addWidget(details_container)
        splitter.setSizes([250, 250])

        layout.addWidget(splitter)

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px; border: none;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.apply_btn = QPushButton("Apply to editor")
        self.apply_btn.setStyleSheet(
            "QPushButton { padding: 5px 14px; font-size: 11px; font-weight: bold; "
            "background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.3); "
            "border-radius: 8px; color: #6ee7b7; }"
            "QPushButton:hover { background: rgba(16, 185, 129, 0.4); }"
        )
        self.apply_btn.clicked.connect(self._on_apply)
        self.apply_btn.setVisible(False)
        status_layout.addWidget(self.apply_btn)

        layout.addLayout(status_layout)

        self._last_output = ""
        self._last_raw_tags = ""
        self._last_kept = []
        self._last_dropped = []

    def _on_validate(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.status_label.setText("Enter some tags first")
            return

        if not self._validator or not self._validator.is_loaded:
            self.status_label.setText("Tag database not loaded!")
            return

        strict = self.strict_check.isChecked()
        sort_tags = self.sort_check.isChecked()
        fuzzy = self.fuzzy_spin.value()
        min_count = self.min_count_spin.value()

        output, kept, dropped = self._validator.validate(
            text,
            strict=strict,
            fuzzy_cutoff=fuzzy,
            min_post_count=min_count,
            sort_tags=sort_tags,
        )

        preset = self.template_combo.currentText()
        wrapped = apply_template(TEMPLATE_PRESETS[preset], output)

        self._last_output = wrapped
        self._last_raw_tags = output
        self._last_kept = kept
        self._last_dropped = dropped

        self.output_edit.setPlainText(wrapped)
        self.output_count_label.setText(f"{len(kept)} tags")

        # Dropped table
        self.dropped_table.setRowCount(len(dropped))
        for i, tag in enumerate(dropped):
            reason = "Not a real tag"
            if self._validator.resolve(tag, fuzzy):
                reason = "Filtered by min count or category"
            self.dropped_table.setItem(i, 0, QTableWidgetItem(tag))
            self.dropped_table.setItem(i, 1, QTableWidgetItem(reason))

        # Info table for kept tags
        self.info_table.setRowCount(len(kept))
        for i, tag_text in enumerate(kept):
            info = self._validator.get_info(tag_text)
            if info:
                cat = info['category_name']
                cat_item = QTableWidgetItem(cat)
                cat_item.setForeground(
                    QColor(CATEGORY_COLORS.get(info['category'], "#ccc"))
                )
                self.info_table.setItem(i, 0, QTableWidgetItem(info['name']))
                self.info_table.setItem(i, 1, cat_item)
                self.info_table.setItem(i, 2, QTableWidgetItem(f"{info['post_count']:,}"))
                aliases = self._validator.get_aliases(info['name'])
                self.info_table.setItem(i, 3, QTableWidgetItem(", ".join(aliases[:5])))
            else:
                self.info_table.setItem(i, 0, QTableWidgetItem(tag_text))
                self.info_table.setItem(i, 1, QTableWidgetItem("raw"))
                self.info_table.setItem(i, 2, QTableWidgetItem("-"))
                self.info_table.setItem(i, 3, QTableWidgetItem(""))

        self.apply_btn.setVisible(True)
        n_kept = len(kept)
        n_dropped = len(dropped)
        self.status_label.setText(f"Validated: {n_kept} kept, {n_dropped} dropped")

    def _on_copy(self):
        if self._last_output:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(self._last_output)
            self.status_label.setText("Copied to clipboard")

    def _on_apply(self):
        if self._last_output:
            self.tags_validated.emit(self._last_output, self._last_kept, self._last_dropped)
            self.status_label.setText("Applied to editor")

    def set_tags(self, tags_text: str):
        self.input_edit.setPlainText(tags_text)
        self._on_validate()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    def _glass_stylesheet(self):
        return """
            QDialog {
                background: rgba(16, 18, 26, 0.92);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 14px;
                color: #e2e8f0;
            }
            QTableWidget {
                gridline-color: rgba(255, 255, 255, 0.04);
                selection-background-color: rgba(139, 92, 246, 0.25);
            }
            QTableWidget::item {
                padding: 4px 6px;
                font-size: 11px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QCheckBox { color: #cbd5e1; font-size: 11px; spacing: 6px; }
            QCheckBox::indicator {
                width: 14px; height: 14px; border-radius: 3px;
                border: 1px solid rgba(255,255,255,0.2);
                background: rgba(255,255,255,0.05);
            }
            QCheckBox::indicator:checked {
                background: rgba(139, 92, 246, 0.6);
                border-color: rgba(139, 92, 246, 0.8);
            }
            QSpinBox, QDoubleSpinBox {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 5px; padding: 3px 6px; color: #e2e8f0; font-size: 11px;
            }
            QComboBox {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 5px; padding: 4px 8px; color: #e2e8f0; font-size: 11px;
            }
        """
