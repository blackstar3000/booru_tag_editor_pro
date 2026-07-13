from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox, QLabel, QPushButton, QMessageBox, QTextEdit, QHBoxLayout
from PyQt5.QtGui import QGuiApplication, QDesktopServices
from PyQt5.QtCore import QUrl
import cloudscraper
import logging

from ui.windows_theme import set_dark_title_bar, dark_question, dark_information, dark_warning, dark_critical

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    def __init__(self, parent, current_username, current_api_key, current_cookies=""):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Danbooru Settings")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Get your API key from your Danbooru profile → My Account.\n\n"
            "If you get Cloudflare errors, paste your browser cookies below.\n"
            "How to get cookies:\n"
            "1. Open Danbooru in Chrome/Firefox\n"
            "2. F12 → Network tab → click the first 'danbooru.donmai.us' request\n"
            "3. Headers tab → Copy the entire 'Cookie:' value"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(info)

        # Open Danbooru button
        open_btn = QPushButton("🌐 Open Danbooru in Browser")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://danbooru.donmai.us")))
        layout.addWidget(open_btn)

        form = QFormLayout()
        self.username_input = QLineEdit(current_username or "")
        self.api_key_input = QLineEdit(current_api_key or "")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        form.addRow("Username:", self.username_input)
        form.addRow("API Key:", self.api_key_input)

        # Cookies row with paste button
        cookies_row = QHBoxLayout()
        self.cookies_input = QTextEdit()
        self.cookies_input.setPlaceholderText("Paste cookies here, e.g.: cf_clearance=...; _danbooru_session=...")
        self.cookies_input.setMaximumHeight(60)
        self.cookies_input.setPlainText(current_cookies or "")
        cookies_row.addWidget(self.cookies_input)
        paste_btn = QPushButton("📋 Paste")
        paste_btn.setToolTip("Paste from clipboard")
        paste_btn.clicked.connect(self._paste_from_clipboard)
        cookies_row.addWidget(paste_btn)
        form.addRow("Cookies:", cookies_row)

        layout.addLayout(form)

        test_btn = QPushButton("🔍 Test Credentials")
        test_btn.clicked.connect(self.test_credentials)
        layout.addWidget(test_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _paste_from_clipboard(self):
        clipboard = QGuiApplication.clipboard()
        text = clipboard.text()
        if text:
            self.cookies_input.setPlainText(text)
            dark_information(self, "Pasted", "Cookies pasted from clipboard.")

    def test_credentials(self):
        username = self.username_input.text().strip()
        api_key = self.api_key_input.text().strip()
        cookies = self.cookies_input.toPlainText().strip()
        if not username or not api_key:
            dark_warning(self, "Missing Credentials", "Please enter both username and API key.")
            return
        try:
            scraper = cloudscraper.create_scraper()
            if cookies:
                for item in cookies.split(';'):
                    if '=' in item:
                        key, val = item.strip().split('=', 1)
                        scraper.cookies.set(key.strip(), val.strip())
            url = f"https://danbooru.donmai.us/tags.json?search[name]=1girl&login={username}&api_key={api_key}"
            response = scraper.get(url, timeout=10)
            if response.status_code == 200:
                dark_information(self, "Success", "Credentials are valid and API is reachable!")
            else:
                dark_warning(self, "Error", f"API returned status {response.status_code}.\nResponse: {response.text[:200]}")
        except Exception as e:
            dark_critical(self, "Error", f"Failed to connect to Danbooru:\n{e}")

    def values(self):
        return (
            self.username_input.text().strip(),
            self.api_key_input.text().strip(),
            self.cookies_input.toPlainText().strip()
        )

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)