from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QMessageBox,
    QFileDialog, QAbstractItemView,
)
from PyQt5.QtCore import Qt, pyqtSignal

from ui.windows_theme import set_dark_title_bar, dark_get_text, dark_question


class WorkspaceManagerDialog(QDialog):
    """Dialog for managing all workspaces."""

    workspace_selected = pyqtSignal(str)   # load requested
    workspace_deleted = pyqtSignal(str)
    workspace_renamed = pyqtSignal(str, str)  # old, new
    workspace_duplicated = pyqtSignal(str, str)  # source, dest
    workspace_imported = pyqtSignal(str)   # imported name
    workspace_exported = pyqtSignal(str, str)   # name, destination path
    set_startup_requested = pyqtSignal(str)
    restore_default_requested = pyqtSignal()

    def __init__(self, parent, workspace_names: list[str], startup_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Workspace Manager")
        self.setMinimumSize(520, 400)
        self._names = list(workspace_names)
        self._startup = startup_name

        layout = QVBoxLayout(self)

        header = QLabel("Workspaces")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        self._refresh_list()

        btn_row = QHBoxLayout()

        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self._on_load)
        btn_row.addWidget(self.load_btn)

        self.rename_btn = QPushButton("Rename")
        self.rename_btn.clicked.connect(self._on_rename)
        btn_row.addWidget(self.rename_btn)

        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.clicked.connect(self._on_duplicate)
        btn_row.addWidget(self.duplicate_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()

        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._on_import)
        btn_row.addWidget(self.import_btn)

        layout.addLayout(btn_row)

        btn_row2 = QHBoxLayout()

        self.startup_btn = QPushButton("Set Startup View")
        self.startup_btn.clicked.connect(self._on_set_startup)
        btn_row2.addWidget(self.startup_btn)

        self.restore_btn = QPushButton("Restore Default")
        self.restore_btn.clicked.connect(self._on_restore_default)
        btn_row2.addWidget(self.restore_btn)

        btn_row2.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row2.addWidget(close_btn)

        layout.addLayout(btn_row2)

    def _refresh_list(self):
        self.list_widget.clear()
        for name in self._names:
            label = name
            if name == self._startup:
                label = f"{name}  (startup)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, name)
            self.list_widget.addItem(item)

    def _selected_name(self) -> str | None:
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def _on_double_click(self, item):
        name = item.data(Qt.UserRole)
        if name:
            self.workspace_selected.emit(name)
            self.accept()

    def _on_load(self):
        name = self._selected_name()
        if name:
            self.workspace_selected.emit(name)
            self.accept()

    def _on_rename(self):
        name = self._selected_name()
        if not name:
            return
        new_name, ok = dark_get_text(self, "Rename Workspace", "New name:", text=name)
        if ok and new_name.strip() and new_name.strip() != name:
            self.workspace_renamed.emit(name, new_name.strip())

    def _on_duplicate(self):
        name = self._selected_name()
        if not name:
            return
        new_name, ok = dark_get_text(self, "Duplicate Workspace", "New name:", text=f"{name} Copy")
        if ok and new_name.strip():
            self.workspace_duplicated.emit(name, new_name.strip())

    def _on_delete(self):
        name = self._selected_name()
        if not name:
            return
        reply = dark_question(
            self, "Delete Workspace",
            f"Delete workspace '{name}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.workspace_deleted.emit(name)

    def _on_export(self):
        name = self._selected_name()
        if not name:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Workspace", f"{name}.workspace.json",
            "Workspace Files (*.workspace.json);;All Files (*)",
        )
        if dest:
            self.workspace_exported.emit(name, dest)

    def _on_import(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Workspace", "",
            "Workspace Files (*.workspace.json *.json);;All Files (*)",
        )
        if file_path:
            self.workspace_imported.emit(file_path)

    def _on_set_startup(self):
        name = self._selected_name()
        if name:
            self.set_startup_requested.emit(name)
            self._startup = name
            self._refresh_list()

    def _on_restore_default(self):
        self.restore_default_requested.emit()
        self._startup = "Default"
        self._refresh_list()

    def refresh_names(self, names: list[str], startup: str = ""):
        self._names = list(names)
        self._startup = startup
        self._refresh_list()

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
