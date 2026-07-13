from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QScrollArea, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from ui.windows_theme import set_dark_title_bar

CATEGORY_NAMES = {0: "General", 1: "Artist", 3: "Copyright", 4: "Character", 5: "Meta"}


class ClickableLabel(QLabel):
    def __init__(self, text, url, parent=None):
        super().__init__(parent)
        self._url = url
        self.setText(f'<a href="#" style="color:#8B5CF6;">{text}</a>')
        self.setOpenExternalLinks(False)
        self.mousePressEvent = lambda e: self._open_url()

    def _open_url(self):
        import subprocess, sys
        if sys.platform == 'win32':
            subprocess.Popen(['start', self._url], shell=True)
        else:
            subprocess.Popen(['open', self._url])


class TagInspector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle("Smart Tag Inspector")
        self.setMinimumSize(500, 500)
        layout = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)
        self._preview_labels = []
        self.clear()

    def display_tag_info(self, tag: str, info: dict):
        self.clear()
        if not info:
            self.content_layout.addWidget(QLabel(f"Tag: {tag}\nNo info available."))
            settings_btn = QPushButton("Open Settings to set Danbooru credentials")
            settings_btn.clicked.connect(self._open_settings)
            self.content_layout.addWidget(settings_btn)
            return
        if "error" in info:
            self.content_layout.addWidget(QLabel(f"Tag: {tag}\nError: {info['error']}"))
            settings_btn = QPushButton("Open Settings to check credentials")
            settings_btn.clicked.connect(self._open_settings)
            self.content_layout.addWidget(settings_btn)
            return
        name = info.get('name', tag)
        category = info.get('category', 0)
        post_count = info.get('post_count', 0)
        cat_name = CATEGORY_NAMES.get(category, f"Unknown ({category})")

        title_label = QLabel(f"<h2>{name}</h2>")
        self.content_layout.addWidget(title_label)
        self.content_layout.addWidget(QLabel(f"Category: <b>{cat_name}</b>"))
        self.content_layout.addWidget(QLabel(f"Post count: <b>{post_count:,}</b>"))

        url = f"https://danbooru.donmai.us/wiki_pages/{name}"
        link = ClickableLabel("Open on Danbooru", url)
        self.content_layout.addWidget(link)

    def display_wiki(self, tag: str, body: str):
        if not body:
            return
        sep = QLabel("<hr>")
        self.content_layout.addWidget(sep)
        desc_label = QLabel("<b>Description</b>")
        self.content_layout.addWidget(desc_label)
        desc_text = QTextEdit()
        desc_text.setReadOnly(True)
        desc_text.setPlainText(body)
        desc_text.setMaximumHeight(200)
        self.content_layout.addWidget(desc_text)

    def display_example_posts(self, tag: str, posts: list):
        if not posts:
            return
        sep = QLabel("<hr>")
        self.content_layout.addWidget(sep)
        example_label = QLabel("<b>Example Images</b>")
        self.content_layout.addWidget(example_label)

        row = QHBoxLayout()
        self._preview_labels = []
        for i, post in enumerate(posts):
            vbox = QVBoxLayout()
            preview = QLabel()
            preview.setFixedSize(150, 150)
            preview.setAlignment(Qt.AlignCenter)
            preview.setStyleSheet("background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 4px;")
            preview.setText("Loading...")
            self._preview_labels.append(preview)
            vbox.addWidget(preview)

            pid = post.get('id', '')
            post_url = f"https://danbooru.donmai.us/posts/{pid}"
            link = ClickableLabel(f"Post #{pid}", post_url)
            vbox.addWidget(link, alignment=Qt.AlignCenter)

            row.addLayout(vbox)
        self.content_layout.addLayout(row)
        self.content_layout.addStretch()

    def set_preview_image(self, tag: str, index: int, pixmap: QPixmap):
        if index < len(self._preview_labels):
            scaled = pixmap.scaled(148, 148, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._preview_labels[index].setPixmap(scaled)

    def _open_settings(self):
        parent = self.parent()
        while parent:
            if hasattr(parent, 'open_settings'):
                parent.open_settings()
                break
            parent = parent.parent()

    def clear(self):
        self._preview_labels = []
        self._clear_layout(self.content_layout)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
