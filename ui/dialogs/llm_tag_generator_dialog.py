# ui/dialogs/llm_tag_generator_dialog.py
"""
LLM Tag Generator Dialog – convert natural language scene descriptions
into validated booru tags using a local LLM server.
"""

import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit,
    QSplitter, QWidget, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from core.llm_client import LLMClient
from core.tag_validator import (
    get_validator, TEMPLATE_PRESETS, DEFAULT_SYSTEM_PROMPT,
    apply_template
)
from core.settings_manager import SettingsManager
from ui.windows_theme import set_dark_title_bar
from ui.dialogs.llm_tag_generator_help import LLMTagGeneratorHelpDialog

logger = logging.getLogger(__name__)

GLASS_BG = "background: rgba(16, 18, 26, 0.75); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px;"
GLASS_BG2 = "background: rgba(24, 26, 36, 0.85); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px;"

ACCENT_BTN = (
    "QPushButton { padding: 8px 20px; font-size: 12px; font-weight: bold; "
    "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8B5CF6, stop:1 #7C3AED); "
    "color: white; border: none; border-radius: 8px; }"
    "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9B6CF6, stop:1 #8C4AED); }"
    "QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6B2AED, stop:1 #5B1AED); }"
    "QPushButton:disabled { background: rgba(139, 92, 246, 0.25); color: rgba(255,255,255,0.3); }"
)

SECONDARY_BTN = (
    "QPushButton { padding: 5px 14px; font-size: 11px; font-weight: bold; "
    "background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.3); "
    "border-radius: 8px; color: #6ee7b7; }"
    "QPushButton:hover { background: rgba(16, 185, 129, 0.4); }"
)

COPY_BTN = (
    "QPushButton { padding: 3px 10px; font-size: 10px; border-radius: 6px; "
    "background: rgba(59,130,246,0.2); border: 1px solid rgba(59,130,246,0.3); color: #93c5fd; }"
    "QPushButton:hover { background: rgba(59,130,246,0.4); }"
)


class LLMTagGeneratorDialog(QDialog):
    tags_generated = pyqtSignal(str)  # validated tags string

    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("🧠 LLM Tag Generator")
        self.setMinimumSize(700, 600)
        self.resize(800, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._validator = get_validator()
        self._llm = LLMClient(self)
        self._llm.finished.connect(self._on_llm_finished)
        self._llm.error.connect(self._on_llm_error)

        self._setup_ui()
        self._load_settings()
        self.setStyleSheet(self._glass_stylesheet())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QLabel("LLM Tag Generator")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #e2e8f0; border: none;")
        layout.addWidget(header)

        info = QLabel("Describe a scene in plain English. The LLM converts it to booru tags, "
                       "validated against the real Danbooru vocabulary.")
        info.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Main splitter: top (input + settings), bottom (output)
        main_splitter = QSplitter(Qt.Vertical)

        # --- Top: scene input + settings ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        # Scene description
        scene_label = QLabel("Scene description:")
        scene_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: bold; border: none;")
        top_layout.addWidget(scene_label)

        self.scene_edit = QTextEdit()
        self.scene_edit.setPlaceholderText(
            "e.g. A cheerful blonde girl in a red dress on a beach at sunset, "
            "arms crossed and smiling"
        )
        self.scene_edit.setMaximumHeight(80)
        self.scene_edit.setFont(QFont("Consolas", 11))
        top_layout.addWidget(self.scene_edit)

        # Settings row
        settings_row = QHBoxLayout()

        server_label = QLabel("Server:")
        server_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        settings_row.addWidget(server_label)

        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText("http://localhost:11434 (Ollama) or :1234 (LM Studio)")
        self.server_edit.setFixedWidth(200)
        settings_row.addWidget(self.server_edit)

        model_label = QLabel("Model:")
        model_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        settings_row.addWidget(model_label)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("qwen3:1.7b (Ollama)")
        self.model_edit.setFixedWidth(160)
        settings_row.addWidget(self.model_edit)

        temp_label = QLabel("Temp:")
        temp_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        settings_row.addWidget(temp_label)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.05)
        self.temp_spin.setValue(0.4)
        self.temp_spin.setDecimals(2)
        self.temp_spin.setFixedWidth(60)
        settings_row.addWidget(self.temp_spin)

        tokens_label = QLabel("Tokens:")
        tokens_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        settings_row.addWidget(tokens_label)

        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(50, 2000)
        self.tokens_spin.setSingleStep(50)
        self.tokens_spin.setValue(500)
        self.tokens_spin.setFixedWidth(60)
        settings_row.addWidget(self.tokens_spin)

        settings_row.addStretch()

        # Generate button
        self.generate_btn = QPushButton("⚡ Generate Tags")
        self.generate_btn.setStyleSheet(ACCENT_BTN)
        self.generate_btn.clicked.connect(self._on_generate)
        settings_row.addWidget(self.generate_btn)

        top_layout.addLayout(settings_row)

        # Template row
        template_row = QHBoxLayout()

        template_label = QLabel("Template:")
        template_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        template_row.addWidget(template_label)

        self.template_combo = QComboBox()
        self.template_combo.addItems(list(TEMPLATE_PRESETS.keys()))
        self.template_combo.setCurrentText("nova_anime_xl")
        self.template_combo.setFixedWidth(140)
        template_row.addWidget(self.template_combo)

        self.thinking_check = QPushButton("🧠 Thinking")
        self.thinking_check.setCheckable(True)
        self.thinking_check.setChecked(False)
        self.thinking_check.setStyleSheet(
            "QPushButton { padding: 3px 10px; font-size: 10px; border-radius: 6px; "
            "background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; }"
            "QPushButton:checked { background: rgba(139,92,246,0.3); border-color: rgba(139,92,246,0.5); color: #c4b5fd; }"
        )
        template_row.addWidget(self.thinking_check)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("API key (optional)")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setFixedWidth(160)
        template_row.addWidget(self.api_key_edit)

        top_layout.addLayout(template_row)

        # System prompt (collapsible)
        self.toggle_prompt_btn = QPushButton("▸ System prompt")
        self.toggle_prompt_btn.setStyleSheet(
            "QPushButton { text-align: left; color: #94a3b8; font-size: 11px; "
            "background: transparent; border: none; padding: 2px 0; }"
            "QPushButton:hover { color: #c4b5fd; }"
        )
        self.toggle_prompt_btn.clicked.connect(self._toggle_system_prompt)
        top_layout.addWidget(self.toggle_prompt_btn)

        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setPlainText(DEFAULT_SYSTEM_PROMPT)
        self.system_prompt_edit.setMaximumHeight(120)
        self.system_prompt_edit.setFont(QFont("Consolas", 10))
        self.system_prompt_edit.setVisible(False)
        top_layout.addWidget(self.system_prompt_edit)

        main_splitter.addWidget(top_widget)

        # --- Bottom: output ---
        output_widget = QWidget()
        output_widget.setStyleSheet(f"#outputWidget {{ {GLASS_BG} }}")
        output_widget.setObjectName("outputWidget")
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(8, 8, 8, 8)

        out_header = QHBoxLayout()
        out_label = QLabel("Generated tags:")
        out_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: bold; border: none;")
        out_header.addWidget(out_label)

        self.tag_count_label = QLabel("0 tags")
        self.tag_count_label.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
        out_header.addWidget(self.tag_count_label)
        out_header.addStretch()

        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.setStyleSheet(COPY_BTN)
        self.copy_btn.clicked.connect(self._on_copy)
        out_header.addWidget(self.copy_btn)

        output_layout.addLayout(out_header)

        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setFont(QFont("Consolas", 11))
        self.output_edit.setStyleSheet("border: none; background: transparent; color: #a5f3fc;")
        output_layout.addWidget(self.output_edit)

        # Dropped tags display
        self.dropped_label = QLabel("")
        self.dropped_label.setStyleSheet("color: #f87171; font-size: 10px; border: none;")
        self.dropped_label.setWordWrap(True)
        output_layout.addWidget(self.dropped_label)

        main_splitter.addWidget(output_widget)
        main_splitter.setSizes([250, 300])

        layout.addWidget(main_splitter)

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px; border: none;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.apply_btn = QPushButton("Apply to editor")
        self.apply_btn.setStyleSheet(SECONDARY_BTN)
        self.apply_btn.clicked.connect(self._on_apply)
        self.apply_btn.setVisible(False)
        status_layout.addWidget(self.apply_btn)

        self.help_btn = QPushButton("? Help")
        self.help_btn.setStyleSheet(SECONDARY_BTN)
        self.help_btn.clicked.connect(self._on_help)
        status_layout.addWidget(self.help_btn)

        layout.addLayout(status_layout)

        self._last_output = ""
        self._last_kept = []

    def _toggle_system_prompt(self):
        vis = not self.system_prompt_edit.isVisible()
        self.system_prompt_edit.setVisible(vis)
        self.toggle_prompt_btn.setText(("▾" if vis else "▸") + " System prompt")

    def _on_generate(self):
        scene = self.scene_edit.toPlainText().strip()
        if not scene:
            self.status_label.setText("Enter a scene description first")
            return

        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("⏳ Generating...")
        self.status_label.setText("Calling LLM...")
        self.output_edit.clear()
        self.dropped_label.clear()

        self._llm.generate(
            user_prompt=scene,
            system_prompt=self.system_prompt_edit.toPlainText().strip() or DEFAULT_SYSTEM_PROMPT,
            server_url=self.server_edit.text().strip() or "http://localhost:11434",
            model=self.model_edit.text().strip() or "qwen3:1.7b",
            temperature=self.temp_spin.value(),
            max_tokens=self.tokens_spin.value(),
            enable_thinking=self.thinking_check.isChecked(),
            api_key=self.api_key_edit.text().strip(),
            timeout=self._settings.llm_timeout,
        )

    def _on_llm_finished(self, raw_tags):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("⚡ Generate Tags")

        if not raw_tags.strip():
            self.status_label.setText("LLM returned empty response")
            return

        # Validate against Danbooru
        if self._validator and self._validator.is_loaded:
            output, kept, dropped = self._validator.validate(
                raw_tags, strict=True, sort_tags=True
            )
        else:
            output = raw_tags
            kept = [t.strip() for t in raw_tags.split(",") if t.strip()]
            dropped = []

        preset = self.template_combo.currentText()
        wrapped = apply_template(TEMPLATE_PRESETS[preset], output)

        self._last_output = wrapped
        self._last_kept = kept

        self.output_edit.setPlainText(wrapped)
        self.tag_count_label.setText(f"{len(kept)} tags")

        if dropped:
            self.dropped_label.setText(f"Dropped: {', '.join(dropped[:15])}")
        else:
            self.dropped_label.setText("All tags validated successfully")

        self.apply_btn.setVisible(True)
        self.status_label.setText(f"Generated {len(kept)} validated tags")

    def _on_llm_error(self, error_msg):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("⚡ Generate Tags")
        self.status_label.setText(f"Error: {error_msg}")
        self.output_edit.setPlainText(f"Error: {error_msg}")

    def _on_copy(self):
        if self._last_output:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(self._last_output)
            self.status_label.setText("Copied to clipboard")

    def _on_apply(self):
        if self._last_output:
            self.tags_generated.emit(self._last_output)
            self.status_label.setText("Applied to editor")

    def _on_help(self):
        dlg = LLMTagGeneratorHelpDialog(self)
        dlg.exec_()

    def _load_settings(self):
        self.server_edit.setText(self._settings.llm_server_url)
        self.model_edit.setText(self._settings.llm_model)
        self.temp_spin.setValue(self._settings.llm_temperature)
        self.tokens_spin.setValue(self._settings.llm_max_tokens)
        self.thinking_check.setChecked(self._settings.llm_enable_thinking)
        self.api_key_edit.setText(self._settings.llm_api_key)

    def _save_settings(self):
        self._settings.llm_server_url = self.server_edit.text().strip()
        self._settings.llm_model = self.model_edit.text().strip()
        self._settings.llm_temperature = self.temp_spin.value()
        self._settings.llm_max_tokens = self.tokens_spin.value()
        self._settings.llm_enable_thinking = self.thinking_check.isChecked()
        self._settings.llm_api_key = self.api_key_edit.text().strip()

    def closeEvent(self, event):
        self._save_settings()
        self._llm.cancel()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)

    def _glass_stylesheet(self):
        return """
            QDialog {
                background: rgba(16, 18, 26, 0.92);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 14px;
                color: #e2e8f0;
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
            QLineEdit {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 5px; padding: 4px 8px; color: #e2e8f0; font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(139, 92, 246, 0.5);
            }
            QComboBox {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 5px; padding: 4px 8px; color: #e2e8f0; font-size: 11px;
            }
        """
