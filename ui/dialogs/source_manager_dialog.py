# ui/dialogs/source_manager_dialog.py
# Dialog for managing booru sources (enable/disable, configure credentials).

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QPushButton, QLineEdit, QCheckBox, QMessageBox, QWidget,
    QFormLayout, QGroupBox, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
import logging

logger = logging.getLogger(__name__)


class SourceConfigWidget(QWidget):
    """Configuration widget for a single booru source."""

    settings_changed = pyqtSignal(str)  # source_name

    def __init__(self, source_name, client, settings, parent=None):
        super().__init__(parent)
        self.source_name = source_name
        self.client = client
        self.settings = settings
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Enable toggle
        self.enable_check = QCheckBox(f"Enable {self.source_name}")
        self.enable_check.setChecked(self.client.enabled)
        self.enable_check.stateChanged.connect(self._on_enable_changed)
        layout.addWidget(self.enable_check)

        # Auth info
        auth_group = QGroupBox("Authentication")
        auth_layout = QFormLayout(auth_group)

        self._auth_fields = {}

        if self.source_name == "Danbooru":
            self._add_field(auth_layout, "Username", "danbooru_username")
            self._add_field(auth_layout, "API Key", "danbooru_api_key")
            self._add_field(auth_layout, "Cookies", "danbooru_cookies")
        elif self.source_name == "Gelbooru":
            self._add_field(auth_layout, "Numeric User ID", "gelbooru_user_id")
            self._add_field(auth_layout, "API Key", "gelbooru_api_key")
            self._add_field(auth_layout, "Cookies", "gelbooru_cookies")
        elif self.source_name == "Rule34":
            self._add_field(auth_layout, "User ID", "rule34_user_id")
            self._add_field(auth_layout, "API Key", "rule34_api_key")
        elif self.source_name == "yande.re":
            self._add_field(auth_layout, "API Key (optional)", "yandere_api_key")
            self._add_field(auth_layout, "Cookies (optional)", "yandere_cookies")
        elif self.source_name == "Konachan":
            auth_layout.addRow(QLabel("No authentication required."))

        layout.addWidget(auth_group)

        # Status
        self.status_label = QLabel()
        self._update_status()
        layout.addWidget(self.status_label)

        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

    def _add_field(self, layout, label, key):
        field = QLineEdit()
        current = self.settings.get(key, "") or ""
        field.setText(current)
        field.setMinimumWidth(250)
        if "key" in label.lower() or "cookie" in label.lower():
            field.setEchoMode(QLineEdit.Password)
        layout.addRow(label, field)
        self._auth_fields[key] = field

    def _update_status(self):
        if self.client.enabled:
            if self.client._has_credentials() or not self.client.requires_auth:
                self.status_label.setText("✅ Ready")
                self.status_label.setStyleSheet("color: #4ade80;")
            else:
                self.status_label.setText("⚠️ Credentials not configured")
                self.status_label.setStyleSheet("color: #fbbf24;")
        else:
            self.status_label.setText("⛔ Disabled")
            self.status_label.setStyleSheet("color: #666;")

    def _on_enable_changed(self, state):
        enabled = state == Qt.Checked
        self.client.enabled = enabled
        self.settings.set(f"source_{self.source_name}_enabled", enabled)
        self._update_status()
        self.settings_changed.emit(self.source_name)

    def _save_settings(self):
        for key, field in self._auth_fields.items():
            self.settings.set(key, field.text())
        self.client.reload_settings()
        self._update_status()
        QMessageBox.information(self, "Settings Saved",
            f"{self.source_name} settings saved. Caches cleared.")


class SourceManagerDialog(QDialog):
    """Dialog for managing all booru sources."""

    sources_changed = pyqtSignal()

    def __init__(self, source_manager, parent=None):
        super().__init__(parent)
        self.source_manager = source_manager
        self.setWindowTitle("Booru Sources")
        self.setMinimumSize(520, 450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Configure Booru Sources")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Enable or disable booru sources for tag lookup and autocomplete. "
            "Each source requires its own API credentials."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #999; margin-bottom: 8px;")
        layout.addWidget(desc)

        # Tabs for each source
        self.tabs = QTabWidget()

        for name in self.source_manager.get_source_names():
            client = self.source_manager.get_client(name)
            if client:
                widget = SourceConfigWidget(name, client, self.source_manager.settings)
                widget.settings_changed.connect(self._on_source_changed)
                self.tabs.addTab(widget, name)

        layout.addWidget(self.tabs)

        # Bottom buttons
        btn_row = QHBoxLayout()

        enable_all_btn = QPushButton("Enable All")
        enable_all_btn.clicked.connect(self._enable_all)
        btn_row.addWidget(enable_all_btn)

        disable_all_btn = QPushButton("Disable All")
        disable_all_btn.clicked.connect(self._disable_all)
        btn_row.addWidget(disable_all_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _on_source_changed(self, source_name):
        self.sources_changed.emit()

    def _enable_all(self):
        for name in self.source_manager.get_source_names():
            self.source_manager.set_source_enabled(name, True)
        # Refresh all tabs
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, 'enable_check'):
                widget.enable_check.setChecked(True)
                widget._update_status()

    def _disable_all(self):
        for name in self.source_manager.get_source_names():
            self.source_manager.set_source_enabled(name, False)
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(widget, 'enable_check'):
                widget.enable_check.setChecked(False)
                widget._update_status()
