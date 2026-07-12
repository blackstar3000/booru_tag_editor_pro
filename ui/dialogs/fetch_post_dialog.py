# ui/dialogs/fetch_post_dialog.py
"""
Fetch Post Dialog – paste a booru URL or ID, fetch tags from any source.
"""

import re
import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QGroupBox, QCheckBox, QMessageBox, QHeaderView,
    QTextEdit, QSplitter, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices

from core.booru_source_manager import BooruSourceManager

logger = logging.getLogger(__name__)

# URL pattern → source name mapping
SOURCE_URL_MAP = {
    'danbooru.donmai.us': 'Danbooru',
    'gelbooru.com': 'Gelbooru',
    'yande.re': 'yande.re',
    'konachan.com': 'Konachan',
    'rule34.xxx': 'Rule34',
    'rule34.eu': 'Rule34',
    'e621.net': 'e621',
}

CATEGORY_LABELS = {
    'artist': 'Artist',
    'copyright': 'Copyright',
    'character': 'Character',
    'general': 'General',
    'meta': 'Meta',
}


def _detect_source_from_url(url: str) -> str:
    """Auto-detect booru source from a URL."""
    url_lower = url.lower()
    for pattern, source in SOURCE_URL_MAP.items():
        if pattern in url_lower:
            return source
    return ""


def _extract_post_id(url_or_id: str) -> str:
    """Extract post ID from a URL or 'id:xxxxxx' format."""
    url_or_id = url_or_id.strip()

    # id:xxxxxx format
    match = re.match(r'^id[:\s]+(\d+)$', url_or_id, re.IGNORECASE)
    if match:
        return match.group(1)

    # URL with /posts/xxxxxx or /post/show/xxxxxx
    match = re.search(r'/posts?/(?:show/)?(\d+)', url_or_id)
    if match:
        return match.group(1)

    # Query param id=NNNNN (Rule34, Gelbooru page=post)
    match = re.search(r'[?&]id=(\d+)', url_or_id)
    if match:
        return match.group(1)

    # Plain numeric ID
    if url_or_id.isdigit():
        return url_or_id

    return ""


class FetchPostDialog(QDialog):
    """Dialog to fetch tags from a booru post by URL or ID."""

    tags_fetched = pyqtSignal(list)  # list of tag strings to add

    def __init__(self, source_manager: BooruSourceManager, parent=None):
        super().__init__(parent)
        self.source_manager = source_manager
        self._post_data = None
        self._selected_tags = []
        self.setWindowTitle("Fetch Tags from Booru Post")
        self.setMinimumSize(700, 550)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # URL input row
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("URL or ID:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://danbooru.donmai.us/posts/4861569  or  id:4861569  or  4861569")
        self.url_input.returnPressed.connect(self._on_fetch)
        url_row.addWidget(self.url_input, 1)
        layout.addLayout(url_row)

        # Source selection row
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source:"))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(150)
        src_row.addWidget(self.source_combo)
        src_row.addStretch()

        self.fetch_btn = QPushButton("🔍 Fetch")
        self.fetch_btn.setStyleSheet("""
            QPushButton {
                background: rgba(139,92,246,0.3);
                color: white;
                border: 1px solid rgba(139,92,246,0.5);
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(139,92,246,0.5);
            }
        """)
        self.fetch_btn.clicked.connect(self._on_fetch)
        src_row.addWidget(self.fetch_btn)
        layout.addLayout(src_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(3)
        layout.addWidget(self.progress)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Results area
        splitter = QSplitter(Qt.Vertical)

        # Tags by category
        tags_group = QGroupBox("Tags")
        tags_layout = QVBoxLayout(tags_group)

        # Category checkboxes
        cat_row = QHBoxLayout()
        self.cat_checkboxes = {}
        for cat_key, label in CATEGORY_LABELS.items():
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_selected_tags)
            self.cat_checkboxes[cat_key] = cb
            cat_row.addWidget(cb)
        cat_row.addStretch()
        tags_layout.addLayout(cat_row)

        # Tags display
        self.tags_display = QTextEdit()
        self.tags_display.setReadOnly(True)
        self.tags_display.setMaximumHeight(150)
        self.tags_display.setStyleSheet("background: rgba(30,32,36,200); color: #ddd; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px; font-family: Consolas, monospace; font-size: 11px;")
        tags_layout.addWidget(self.tags_display)

        # Format options
        fmt_row = QHBoxLayout()
        self.underscore_cb = QCheckBox("Replace _ with spaces")
        self.underscore_cb.setChecked(False)
        self.underscore_cb.stateChanged.connect(self._update_selected_tags)
        fmt_row.addWidget(self.underscore_cb)
        self.comma_cb = QCheckBox("Comma-separated")
        self.comma_cb.setChecked(True)
        self.comma_cb.stateChanged.connect(self._update_selected_tags)
        fmt_row.addWidget(self.comma_cb)
        fmt_row.addStretch()
        tags_layout.addLayout(fmt_row)

        splitter.addWidget(tags_group)

        # Post info
        info_group = QGroupBox("Post Info")
        info_layout = QVBoxLayout(info_group)
        self.info_display = QLabel("No post loaded.")
        self.info_display.setStyleSheet("color: #aaa;")
        self.info_display.setWordWrap(True)
        info_layout.addWidget(self.info_display)

        link_row = QHBoxLayout()
        self.open_link_btn = QPushButton("🔗 Open in Browser")
        self.open_link_btn.setEnabled(False)
        self.open_link_btn.clicked.connect(self._open_link)
        link_row.addWidget(self.open_link_btn)
        link_row.addStretch()
        info_layout.addLayout(link_row)

        splitter.addWidget(info_group)
        splitter.setSizes([300, 150])
        layout.addWidget(splitter)

        # Action buttons
        btn_row = QHBoxLayout()
        self.add_tags_btn = QPushButton("➕ Add Tags to Current Image")
        self.add_tags_btn.setEnabled(False)
        self.add_tags_btn.setStyleSheet("""
            QPushButton {
                background: rgba(34,197,94,0.25);
                color: #86efac;
                border: 1px solid rgba(34,197,94,0.4);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(34,197,94,0.4);
            }
            QPushButton:disabled {
                background: rgba(50,50,50,0.5);
                color: #666;
                border-color: rgba(255,255,255,0.05);
            }
        """)
        self.add_tags_btn.clicked.connect(self._on_add_tags)
        btn_row.addWidget(self.add_tags_btn)

        self.replace_tags_btn = QPushButton("🔄 Replace All Tags")
        self.replace_tags_btn.setEnabled(False)
        self.replace_tags_btn.setStyleSheet("""
            QPushButton {
                background: rgba(234,179,8,0.2);
                color: #fde047;
                border: 1px solid rgba(234,179,8,0.4);
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(234,179,8,0.35);
            }
            QPushButton:disabled {
                background: rgba(50,50,50,0.5);
                color: #666;
                border-color: rgba(255,255,255,0.05);
            }
        """)
        self.replace_tags_btn.clicked.connect(self._on_replace_tags)
        btn_row.addWidget(self.replace_tags_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._populate_sources()

    def _populate_sources(self):
        self.source_combo.clear()
        self.source_combo.addItem("Auto-detect", "")
        for name in self.source_manager.get_source_names():
            self.source_combo.addItem(name, name)

    def _connect_signals(self):
        self.source_manager.post_fetched.connect(self._on_post_fetched)
        self.source_manager.post_fetch_error.connect(self._on_post_error)
        self.url_input.textChanged.connect(self._on_url_changed)

    def _on_url_changed(self, text):
        source = _detect_source_from_url(text)
        if source:
            idx = self.source_combo.findData(source)
            if idx >= 0:
                self.source_combo.setCurrentIndex(idx)

    def _on_fetch(self):
        url = self.url_input.text().strip()
        if not url:
            return

        post_id = _extract_post_id(url)
        if not post_id:
            self.status_label.setText("Could not extract post ID from input.")
            return

        source_name = self.source_combo.currentData()

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.fetch_btn.setEnabled(False)
        self.status_label.setText(f"Fetching post {post_id}...")

        self.source_manager.fetch_post_by_id(post_id, source_name or None)

    def _on_post_fetched(self, source_name, post_data):
        self.progress.setVisible(False)
        self.fetch_btn.setEnabled(True)
        self._post_data = post_data
        self._selected_tags = []

        post_id = post_data.get('id', '?')
        rating = post_data.get('rating', '')
        score = post_data.get('score', 0)
        self.status_label.setText(f"Fetched from {source_name}")
        self.info_display.setText(
            f"Post #{post_id}  |  Rating: {rating}  |  Score: {score}  |  "
            f"Tags: {len(post_data.get('tags', []))}"
        )

        self._update_selected_tags()
        self.add_tags_btn.setEnabled(True)
        self.replace_tags_btn.setEnabled(True)

        file_url = post_data.get('file_url', '')
        self.open_link_btn.setEnabled(bool(file_url))
        self.open_link_btn.setProperty('url', file_url)

    def _on_post_error(self, source_name, error):
        self.progress.setVisible(False)
        self.fetch_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error}")
        self.add_tags_btn.setEnabled(False)
        self.replace_tags_btn.setEnabled(False)

    def _update_selected_tags(self):
        if not self._post_data:
            return

        tags_by_category = self._post_data.get('tags_by_category', {})
        replace_underscores = self.underscore_cb.isChecked()
        comma_separated = self.comma_cb.isChecked()

        selected = []
        display_lines = []

        for cat_key in ['artist', 'copyright', 'character', 'general', 'meta']:
            if not self.cat_checkboxes[cat_key].isChecked():
                continue
            tags = tags_by_category.get(cat_key, [])
            if not tags:
                continue

            cat_label = CATEGORY_LABELS.get(cat_key, cat_key)
            formatted = []
            for t in tags:
                name = t.replace('_', ' ') if replace_underscores else t
                formatted.append(name)
                selected.append(name)

            sep = ', ' if comma_separated else ' '
            display_lines.append(f"[{cat_label}] {sep.join(formatted)}")

        self.tags_display.setPlainText('\n'.join(display_lines))
        self._selected_tags = selected

    def _open_link(self):
        url = self.open_link_btn.property('url')
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _on_add_tags(self):
        if self._selected_tags:
            self.tags_fetched.emit(self._selected_tags)
            self.status_label.setText(f"Added {len(self._selected_tags)} tags.")

    def _on_replace_tags(self):
        if self._selected_tags:
            self.tags_fetched.emit(self._selected_tags)
            self.status_label.setText(f"Replaced with {len(self._selected_tags)} tags.")
