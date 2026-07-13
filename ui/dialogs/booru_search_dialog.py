# ui/dialogs/booru_search_dialog.py
"""
Booru Search Dialog – search posts with thumbnail gallery, click to pull tags.
"""

import logging
import os
import webbrowser
from collections import OrderedDict
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QProgressBar, QScrollArea, QWidget,
    QGridLayout, QFrame, QSizePolicy, QTextEdit, QSplitter,
    QMenu, QAction, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread, pyqtSlot, QTimer
from PyQt5.QtGui import QPixmap, QImage

from core.booru_source_manager import BooruSourceManager
from ui.windows_theme import set_dark_title_bar

logger = logging.getLogger(__name__)


class ThumbnailCache(OrderedDict):
    """LRU cache for remote thumbnail pixmaps."""
    def __init__(self, maxsize=200):
        super().__init__()
        self._maxsize = maxsize

    def get(self, key):
        if key in self:
            self.move_to_end(key)
            return self[key]
        return None

    def put(self, key, value):
        if key in self:
            self.move_to_end(key)
            self[key] = value
        else:
            if len(self) >= self._maxsize:
                self.popitem(last=False)
            self[key] = value


class ThumbnailWidget(QFrame):
    """A single thumbnail card in the search grid."""
    clicked = pyqtSignal(dict)  # emits post_data
    context_action = pyqtSignal(str, dict)  # action_name, post_data

    def __init__(self, post_data, parent=None):
        super().__init__(parent)
        self.post_data = post_data
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(160, 180)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.setStyleSheet("""
            ThumbnailWidget {
                background: rgba(20, 22, 30, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
            ThumbnailWidget:hover {
                border: 1px solid rgba(139, 92, 246, 0.5);
                background: rgba(30, 32, 42, 0.9);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail image
        self.image_label = QLabel()
        self.image_label.setFixedSize(148, 148)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            "background: rgba(10, 12, 18, 0.6); border-radius: 6px; color: #555;"
        )
        self.image_label.setText("Loading...")
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        # Post ID + source + rating
        post_id = self.post_data.get('id', '?')
        rating = self.post_data.get('rating', '')
        source = self.post_data.get('source', '')
        info_text = f"#{post_id}"
        if source:
            info_text += f"  [{source}]"
        if rating:
            info_text += f"  {rating}"
        info_label = QLabel(info_text)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #888; font-size: 10px; border: none;")
        layout.addWidget(info_label)

    def set_pixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(148, 148, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.post_data)
        super().mousePressEvent(event)

    def _show_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(18, 20, 28, 0.97);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 6px;
                color: #ccc;
            }
            QMenu::item:selected {
                background: rgba(139, 92, 246, 0.25);
                color: #fff;
            }
        """)

        dl_action = menu.addAction("📥  Download Image")
        view_action = menu.addAction("👁  View Image")
        post_action = menu.addAction("🔗  View Post")

        action = menu.exec_(self.mapToGlobal(pos))
        if action == dl_action:
            self.context_action.emit("download", self.post_data)
        elif action == view_action:
            self.context_action.emit("view_image", self.post_data)
        elif action == post_action:
            self.context_action.emit("view_post", self.post_data)


class ImageFetchThread(QThread):
    """Background thread to fetch a single image URL."""
    image_loaded = pyqtSignal(str, QPixmap)  # url, pixmap

    def __init__(self, url, referer="", parent=None):
        super().__init__(parent)
        self.url = url
        self.referer = referer

    def run(self):
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
            )
            headers = {
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            if self.referer:
                headers['Referer'] = self.referer
            response = scraper.get(self.url, timeout=15, headers=headers)
            if response.status_code == 200:
                ct = response.headers.get('content-type', '')
                if 'image' in ct or response.content[:4] in (b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'RIFF'):
                    img = QImage()
                    img.loadFromData(response.content)
                    if not img.isNull():
                        pixmap = QPixmap.fromImage(img)
                        self.image_loaded.emit(self.url, pixmap)
        except Exception as e:
            logger.debug(f"Thumbnail fetch failed for {self.url}: {e}")


class BooruSearchDialog(QDialog):
    """Dialog for searching booru posts with a thumbnail gallery."""

    tags_selected = pyqtSignal(list)  # list of tag strings to import

    def __init__(self, source_manager: BooruSourceManager, parent=None):
        super().__init__(parent)
        self.source_manager = source_manager
        self._cache = ThumbnailCache(maxsize=200)
        self._fetch_threads = []
        self._selected_post = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setWindowTitle("Search Booru Posts")
        self.setMinimumSize(800, 600)
        self.resize(900, 650)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search bar
        search_row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Search tags... (e.g. 1girl solo landscape)")
        self.query_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.query_input, 1)

        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(130)
        self.source_combo.addItem("All Sources", "")
        for name in self.source_manager.get_enabled_source_names():
            self.source_combo.addItem(name, name)
        search_row.addWidget(self.source_combo)

        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setStyleSheet("""
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
        self.search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(3)
        layout.addWidget(self.progress)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Main content: thumbnail grid + detail panel
        splitter = QSplitter(Qt.Horizontal)

        # Thumbnail grid in scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background: rgba(16, 18, 26, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 10px;
            }
            QScrollBar:vertical {
                background: rgba(30, 32, 40, 0.8);
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(139, 92, 246, 0.35);
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(self.grid_widget)
        splitter.addWidget(scroll)

        # Detail panel (right side)
        detail_widget = QWidget()
        detail_widget.setStyleSheet("""
            QWidget {
                background: rgba(16, 18, 26, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 10px;
            }
        """)
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(10, 10, 10, 10)

        self.detail_title = QLabel("Select a post")
        self.detail_title.setStyleSheet("color: #ccc; font-size: 13px; font-weight: bold; border: none;")
        detail_layout.addWidget(self.detail_title)

        self.detail_info = QLabel("")
        self.detail_info.setStyleSheet("color: #888; font-size: 11px; border: none;")
        self.detail_info.setWordWrap(True)
        detail_layout.addWidget(self.detail_info)

        self.detail_tags = QTextEdit()
        self.detail_tags.setReadOnly(True)
        self.detail_tags.setStyleSheet(
            "background: rgba(10,12,18,0.6); color: #ddd; border: 1px solid rgba(255,255,255,0.08); "
            "border-radius: 6px; padding: 6px; font-family: Consolas, monospace; font-size: 11px;"
        )
        detail_layout.addWidget(self.detail_tags, 1)

        self.import_btn = QPushButton("➕ Import Tags to Current Image")
        self.import_btn.setEnabled(False)
        self.import_btn.setStyleSheet("""
            QPushButton {
                background: rgba(34,197,94,0.25);
                color: #86efac;
                border: 1px solid rgba(34,197,94,0.4);
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(34,197,94,0.4);
            }
            QPushButton:disabled {
                background: rgba(50,50,50,0.5);
                color: #666;
                border: 1px solid rgba(80,80,80,0.3);
            }
        """)
        self.import_btn.clicked.connect(self._on_import)
        detail_layout.addWidget(self.import_btn)

        splitter.addWidget(detail_widget)
        splitter.setSizes([600, 250])
        layout.addWidget(splitter, 1)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(100, 100, 120, 0.3);
                color: #ccc;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 6px 20px;
            }
            QPushButton:hover {
                background: rgba(100, 100, 120, 0.5);
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _connect_signals(self):
        self.source_manager.search_posts_results.connect(self._on_search_results)
        self.source_manager.search_posts_error.connect(self._on_search_error)

    def _on_search(self):
        query = self.query_input.text().strip()
        if not query:
            return

        source_name = self.source_combo.currentData()

        # Clear previous results
        self._clear_grid()
        self.detail_title.setText("Select a post")
        self.detail_info.setText("")
        self.detail_tags.clear()
        self.import_btn.setEnabled(False)
        self._selected_post = None

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText(f"Searching '{query}'...")

        self.source_manager.search_posts(query, source_name or None, limit=20)

    def _on_search_results(self, source_name, query, posts):
        self.progress.setVisible(False)
        self.status_label.setText(f"Found {len(posts)} posts")

        cols = max(1, (self.grid_widget.width() - 16) // 168)
        for i, post in enumerate(posts):
            row, col = divmod(i, cols)
            thumb = ThumbnailWidget(post)
            thumb.clicked.connect(self._on_post_clicked)
            thumb.context_action.connect(self._on_context_action)

            # Load thumbnail
            preview_url = post.get('preview_url', '')
            post_source = post.get('source') or source_name
            if preview_url:
                cached = self._cache.get(preview_url)
                if cached:
                    thumb.set_pixmap(cached)
                else:
                    self._fetch_thumbnail(preview_url, thumb, post_source)

            self.grid_layout.addWidget(thumb, row, col)

    def _on_search_error(self, source_name, query, error):
        self.progress.setVisible(False)
        self.status_label.setText(f"Error: {error}")

    def _fetch_thumbnail(self, url, thumb_widget, source_name=""):
        referer_map = {
            'gelbooru': 'https://gelbooru.com/',
            'danbooru': 'https://danbooru.donmai.us/',
            'rule34': 'https://rule34.xxx/',
            'yande.re': 'https://yande.re/',
            'konachan': 'https://konachan.com/',
        }
        source = source_name or self.source_combo.currentData() or ''
        referer = referer_map.get(source.lower(), '')
        thread = ImageFetchThread(url, referer=referer, parent=self)
        thread.image_loaded.connect(lambda u, pm, tw=thumb_widget: self._on_thumbnail_loaded(u, pm, tw))
        thread.finished.connect(lambda: self._cleanup_thread(thread))
        self._fetch_threads.append(thread)
        thread.start()

    def _on_thumbnail_loaded(self, url, pixmap, thumb_widget):
        self._cache.put(url, pixmap)
        thumb_widget.set_pixmap(pixmap)

    def _cleanup_thread(self, thread):
        if thread in self._fetch_threads:
            self._fetch_threads.remove(thread)

    def _on_post_clicked(self, post_data):
        self._selected_post = post_data

        post_id = post_data.get('id', '?')
        rating = post_data.get('rating', 'unknown')
        score = post_data.get('score', 0)
        source = post_data.get('source', '')
        tags = post_data.get('tags', [])
        num_tags = len(tags)

        self.detail_title.setText(f"Post #{post_id}  ({source})")
        self.detail_info.setText(f"Rating: {rating}  |  Score: {score}  |  Tags: {num_tags}")

        # Show tags
        tags_text = ', '.join(tags) if tags else 'No tags available'
        self.detail_tags.setText(tags_text)

        self.import_btn.setEnabled(bool(tags))

    def _on_import(self):
        if not self._selected_post:
            return
        tags = self._selected_post.get('tags', [])
        if tags:
            self.tags_selected.emit(tags)
            self.status_label.setText(f"Imported {len(tags)} tags from post #{self._selected_post.get('id', '?')}")

    def _on_context_action(self, action_name, post_data):
        if action_name == "download":
            self._download_image(post_data)
        elif action_name == "view_image":
            self._view_image(post_data)
        elif action_name == "view_post":
            self._view_post(post_data)

    def _get_post_url(self, post_data):
        source = (post_data.get('source') or '').lower()
        post_id = post_data.get('id', '')
        if not post_id:
            return None
        urls = {
            'danbooru': f"https://danbooru.donmai.us/posts/{post_id}",
            'gelbooru': f"https://gelbooru.com/index.php?page=post&s=view&id={post_id}",
            'rule34': f"https://rule34.xxx/index.php?page=post&s=view&id={post_id}",
            'yande.re': f"https://yande.re/post/show/{post_id}",
            'konachan': f"https://konachan.com/post/show/{post_id}",
        }
        return urls.get(source)

    def _get_file_url(self, post_data):
        return post_data.get('file_url') or post_data.get('large_url') or post_data.get('preview_url')

    def _download_image(self, post_data):
        file_url = self._get_file_url(post_data)
        if not file_url:
            self.status_label.setText("No download URL available")
            return

        source = (post_data.get('source') or 'unknown').replace('.', '_')
        post_id = post_data.get('id', '0')

        ext = 'jpg'
        try:
            from urllib.parse import urlparse
            path = urlparse(file_url).path.lower()
            if path.endswith('.png'):
                ext = 'png'
            elif path.endswith('.gif'):
                ext = 'gif'
            elif path.endswith('.webp'):
                ext = 'webp'
        except Exception:
            pass

        default_name = f"{source}_{post_id}.{ext}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", default_name,
            "Images (*.png *.jpg *.jpeg *.webp *.gif)"
        )
        if not path:
            return

        self.status_label.setText(f"Downloading post #{post_id}...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        source_name = post_data.get('source', '')
        referer_map = {
            'gelbooru': 'https://gelbooru.com/',
            'danbooru': 'https://danbooru.donmai.us/',
            'rule34': 'https://rule34.xxx/',
            'yande.re': 'https://yande.re/',
            'konachan': 'https://konachan.com/',
        }
        referer = referer_map.get(source_name.lower(), '')

        thread = ImageFetchThread(file_url, referer=referer, parent=self)
        thread.image_loaded.connect(lambda u, pm, p=path: self._on_download_complete(pm, p))
        thread.finished.connect(lambda: self._on_download_finished(thread))
        self._fetch_threads.append(thread)
        thread.start()

    def _on_download_complete(self, pixmap, save_path):
        if pixmap and not pixmap.isNull():
            pixmap.save(save_path)
            self.status_label.setText(f"Saved to {os.path.basename(save_path)}")
        else:
            self.status_label.setText("Failed to save image")

    def _on_download_finished(self, thread):
        self.progress.setVisible(False)
        if thread in self._fetch_threads:
            self._fetch_threads.remove(thread)

    def _view_image(self, post_data):
        file_url = self._get_file_url(post_data)
        if not file_url:
            self.status_label.setText("No image URL available")
            return

        source = post_data.get('source', '')
        post_id = post_data.get('id', '?')

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Post #{post_id} [{source}]")
        dlg.setMinimumSize(800, 600)
        dlg.resize(900, 700)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
        dlg.setStyleSheet("""
            QDialog {
                background: rgba(16, 18, 26, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
            }
        """)

        from ui.image_viewer import ImageViewer
        viewer = ImageViewer(dlg)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(4, 4, 4, 4)
        dlg_layout.addWidget(viewer)

        loading_label = QLabel("Loading full image...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("color: #94a3b8; font-size: 13px; border: none;")
        dlg_layout.addWidget(loading_label)

        referer_map = {
            'gelbooru': 'https://gelbooru.com/',
            'danbooru': 'https://danbooru.donmai.us/',
            'rule34': 'https://rule34.xxx/',
            'yande.re': 'https://yande.re/',
            'konachan': 'https://konachan.com/',
        }
        referer = referer_map.get(source.lower(), '')

        thread = ImageFetchThread(file_url, referer=referer, parent=dlg)
        thread.image_loaded.connect(lambda u, pm: self._on_view_loaded(pm, viewer, loading_label))
        thread.finished.connect(lambda: self._cleanup_view_thread(thread, dlg))
        self._fetch_threads.append(thread)

        def on_show(event):
            super(QDialog, dlg).showEvent(event)
            set_dark_title_bar(dlg)
            thread.start()

        dlg.showEvent = on_show
        dlg.exec_()

    def _on_view_loaded(self, pixmap, viewer, loading_label):
        loading_label.setVisible(False)
        viewer.set_pixmap(pixmap)

    def _cleanup_view_thread(self, thread, dlg):
        if thread in self._fetch_threads:
            self._fetch_threads.remove(thread)

    def _view_post(self, post_data):
        url = self._get_post_url(post_data)
        if url:
            webbrowser.open(url)
            self.status_label.setText(f"Opened post in browser")
        else:
            file_url = self._get_file_url(post_data)
            if file_url:
                webbrowser.open(file_url)
                self.status_label.setText("Opened image URL in browser")
            else:
                self.status_label.setText("No URL available")

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)

    def closeEvent(self, event):
        try:
            self.source_manager.search_posts_results.disconnect(self._on_search_results)
            self.source_manager.search_posts_error.disconnect(self._on_search_error)
        except TypeError:
            pass
        for thread in self._fetch_threads:
            if thread.isRunning():
                thread.terminate()
            thread.wait(1000)
        self._fetch_threads.clear()
        super().closeEvent(event)
