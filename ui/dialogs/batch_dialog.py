from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, QDialogButtonBox, QLabel

from ui.windows_theme import set_dark_title_bar


class BatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Batch Operations")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.operation_combo = QComboBox()
        self.operation_combo.addItems(["Add Tag", "Remove Tag", "Replace Tag", "Normalize (sort, deduplicate)"])
        form.addRow("Operation:", self.operation_combo)

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Tag name (for Add/Remove/Replace)")
        form.addRow("Tag:", self.tag_input)

        self.replace_with = QLineEdit()
        self.replace_with.setPlaceholderText("Replace with (for Replace)")
        form.addRow("Replace with:", self.replace_with)

        layout.addLayout(form)

        self.info_label = QLabel("Applies to all images in the current folder.")
        self.info_label.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(self.info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "operation": self.operation_combo.currentText(),
            "tag": self.tag_input.text().strip(),
            "replace_with": self.replace_with.text().strip()
        }

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)